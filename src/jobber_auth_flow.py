"""
Manages the Jobber OAuth 2.0 authorization code flow.
Includes functions to initiate authorization, handle callbacks, and refresh tokens.
"""
import requests
import time
import urllib.parse
import secrets # For generating a state token
from typing import Optional
from typing import Dict

from .jobber_config import (
    JOBBER_CLIENT_ID, JOBBER_CLIENT_SECRET, JOBBER_REDIRECT_URI,
    JOBBER_AUTHORIZATION_URL, JOBBER_TOKEN_URL
)
from .token_storage import save_tokens, load_tokens, clear_tokens, TokenData

_oauth_state_store: Optional[str] = None

def get_authorization_url() -> str:
    """
    Generates the Jobber authorization URL to redirect the user to.
    Includes a 'state' parameter for CSRF protection.
    """
    global _oauth_state_store
    # Generate a random string for the state parameter for CSRF protection.
    # This should be stored (e.g., in a session or temporary cache)
    # and verified when Jobber redirects back to the callback URL.
    _oauth_state_store = secrets.token_urlsafe(32)
    
    params: Dict[str, str] = {
        "client_id": JOBBER_CLIENT_ID,
        "redirect_uri": JOBBER_REDIRECT_URI,
        "response_type": "code",
        "state": _oauth_state_store
    }
    return f"{JOBBER_AUTHORIZATION_URL}?{urllib.parse.urlencode(params)}"

def verify_state_parameter(received_state: Optional[str]) -> bool:
    """Verifies the received state parameter against the stored one."""
    global _oauth_state_store
    if not _oauth_state_store or not received_state:
        print("State parameter missing for verification.")
        return False
    is_valid = secrets.compare_digest(_oauth_state_store, received_state)
    _oauth_state_store = None 
    if not is_valid:
        print("OAuth state parameter mismatch. Potential CSRF attack.")
    return is_valid

def exchange_code_for_token(code: str) -> bool:
    """
    Exchanges an authorization code for an access token and refresh token.
    Saves the tokens using token_storage.
    Returns True on success, False on failure.
    """
    token_payload: Dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": JOBBER_REDIRECT_URI, # Must match the URI used for the auth request
        "client_id": JOBBER_CLIENT_ID,
        "client_secret": JOBBER_CLIENT_SECRET,
    }
    try:
        response = requests.post(JOBBER_TOKEN_URL, data=token_payload, timeout=30)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        token_data = response.json()

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token") # Jobber only returns this if you've configured it to do so in the app settings on their website
        expires_in = token_data.get("expires_in")

        if not access_token:
            print("Error: No access_token in response from Jobber.")
            print(f"Response: {token_data}")
            return False

        expires_at = (time.time() + int(expires_in)) if expires_in else None
        
        save_tokens(access_token, refresh_token, expires_at)
        print("Successfully exchanged code for tokens.")
        return True
    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if e.response is not None:
            error_message += f" | Status: {e.response.status_code} | Response: {e.response.text}"
        print(f"Error exchanging code for token: {error_message}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during token exchange: {e}")
        return False


def refresh_access_token() -> Optional[str]:
    """
    Refreshes an expired access token using the stored refresh token.
    Saves the new tokens.
    Returns the new access token if successful, None otherwise.
    """
    stored_tokens_data: Optional[TokenData] = load_tokens()

    if not stored_tokens_data or not stored_tokens_data.refresh_token: 
        print("No refresh token available. Please re-authorize.")
        return None

    refresh_payload: Dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": stored_tokens_data.refresh_token,
        "client_id": JOBBER_CLIENT_ID,
        "client_secret": JOBBER_CLIENT_SECRET,
    }
    
    try:
        response = requests.post(JOBBER_TOKEN_URL, data=refresh_payload, timeout=30)
        response.raise_for_status()
        new_token_data = response.json()

        new_access_token = new_token_data.get("access_token")
        new_refresh_token = new_token_data.get("refresh_token") 

        # 1. Was a new access token received?
        if not new_access_token:
            print("Error: No new access_token in refresh response from Jobber.")
            print(f"Response: {new_token_data}")
            return None

        # 2. Was a new refresh token received?
        #    This assumes Refresh Token Rotation is ON for the app in Jobber's settings.
        if new_refresh_token is None:
            print("CRITICAL: Jobber refresh response did NOT contain a 'refresh_token' field. "
                "A new one is expected when Refresh Token Rotation is ON. "
                "The token refresh chain is broken.")
            print("Clearing all tokens to force re-authorization.")
            clear_tokens() # type: ignore
            return None
        
        # 3. Is the refresh token new?
        if new_refresh_token == stored_tokens_data.refresh_token: # type: ignore
            print(f"DEBUG: Jobber returned the SAME refresh token as the one used: {new_refresh_token[:10]}...") # type: ignore
        else:
            print(f"DEBUG: Jobber returned a NEW refresh token: {new_refresh_token[:10]}...") # type: ignore

        # 4. Process expiry information
        new_expires_in = new_token_data.get("expires_in")
        new_expires_at: Optional[float] = None
        if new_expires_in is not None:
            try:
                new_expires_at = time.time() + int(new_expires_in)
            except ValueError:
                print(f"Warning: Could not parse 'expires_in' value: {new_expires_in}. Token may not auto-expire based on this.")
        else:
            print("Warning: Jobber refresh response did not contain 'expires_in'.")

        # 5. Save new tokens
        save_tokens(new_access_token, new_refresh_token, new_expires_at) # type: ignore
        print("Access token refreshed successfully.")
        return new_access_token

    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if e.response is not None:
            error_message += f" | Status: {e.response.status_code} | Response: {e.response.text}"
            # it's invalid. Clear tokens to force re-authorization.
            if e.response.status_code in [400, 401]:
                print("Refresh token seems invalid or rejected by Jobber (e.g., HTTP 400/401). Clearing all tokens.")
                clear_tokens() # type: ignore
        print(f"Error refreshing access token: {error_message}")
        return None
    except json.JSONDecodeError as e: # type: ignore
        response_text = "'response' variable not available"
        if 'response' in locals() and hasattr(response, 'text'): # type: ignore
            response_text = response.text # type: ignore
        print(f"Error decoding JSON from Jobber token refresh response: {e}. Response text: {response_text}")
        return None
    except Exception as e: # Catch any other unexpected errors during the process
        print(f"An unexpected error occurred during token refresh: {e}")
        # For deeper debugging of unexpected errors:
        # import traceback
        # traceback.print_exc()
        return None


def get_valid_access_token() -> Optional[str]:
    """
    Retrieves a valid access token.
    If the token is expired or nearing expiry, it attempts to refresh it.
    If no token or refresh fails, returns None.
    """
    tokens_data: Optional[TokenData] = load_tokens()
    if not tokens_data or not tokens_data.access_token: # Access via attribute
        print("No tokens found. Please authorize the application first.")
        return None
    
    buffer_seconds = 300 
    if tokens_data.expires_at and tokens_data.expires_at < (time.time() + buffer_seconds):
        print("Access token expired or nearing expiry. Attempting refresh.")
        return refresh_access_token()
    
    return tokens_data.access_token