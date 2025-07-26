import os
import json
from flask import Flask, request, redirect, url_for, render_template, jsonify, Response
from .gsheet.catalog_manager import catalog_manager
from dataclasses import asdict
from .saberis_ingestion import ingest_saberis_exports, SaberisExportRecord

# Auth and Config
from .jobber_auth_flow import get_authorization_url, exchange_code_for_token, get_valid_access_token, verify_state_parameter
from .jobber_client_module import (
    JobberClient, QuoteNodeGQL, JobNodeGQL, QuoteLineEditItemGQL, 
    QuoteEditLineItemInputGQL, JobCreateLineItemGQL, JobEditLineItemGQL,
    JobLineItemNodeGQL
)
from .jobber_models import get_line_items_from_export, SaberisOrder, QuoteLineItemGQL
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

class JobberItemForUI(TypedDict):
    id: str
    type: str
    number: str
    client_name: str
    shipping_address: str
    total: str
    status: str

# ---------------------------------------------------------------------------
# Data Transformation
# ---------------------------------------------------------------------------

def _transform_items_for_ui(item: Union[QuoteNodeGQL, JobNodeGQL], item_type: str) -> JobberItemForUI:
    """Transforms a Jobber Quote or Job into a simple dict for the UI."""
    shipping_address = "Address not available"
    property_data = item.get("property")
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

    # Handle different total fields between quotes and jobs
    if item_type == 'Quote':
        total = item.get("amounts", {}).get("total", 0.0)
    else: # It's a Job
        total = item.get("total", 0.0)
    
    # Get the display number (quoteNumber or jobNumber)
    number = item.get("quoteNumber") if item_type == 'Quote' else item.get("jobNumber")

    return {
        "id": item["id"],
        "type": item_type,
        "number": f"#{number}",
        "client_name": item["client"]["name"],
        "shipping_address": shipping_address,
        "total": f"${total:,.2f}",
        "status": item.get("jobStatus", "N/A") if item_type == 'Job' else item.get("transitionedAt", "").split('T')[0]
    }



# ---------------------------------------------------------------------------
# Flask Web Routes
# ---------------------------------------------------------------------------
# In main.py

