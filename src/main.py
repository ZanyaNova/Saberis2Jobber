import os
import json
from flask import Flask, request, redirect, url_for, render_template, jsonify, Response
from .gsheet.catalog_manager import catalog_manager
from .saberis_ingestion import ingest_saberis_exports, SaberisExportRecord

# Auth and Config
from .jobber_auth_flow import get_authorization_url, exchange_code_for_token, get_valid_access_token, verify_state_parameter
from .jobber_client_module import JobberClient, QuoteNodeGQL, QuoteLineEditItemGQL, QuoteEditLineItemInputGQL
from .jobber_models import get_line_items_from_export, SaberisOrder
from typing import Dict, Any, TypedDict, List, Union, Tuple

# Flask App Initialization
app = Flask(__name__)
# Secret key is needed for session management (to store OAuth state)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

class SaberisExportPayload(TypedDict):
    saberis_id: str
    quantity: int

class SendToJobberPayload(TypedDict):
    quoteId: str
    exports: List[SaberisExportPayload]

class EnrichedSaberisExportRecord(SaberisExportRecord):
    """
    Extends the basic manifest record with data needed for quote calculation.
    """
    catalogs: List[str]
    costs_by_catalog: Dict[str, float]

# ---------------------------------------------------------------------------
# Data Transformation
# ---------------------------------------------------------------------------

def _transform_quote_for_ui(quote_node: QuoteNodeGQL) -> Dict[str, Any]:
    """Transforms a detailed QuoteNodeGQL object into a simple dict for the UI."""
    shipping_address = "Address not available"
    property_data = quote_node.get("property")
    if property_data:
        address_data = property_data.get("address", {})
        parts = [
            address_data.get("street1"),
            address_data.get("city"),
            address_data.get("province")
        ]
        address_str = ", ".join(filter(None, parts))
        if address_data.get("postalCode"):
            address_str += f" {address_data.get('postalCode')}"
        if address_str:
            shipping_address = address_str

    total = quote_node.get("amounts", {}).get("total", 0.0)

    return {
        "id": quote_node["id"],
        "client_name": quote_node["client"]["name"],
        "shipping_address": shipping_address,
        "total": f"${total:,.2f}",
        "approved_date": quote_node["transitionedAt"].split('T')[0]
    }



# ---------------------------------------------------------------------------
# Flask Web Routes
# ---------------------------------------------------------------------------

