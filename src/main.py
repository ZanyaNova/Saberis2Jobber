import os
import json
import re
from flask import Flask, request, redirect, url_for, render_template, jsonify, Response
from .gsheet.catalog_manager import catalog_manager
from dataclasses import asdict
from .saberis_ingestion import ingest_saberis_exports, SaberisExportRecord

# Auth and Config
from .jobber_auth_flow import get_authorization_url, exchange_code_for_token, get_valid_access_token, verify_state_parameter
from .jobber_client_module import JobberClient, QuoteNodeGQL, QuoteLineEditItemGQL, QuoteEditLineItemInputGQL
from .jobber_models import get_line_items_from_export, SaberisOrder
from typing import Dict, Any, TypedDict, List, Union, Tuple, Optional, cast

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

@app.route('/api/saberis-exports/prune', methods=['POST'])
def prune_saberis_exports_route():
    """
    API endpoint to prune old Saberis exports, keeping only the most recent ones.
    """
    from .saberis_ingestion import prune_saberis_exports
    try:
        pruned_count = prune_saberis_exports(keep_count=3)
        return jsonify({"message": f"Successfully deleted {pruned_count} old export(s)."})
    except Exception as e:
        print(f"ERROR: Could not prune Saberis exports: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/send-to-jobber', methods=['POST'])
def send_to_jobber():
    """
    API endpoint to add/update items on a Jobber quote from Saberis exports.
    This function now performs a multi-step, robust update:
    1.  Fetches all existing master "Products and Services" to create an S2J hash lookup map.
    2.  Fetches all line items currently on the target Jobber Quote.
    3.  Generates all desired line items from the selected Saberis exports.
    4.  Categorizes the desired items:
        - If an item already exists on the quote -> Add to an 'update' list.
        - If an item is new to the quote -> Add to an 'add' list.
    5.  For items being added, it uses the S2J map to decide whether to link to an
        existing product or create a new one.
    6.  Executes the 'update' and 'add' API calls separately and reports the combined result.
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

    # --- Step 1: Fetch master product list for S2J hash mapping ---
    existing_products = jobber_client.get_all_products_and_services()
    s2j_hash_to_id_map: Dict[str, str] = {}
    s2j_hash_pattern: re.Pattern[str] = re.compile(r"S2J\((\w{6})\)")

    for product in existing_products:
        match: Optional[re.Match[str]] = s2j_hash_pattern.search(product['name'])
        if match:
            s2j_hash: str = match.group(1)
            s2j_hash_to_id_map[s2j_hash] = product['id']
    print(f"INFO: Created S2J product lookup map with {len(s2j_hash_to_id_map)} items.")

    # --- Step 2: Generate all line items that SHOULD be on the quote ---
    all_desired_line_items: List[QuoteLineEditItemGQL] = []
    for export_data in exports_payload:
        saberis_id, quantity = export_data.get('saberis_id'), export_data.get('quantity')
        if saberis_id and quantity and saberis_id in manifest:
            stored_path = manifest[saberis_id]['stored_path']
            line_items = get_line_items_from_export(stored_path, quantity)
            all_desired_line_items.extend(line_items)

    if not all_desired_line_items:
        return jsonify({"error": "No valid line items could be generated"}), 400

    # --- Step 3: Fetch the quote's CURRENT line items ---
    quote_details = jobber_client.get_quote_with_line_items(quote_id)
    if not quote_details:
        return jsonify({"error": "Could not fetch existing quote details from Jobber."}), 500
    existing_line_items_nodes = quote_details.get("lineItems", {}).get("nodes", [])
    existing_items_map = {item['name']: item for item in existing_line_items_nodes}

    # --- Step 4: Compare and categorize into 'add' vs 'update' lists ---
    items_to_add: List[QuoteLineEditItemGQL] = []
    items_to_update: List[QuoteEditLineItemInputGQL] = []

    for desired_item in all_desired_line_items:
        desired_name = desired_item['name']
        if desired_name in existing_items_map:
            # This item already exists on the quote, check if quantity differs.
            existing_item = existing_items_map[desired_name]
            if existing_item.get('quantity') != desired_item.get('quantity'):
                items_to_update.append({
                    "lineItemId": existing_item['id'],
                    "quantity": desired_item['quantity']
                })
        else:
            # This is a new item for this quote. Now we apply the S2J logic.
            final_item_to_add = desired_item.copy()
            match = s2j_hash_pattern.search(final_item_to_add['name'])
            if match:
                s2j_hash = match.group(1)
                existing_product_id = s2j_hash_to_id_map.get(s2j_hash)
                if existing_product_id:
                    # Link to the existing master product
                    final_item_to_add['productOrServiceId'] = existing_product_id
                    final_item_to_add['saveToProductsAndServices'] = False
                else:
                    # No master product found, so create a new one
                    final_item_to_add['saveToProductsAndServices'] = True
            else:
                final_item_to_add['saveToProductsAndServices'] = True
            
            items_to_add.append(final_item_to_add)

    # --- Step 5: Execute API Calls ---
    update_success, update_message = jobber_client.update_line_items_on_quote(quote_id, items_to_update)
    add_success, add_message = jobber_client.add_line_items_to_quote(quote_id, items_to_add)

    # --- Step 6: Report Combined Results ---
    error_messages: list[str] = []
    if not update_success:
        error_messages.append(f"Update failed: {update_message}")
    if not add_success:
        error_messages.append(f"Add failed: {add_message}")

    if error_messages:
        return jsonify({"error": " | ".join(error_messages)}), 500

    # --- Build the definitive, informative success message ---
    num_updated = len(items_to_update)
    num_added_to_quote = len(items_to_add)
    
    # This is our new counter
    num_new_products_created = sum(1 for item in items_to_add if item.get('saveToProductsAndServices'))

    success_parts: list[str] = []

    if num_updated > 0:
        plural = "s" if num_updated > 1 else ""
        success_parts.append(f"updated {num_updated} item{plural} on the quote")
    
    if num_added_to_quote > 0:
        plural = "s" if num_added_to_quote > 1 else ""
        success_parts.append(f"added {num_added_to_quote} new line item{plural}")

    # Add the new product count to the message, only if it's relevant
    if num_new_products_created > 0:
        plural = "s" if num_new_products_created > 1 else ""
        success_parts.append(f"creating {num_new_products_created} new product{plural} in your library")

    if not success_parts:
        return jsonify({"message": "Success: No changes were needed for the quote."})

    # Join the parts with commas and a final 'and' for readability
    if len(success_parts) > 1:
        final_message = f"Success: Successfully {', '.join(success_parts[:-1])} and {success_parts[-1]}."
    else:
        final_message = f"Success: Successfully {success_parts[0]}."
        
    return jsonify({"message": final_message})

@app.route('/api/catalog-item/<string:catalog_id>', methods=['GET'])
def get_catalog_item(catalog_id: str) -> Union[Response, Tuple[Response, int]]:
    """
    API endpoint to get all data for a specific catalog item.
    """
    try:
        item = catalog_manager.get_catalog_item(catalog_id)
        if item:
            # asdict converts the CatalogItem object to a dictionary
            return jsonify(asdict(item))
        else:
            # If not found, return a 404
            return jsonify({"error": "Item not found", "catalog_id": catalog_id}), 404

    except Exception as e:
        print(f"ERROR: Could not fetch item for {catalog_id}: {e}")
        return jsonify({"error": "An internal error occurred"}), 500

@app.route('/api/catalog-items', methods=['POST'])
def save_catalog_items() -> Union[Response, Tuple[Response, int]]:
    """
    API endpoint to save pricing factors for multiple catalog items.
    Returns the updated state of the successfully saved items.
    """
    data: Any = request.get_json()
    
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid payload format. Expected a JSON object."}), 400

    # This is the key: We cast 'data' to its specific, expected structure.
    # This tells the linter that keys are strings and values are dictionaries
    # containing strings and numbers.
    typed_data = cast(Dict[str, Dict[str, Union[int, float]]], data)

    errors: Dict[str, str] = {}
    saved_items: List[Dict[str, Any]] = []

    # The linter now knows the types of 'catalog_id' and 'values' here.
    for catalog_id, values in typed_data.items():
        try:
            # We still need runtime checks because cast does nothing at runtime.
            multiplier = float(values['multiplier'])
            margin = float(values['margin'])
            
            success = catalog_manager.set_pricing_factors(catalog_id, multiplier, margin)

            if success:
                updated_item = catalog_manager.get_catalog_item(catalog_id)
                saved_items.append(asdict(updated_item))
            else:
                errors[catalog_id] = "Failed to save in Google Sheet."

        except (KeyError, TypeError, ValueError):
            # A combined block to catch malformed 'values' objects or non-numeric data.
            errors[catalog_id] = f"Invalid data format or value for item: {values}"
        except Exception as e:
            errors[catalog_id] = str(e)

    if errors:
        return jsonify({
            "error": "Failed to save some items", 
            "details": errors
        }), 500

    return jsonify({
        "message": "Items saved successfully.",
        "saved_items": saved_items
    })

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
