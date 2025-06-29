import os

from flask import Flask, request, redirect, url_for, render_template, jsonify

from .saberis_ingestion import ingest_saberis_exports

# Auth and Config
from .jobber_auth_flow import get_authorization_url, exchange_code_for_token, get_valid_access_token, verify_state_parameter
from .jobber_client_module import JobberClient, QuoteNodeGQL, QuoteLineEditItemGQL
from .jobber_models import get_line_items_from_export
from typing import Dict, Any, TypedDict, List

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
    API endpoint to run the ingestion logic and return the manifest.
    This simulates refreshing the list of available exports.
    """
    # This function already scans a folder and returns the manifest list
    # See: src/saberis_ingestion.py
    manifest_records = ingest_saberis_exports()
    return jsonify(manifest_records)

@app.route('/api/send-to-jobber', methods=['POST'])
def send_to_jobber():
    """
    API endpoint to receive selected Saberis exports and add them as
    line items to a specified Jobber quote.
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

    all_line_items: List[QuoteLineEditItemGQL] = []

    for export_data in exports_payload:
        saberis_id = export_data.get('saberis_id')
        quantity = export_data.get('quantity')
        
        if saberis_id and quantity and saberis_id in manifest:
            stored_path = manifest[saberis_id]['stored_path']
            line_items = get_line_items_from_export(stored_path, quantity)
            all_line_items.extend(line_items)

    if not all_line_items:
        return jsonify({"error": "No valid line items could be generated from the selected exports"}), 400

    success, message = jobber_client.add_line_items_to_quote(quote_id, all_line_items)

    if success:
        return jsonify({"message": message})
    else:
        return jsonify({"error": message}), 500

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