@app.route('/api/jobber-quotes')
def get_jobber_quotes():
    """
    API endpoint to serve a list of approved Jobber quotes.
    Supports pagination via a 'cursor' query parameter.
    """
    # Check for authorization first
    if get_valid_access_token() is None:
        return jsonify({"error": "Not authorized with Jobber"}), 401

    jobber_client = JobberClient()
    cursor = request.args.get('cursor', None) # Get cursor from query params

    try:
        # Fetch a page of quotes using our new method
        quote_page = jobber_client.get_approved_quotes(cursor=cursor)
        
        # Transform each quote for the UI
        transformed_quotes = [
            _transform_quote_for_ui(quote) for quote in quote_page["quotes"]
        ]
        
        # Return the transformed data along with pagination info
        return jsonify({
            "quotes": transformed_quotes,
            "next_cursor": quote_page["next_cursor"],
            "has_next_page": quote_page["has_next_page"]
        })
    except ConnectionRefusedError as e:
        print(f"AUTH_ERROR in endpoint: {e}")
        return jsonify({"error": str(e)}), 401

    except Exception as e:
        # If the client raises an error (e.g., connection issue, API error), return it
        print(f"ERROR: Could not fetch Jobber quotes: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/saberis-exports')
def get_saberis_exports():
    """
    API endpoint to run the ingestion logic and return the manifest,
    now enriched with detailed, type-safe catalog and cost data.
    """
    manifest_records: List[SaberisExportRecord] = ingest_saberis_exports()
    
    enriched_records: List[EnrichedSaberisExportRecord] = []
    for record in manifest_records:
        try:
            with open(record['stored_path'], 'r') as f:
                saberis_data: Any = json.load(f)
            
            saberis_order = SaberisOrder.from_json(saberis_data)
            
            # Create a new, strongly-typed dictionary instead of modifying the old one.
            # This is clean, explicit, and respects the TypedDict contract.
            enriched_record: EnrichedSaberisExportRecord = {
                **record,  # Unpack all key-value pairs from the original record
                "catalogs": list(saberis_order.catalogs),
                "costs_by_catalog": saberis_order.catalog_to_total_cost, # Use the pre-calculated dictionary
            }
            enriched_records.append(enriched_record)

        except (IOError, json.JSONDecodeError) as e:
            print(f"WARN: Could not process file {record['stored_path']} for enrichment. Skipping. Error: {e}")
            
    return jsonify(enriched_records)



@app.route('/api/send-to-jobber', methods=['POST'])
def send_to_jobber():
    """
    API endpoint to add/update items on a Jobber quote from Saberis exports.
    1. Fetches the current line items on the quote.
    2. Compares with items generated from Saberis exports.
    3. Updates quantities for existing items.
    4. Adds new items that don't exist.
    """
    if get_valid_access_token() is None:
        return jsonify({"error": "Not authorized with Jobber"}), 401

    data: SendToJobberPayload = request.get_json()
    quote_id = data.get('quoteId')
    exports_payload = data.get('exports')

    if not quote_id or not exports_payload:
        return jsonify({"error": "Missing quoteId or exports data"}), 400

    jobber_client = JobberClient()
    saberis_export_records = ingest_saberis_exports()
    manifest = {item['saberis_id']: item for item in saberis_export_records}

    # ---  Generate all desired line items ---
    all_desired_line_items: List[QuoteLineEditItemGQL] = []
    for export_data in exports_payload:
        saberis_id = export_data.get('saberis_id')
        quantity = export_data.get('quantity')

        if saberis_id and quantity and saberis_id in manifest:
            stored_path = manifest[saberis_id]['stored_path']
            line_items = get_line_items_from_export(stored_path, quantity)
            all_desired_line_items.extend(line_items)

    if not all_desired_line_items:
        return jsonify({"error": "No valid line items could be generated"}), 400

    # --- New Logic: Step 2 - Fetch existing line items from the quote ---
    quote_details = jobber_client.get_quote_with_line_items(quote_id)
    if not quote_details:
        return jsonify({"error": "Could not fetch existing quote details from Jobber."}), 500

    existing_line_items_nodes = quote_details.get("lineItems", {}).get("nodes", [])
    existing_items_map = {item['name']: item for item in existing_line_items_nodes}

    # --- New Logic: Step 3 - Compare and categorize ---
    items_to_add: List[QuoteLineEditItemGQL] = []
    items_to_update: List[QuoteEditLineItemInputGQL] = []

    for desired_item in all_desired_line_items:
        desired_name = desired_item['name']
        if desired_name in existing_items_map:
            # Item exists, check if quantity needs updating
            existing_item = existing_items_map[desired_name]
            if existing_item['quantity'] != desired_item['quantity']:
                items_to_update.append({
                    "lineItemId": existing_item['id'],
                    "quantity": desired_item['quantity']
                })
        else:
            # Item is new
            items_to_add.append(desired_item)

    # --- New Logic: Step 4 - Execute API Calls ---
    update_success, update_message = jobber_client.update_line_items_on_quote(quote_id, items_to_update)
    add_success, add_message = jobber_client.add_line_items_to_quote(quote_id, items_to_add)

    # --- New Logic: Step 5 - Report Results ---
    final_messages: list[str] = []
    if not update_success:
        final_messages.append(f"Update failed: {update_message}")
    if not add_success:
        final_messages.append(f"Add failed: {add_message}")

    if final_messages:
        return jsonify({"error": " | ".join(final_messages)}), 500
    else:
        # Combine success messages for a comprehensive status
        final_messages.append(update_message)
        final_messages.append(add_message)
        return jsonify({"message": " ".join(filter(None, final_messages))})

@app.route('/api/catalog-markup/<string:catalog_id>', methods=['GET'])
def get_catalog_markup(catalog_id: str) -> Union[Response, Tuple[Response, int]]:
    """
    API endpoint to get the markup for a specific catalog.
    """
    try:
        markup = catalog_manager.get_markup(catalog_id)
        return jsonify({"catalog_id": catalog_id, "markup": markup})
    except Exception as e:
        print(f"ERROR: Could not fetch markup for {catalog_id}: {e}")
        # This now correctly matches the return type hint
        return jsonify({"catalog_id": catalog_id, "markup": 0.035}), 500

@app.route('/api/catalog-markups', methods=['POST'])
def save_catalog_markups() -> Union[Response, Tuple[Response, int]]:
    """
    API endpoint to save markup values for multiple catalogs.
    Expects a JSON payload like: {"CATALOG_A": 0.05, "CATALOG_B": 0.10}
    """
    data: Any = request.get_json()
    
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid payload format. Expected a JSON object."}), 400

    # After the check above, the linter knows 'data' is a dictionary.
    # We can now safely iterate over its items.
    typed_data: Dict[str, Any] = data #type:ignore
    errors: Dict[str, str] = {}
    
    for catalog_id, markup in typed_data.items():
        try:
            markup_value = float(markup) # The 'markup' variable is now known.
            if not catalog_manager.set_markup(catalog_id, markup_value):
                 errors[catalog_id] = "Failed to save in Google Sheet."
        except (ValueError, TypeError):
            errors[catalog_id] = f"Invalid markup value: {markup}"
        except Exception as e:
            errors[catalog_id] = str(e)

    if errors:
        return jsonify({"error": "Failed to save some markups", "details": errors}), 500

    return jsonify({"message": "Markups saved successfully."})

@app.route('/')
def home():
    status_message = "Checking authorization status..."
    is_authorized = False
    try:
        # Check if we have a valid token.
        if get_valid_access_token() is not None:
            is_authorized = True
            status_message = "Authorized"
        else:
            status_message = "Not Authorized"
            
    except Exception as e:
        status_message = f"Error checking auth status: {e}"

    return render_template(
        "index.html", 
        is_authorized=is_authorized,
        status_message=status_message
    )

@app.route('/authorize_jobber_start') # Renamed to avoid conflict with any module named authorize_jobber
def authorize_jobber_route():
    """Redirects the user to Jobber's authorization page."""
    auth_url = get_authorization_url() # This now generates and stores state via jobber_auth_flow
    # The state is stored in _oauth_state_store in jobber_auth_flow.py
    # For Flask, it's better to use Flask's session to store the state.
    # Let's modify get_authorization_url to return state, and store it here.
    # For now, assuming _oauth_state_store in jobber_auth_flow is sufficient for this simple case.
    print(f"Redirecting user to Jobber for authorization: {auth_url}")
    return redirect(auth_url)

@app.route('/jobber/callback') # Actual callback path
def jobber_callback_route():
    """
    Handles the callback from Jobber after user authorization.
    Exchanges the authorization code for tokens.
    """
    code = request.args.get('code')
    received_state = request.args.get('state')

    # Verify the state parameter to prevent CSRF.
    # The verify_state_parameter function is now in jobber_auth_flow.
    if not verify_state_parameter(received_state):
        print("OAuth state verification failed. Aborting authorization.")
        return redirect(url_for('home', message="Authorization failed: Invalid state. Please try again."))

    if not code:
        # As per Jobber docs, if user denies, they are redirected back with no additional params.
        print("User denied access or no authorization code provided by Jobber.")
        return redirect(url_for('home', message="Authorization failed: User denied access or no code received."))

    print(f"Received authorization code from Jobber: {code[:20]}...") 
    if exchange_code_for_token(code):
        print("Authorization successful. Tokens stored.")
        return redirect(url_for('home', message="Authorization successful! You can now start the worker if it's not running."))
    else:
        print("Failed to exchange code for tokens.")
        return redirect(url_for('home', message="Authorization failed: Could not exchange code for token. Check server logs."))

# ---------------------------------------------------------------------------
# Main Guard
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    # Default port for Flask
    flask_port = int(os.environ.get("FLASK_PORT", 5000))

    if len(sys.argv) > 1 and sys.argv[1].lower() == "web":
        if not os.environ.get("JOBBER_REDIRECT_URI"):
            print(f"Warning: JOBBER_REDIRECT_URI is not set. The OAuth callback may fail.")
            print(f"Defaulting to http://localhost:{flask_port}/jobber/callback for now. Please set it in your .env file.")
            os.environ["JOBBER_REDIRECT_URI"] = f"http://localhost:{flask_port}/jobber/callback"

        print(f"Starting Flask web server for Jobber OAuth handling on port {flask_port}.")
        print(f"Open your browser to http://localhost:{flask_port}{url_for('home')} to authorize.")
        app.run(debug=True, port=flask_port, use_reloader=False)
    else:
        print("Usage: python main.py [web|worker]")
        print(" web    : Starts the Flask web server for OAuth authorization.")
        print(" worker : Starts the polling worker (requires prior authorization via web).")
        print("\nStarting web server by default...")
        if not os.environ.get("JOBBER_REDIRECT_URI"):
            print(f"Warning: JOBBER_REDIRECT_URI is not set. The OAuth callback may fail.")
            print(f"Defaulting to http://localhost:{flask_port}/jobber/callback for now. Please set it in your .env file.")
            os.environ["JOBBER_REDIRECT_URI"] = f"http://localhost:{flask_port}/jobber/callback"
        app.run(debug=True, port=flask_port, use_reloader=False)