@app.route('/api/jobber-items')
def get_jobber_items():
    """
    API endpoint to serve a COMPLETE list of Jobber jobs and, optionally, approved quotes.
    This function now handles pagination from the Jobber API internally.
    """
    if get_valid_access_token() is None:
        return jsonify({"error": "Not authorized with Jobber"}), 401

    jobber_client = JobberClient()
    include_quotes = request.args.get('include_quotes', 'false').lower() == 'true'
    
    all_items: List[JobberItemForUI] = []

    try:
        # --- Fetch all active jobs ---
        job_cursor: Optional[str] = None
        while True:
            job_page = jobber_client.get_jobs(cursor=job_cursor)
            transformed_jobs = [_transform_items_for_ui(job, 'Job') for job in job_page["jobs"]]
            all_items.extend(transformed_jobs)
            if not job_page.get("has_next_page"):
                break
            job_cursor = job_page.get("next_cursor")

        # --- Optionally fetch all approved quotes ---
        if include_quotes:
            quote_cursor: Optional[str] = None
            while True:
                quote_page = jobber_client.get_approved_quotes(cursor=quote_cursor)
                transformed_quotes = [_transform_items_for_ui(quote, 'Quote') for quote in quote_page["quotes"]]
                all_items.extend(transformed_quotes)
                if not quote_page.get("has_next_page"):
                    break
                quote_cursor = quote_page.get("next_cursor")

        # Sort the final combined list
        all_items.sort(key=lambda x: (x['client_name'], x['type']))
        
        # The response is now a single object with the complete list
        return jsonify({"items": all_items})

    except ConnectionRefusedError as e:
        print(f"AUTH_ERROR in endpoint: {e}")
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        print(f"ERROR: Could not fetch Jobber items: {e}")
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
    API endpoint to add/update items on a Jobber Quote or Job from Saberis exports.
    This function now dynamically handles both item types with proper type safety.
    """
    if get_valid_access_token() is None:
        return jsonify({"error": "Not authorized with Jobber"}), 401

    data = request.get_json()
    item_id = data.get('itemId')
    item_type = data.get('itemType')
    exports_payload = data.get('exports')

    if not item_id or not item_type or not exports_payload:
        return jsonify({"error": "Missing itemId, itemType, or exports data"}), 400

    jobber_client = JobberClient()
    saberis_export_records = ingest_saberis_exports()
    manifest = {item['saberis_id']: item for item in saberis_export_records}

    # --- Step 1: Generate all desired line items ---
    all_desired_line_items: List[QuoteLineEditItemGQL] = []
    for export_data in exports_payload:
        saberis_id, quantity = export_data.get('saberis_id'), export_data.get('quantity')
        if saberis_id and quantity and saberis_id in manifest:
            stored_path = manifest[saberis_id]['stored_path']
            line_items = get_line_items_from_export(stored_path, quantity)
            all_desired_line_items.extend(line_items)

    if not all_desired_line_items:
        return jsonify({"error": "No valid line items could be generated"}), 400

    # --- Step 2: Fetch existing line items and create a lookup map ---
    existing_items_map: Dict[str, Union[QuoteLineItemGQL, JobLineItemNodeGQL]] = {}
    if item_type == 'Quote':
        quote_details = jobber_client.get_quote_with_line_items(item_id)
        if quote_details:
            nodes = quote_details.get("lineItems", {}).get("nodes", [])
            existing_items_map = {
                item['name']: item for item in nodes if 'name' in item
            }
    elif item_type == 'Job':
        job_details = jobber_client.get_job_with_line_items(item_id)
        if job_details:
            nodes = job_details.get("lineItems", {}).get("nodes", [])
            existing_items_map = {
                item['name']: item for item in nodes if 'name' in item
            }
    else:
        return jsonify({"error": f"Unsupported itemType: {item_type}"}), 400

    # --- Step 3: Compare and categorize into 'add' vs 'update' lists ---
    # Explicitly type the lists to resolve the "Unknown" type errors
    items_to_add: List[Union[QuoteLineEditItemGQL, JobCreateLineItemGQL]] = []
    items_to_update: List[Union[QuoteEditLineItemInputGQL, JobEditLineItemGQL]] = []

    for desired_item in all_desired_line_items:
        desired_name = desired_item['name']
        existing_item = existing_items_map.get(desired_name)

        if existing_item:
            # Safely get the ID, as it's required for an update
            existing_item_id = existing_item.get('id')
            if existing_item_id and existing_item.get('quantity') != desired_item.get('quantity'):
                items_to_update.append({
                    "lineItemId": existing_item_id,
                    "quantity": desired_item['quantity']
                })
        else:
            items_to_add.append(desired_item)

    # --- Step 4: Execute API Calls based on type ---
    update_success, add_success = True, True
    update_message, add_message = "No items to update.", "No items to add."

    if item_type == 'Quote':
        if items_to_update:
            # Cast to the specific list type expected by the function
            quote_updates = cast(List[QuoteEditLineItemInputGQL], items_to_update)
            update_success, update_message = jobber_client.update_line_items_on_quote(item_id, quote_updates)
        if items_to_add:
            quote_additions = cast(List[QuoteLineEditItemGQL], items_to_add)
            add_success, add_message = jobber_client.add_line_items_to_quote(item_id, quote_additions)
    elif item_type == 'Job':
        if items_to_update:
            job_updates = cast(List[JobEditLineItemGQL], items_to_update)
            update_success, update_message = jobber_client.update_line_items_on_job(item_id, job_updates)
        if items_to_add:
            job_additions = cast(List[JobCreateLineItemGQL], items_to_add)
            add_success, add_message = jobber_client.add_line_items_to_job(item_id, job_additions)

    # --- Step 5: Report Combined Results ---
    error_messages: list[str] = []
    if not update_success:
        error_messages.append(f"Update failed: {update_message}") 
    if not add_success:
        error_messages.append(f"Add failed: {add_message}")

    if error_messages:
        return jsonify({"error": " | ".join(error_messages)}), 500

    success_message = f"Successfully processed items for {item_type} ID {item_id}. Added: {len(items_to_add)}, Updated: {len(items_to_update)}."
    return jsonify({"message": success_message})

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
