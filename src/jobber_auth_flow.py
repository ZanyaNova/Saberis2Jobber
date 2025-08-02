"""
Manages the Jobber OAuth 2.0 authorization code flow.
Includes functions to initiate authorization, handle callbacks, and refresh tokens.
NOW REFACTORED for a stateless environment.
"""
import requests
import time
import urllib.parse
import secrets
from typing import Optional, Dict

from .jobber_config import (
    JOBBER_CLIENT_ID, JOBBER_CLIENT_SECRET, JOBBER_REDIRECT_URI,
    JOBBER_AUTHORIZATION_URL, JOBBER_TOKEN_URL
)
# Use the simple, stateless token storage functions
from .token_storage import save_token as save_jobber_token_to_env, load_token as load_jobber_token_from_env

_oauth_state_store: Optional[str] = None

def get_authorization_url() -> str:
    """
    Generates the Jobber authorization URL to redirect the user to.
    """
    global _oauth_state_store
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
        return False
    is_valid = secrets.compare_digest(_oauth_state_store, received_state)
    _oauth_state_store = None
    return is_valid

def exchange_code_for_token(code: str) -> bool:
    """
    Exchanges an authorization code for an access token and refresh token.
    Saves the tokens by printing them to the console for env var update.
    """
    token_payload: Dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": JOBBER_REDIRECT_URI,
        "client_id": JOBBER_CLIENT_ID,
        "client_secret": JOBBER_CLIENT_SECRET,
    }
    try:
        response = requests.post(JOBBER_TOKEN_URL, data=token_payload, timeout=30)
        # ---vvv- DEBUGGING: ADD THESE LINES -vvv---
        print(f"DEBUG: Jobber token exchange response status: {response.status_code}")
        print(f"DEBUG: Jobber token exchange response text: {response.text}")
        # ---^^^- END OF ADDED LINES -^^^---
        
        response.raise_for_status()
        token_data = response.json()

        if "access_token" not in token_data:
            print(f"Error: No access_token in response from Jobber. Response: {token_data}")
            return False

        # Add expires_at to the token data before saving
        if "expires_in" in token_data:
            token_data["expires_at"] = time.time() + int(token_data["expires_in"])

        save_jobber_token_to_env(token_data)
        print("Successfully exchanged code for tokens.")
        return True
    except requests.exceptions.RequestException as e:
        error_message = str(e)
        if e.response is not None:
            error_message += f" | Status: {e.response.status_code} | Response: {e.response.text}"
        print(f"Error exchanging code for token: {error_message}")
        return False

def refresh_access_token() -> Optional[str]:
    """
    Refreshes an expired access token using the stored refresh token.
    Saves the new tokens and returns the new access token.
    """
    stored_tokens = load_jobber_token_from_env()
    if not stored_tokens or not stored_tokens.get("refresh_token"):
        print("No refresh token available. Please re-authorize.")
        return None

    refresh_payload: Dict[str, str] = {
        "grant_type": "refresh_token",
        "refresh_token": stored_tokens["refresh_token"],
        "client_id": JOBBER_CLIENT_ID,
        "client_secret": JOBBER_CLIENT_SECRET,
    }
    try:
        response = requests.post(JOBBER_TOKEN_URL, data=refresh_payload, timeout=30)
        response.raise_for_status()
        new_token_data = response.json()

        new_access_token = new_token_data.get("access_token")
        if not new_access_token:
            print(f"Error: No new access_token in refresh response. Response: {new_token_data}")
            return None

        # Add expires_at to the new token data before saving
        if "expires_in" in new_token_data:
            new_token_data["expires_at"] = time.time() + int(new_token_data["expires_in"])
        
        # The new response may not include a new refresh token if rotation is off.
        # Preserve the old one if a new one isn't provided.
        if "refresh_token" not in new_token_data:
            new_token_data["refresh_token"] = stored_tokens["refresh_token"]

        save_jobber_token_to_env(new_token_data)
        print("Access token refreshed successfully.")
        return new_access_token
    except requests.exceptions.RequestException as e:
        if e.response is not None and e.response.status_code in [400, 401]:
            print("Refresh token seems invalid. Clearing tokens by saving an empty dict.")
            save_jobber_token_to_env({}) # "Clear" tokens
        print(f"Error refreshing access token: {e}")
        return None

def get_valid_access_token() -> Optional[str]:
    """
    Retrieves a valid access token, refreshing it if necessary.
    """
    tokens_data = load_jobber_token_from_env()
    if not tokens_data or not tokens_data.get("access_token"):
        print("No Jobber tokens found. Please authorize the application.")
        return None

    expires_at = tokens_data.get("expires_at")
    buffer_seconds = 300
    if expires_at and expires_at < (time.time() + buffer_seconds):
        print("Jobber access token expired or nearing expiry. Attempting refresh.")
        return refresh_access_token()

    return tokens_data.get("access_token")