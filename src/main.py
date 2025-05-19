import time
import os
import json 
import pathlib 

from flask import Flask, request, redirect, url_for 

# Auth and Config
from jobber_config import load_dotenv 
from jobber_auth_flow import get_authorization_url, exchange_code_for_token, get_valid_access_token, verify_state_parameter

# Jobber Business Logic
from jobber_models import SaberisOrder, saberis_to_jobber 
from jobber_client_module import JobberClient 

load_dotenv() 

# Flask App Initialization
app = Flask(__name__)
# Secret key is needed for session management (to store OAuth state)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))


# ---------------------------------------------------------------------------
# Flask Web Routes for OAuth
# ---------------------------------------------------------------------------
@app.route('/')
def home():
    status_message = "Checking authorization status..."
    try:
        is_authorized = get_valid_access_token() is not None
        status_message = "Authorized" if is_authorized else "Not Authorized (or token refresh failed)"
    except Exception as e:
        status_message = f"Error checking auth status: {e}"

    auth_url_val = url_for('authorize_jobber_route') # Renamed route function
    callback_url_val = url_for('jobber_callback_route', _external=True) # Renamed route function
    
    message = request.args.get('message', '') # For displaying success/error messages

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Jobber Integration Service</title>
        <style>
            body {{ font-family: sans-serif; margin: 20px; line-height: 1.6; }}
            h1 {{ color: #333; }}
            p {{ color: #555; }}
            code {{ background-color: #f4f4f4; padding: 2px 6px; border-radius: 4px; }}
            .button {{ display: inline-block; padding: 10px 15px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
            .button:hover {{ background-color: #0056b3; }}
            .message {{ padding: 10px; margin-bottom: 15px; border-radius: 4px; }}
            .success {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .error {{ background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        </style>
    </head>
    <body>
        <h1>Jobber Integration Service</h1>
        {f'<div class="message success">{message}</div>' if message and "successful" in message.lower() else ''}
        {f'<div class="message error">{message}</div>' if message and "failed" in message.lower() else ''}
        <p><strong>Status:</strong> {status_message}</p>
        <p><a href="{auth_url_val}" class="button">Authorize with Jobber</a></p>
        <p>Ensure your Jobber App Redirect URI is set to: <code>{callback_url_val}</code></p>
        <p>If you've authorized and the worker isn't running, you might need to start it separately using <code>python main.py worker</code>.</p>
    </body>
    </html>
    """

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
# Polling Worker Logic 
# ---------------------------------------------------------------------------
POLL_SECONDS = 30 

def poll_once(jobber_client: JobberClient) -> None:
    """One poll cycle – fetch Saberis docs, process, create Jobber items."""
    print(f"\n--- Starting poll cycle at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    BASE_DIR = pathlib.Path(__file__).resolve().parent
    DOC_DIR  = BASE_DIR / "example_docs" 

    if not DOC_DIR.is_dir():
        print(f"Warning: Example documents directory not found at {DOC_DIR}")
        print("Please create it and add sample JSON files (e.g., order1.json) to test the polling worker.")
        return

    sample_files = list(DOC_DIR.glob("*.json"))
    if not sample_files:
        print(f"No sample JSON files found in {DOC_DIR}. Skipping Saberis processing for this cycle.")
        return

    for path_obj in sample_files:
        path_str = str(path_obj)
        print(f"Processing Saberis document: {path_str}")
        try:
            doc_content = path_obj.read_text()
            if not doc_content.strip():
                print(f"Warning: File {path_str} is empty. Skipping.")
                continue
            doc = json.loads(doc_content)
            order = SaberisOrder.from_json(doc)

            client_id, property_id = jobber_client.create_client_and_property(order)
            quote_payload = saberis_to_jobber(order, client_id, property_id)
            quote_id = jobber_client.create_and_send_quote(quote_payload)
            print(f"Successfully created & sent quote {quote_id} for Saberis order {order.unique_key()}")

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from {path_str}: {e}")
        except ConnectionRefusedError as e: 
            print(f"Jobber API connection/authorization error: {e}. Worker will pause. Please check authorization status via web UI.")
            # This indicates a token issue (e.g. invalid, expired and couldn't refresh).
            # The worker should pause and wait for re-authorization.
            return # Stop this poll cycle; it will be restarted by start_worker after a delay.
        except RuntimeError as e: 
            print(f"Runtime error processing order from {path_str} with Jobber: {e}")
        except Exception as e:
            print(f"An unexpected error occurred processing {path_str}: {e}")
            # Consider logging traceback for unexpected errors:
            # import traceback
            # traceback.print_exc()
    print(f"--- Poll cycle finished at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")


def start_worker():
    """Initializes JobberClient and starts the polling loop."""
    print("Initializing Jobber Client for worker...")
    
    jobber_service_client = JobberClient()

    print("Starting Saberis -> Jobber worker. Press Ctrl-C to exit.")
    try:
        while True:
            # get_valid_access_token will attempt to load/refresh.
            # If it returns None, auth is not established or refresh failed.
            current_token = get_valid_access_token() 
            if not current_token:
                print("Jobber authorization lost or not established. Worker pausing.")
                print(f"Please visit http://localhost:{os.environ.get('FLASK_PORT', 5000)}{url_for('authorize_jobber_route')} to authorize.")
                # Wait longer before retrying if auth is lost/unavailable
                time.sleep(POLL_SECONDS * 2) # e.g., 60 seconds
                continue # Skip poll_once and re-check token in the next loop iteration

            # Update the client's token in case it was refreshed.
            # This ensures the JobberClient instance uses the latest token.
            jobber_service_client.access_token = current_token
            
            poll_once(jobber_service_client)
            print(f"Waiting {POLL_SECONDS} seconds for next poll cycle...")
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\nWorker stopped by user.")
    except Exception as e:
        print(f"Critical error in worker loop: {e}")
        # import traceback
        # traceback.print_exc()
    finally:
        print("Worker has shut down.")

# ---------------------------------------------------------------------------
# Main Guard
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    # Default port for Flask
    flask_port = int(os.environ.get("FLASK_PORT", 5000))

    if len(sys.argv) > 1 and sys.argv[1].lower() == "worker":
        start_worker()
    elif len(sys.argv) > 1 and sys.argv[1].lower() == "web":
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