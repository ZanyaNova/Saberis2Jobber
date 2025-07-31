"""
Client for interacting with the Saberis API.
Handles session token fetching, caching, and automatic refreshing on expiry.
"""
import requests
from typing import Optional, List, Dict, Any

from .saberis_config import SABERIS_AUTH_TOKEN, SABERIS_BASE_URL
# We are importing the string-based token handlers now.
from .saberis_token_storage import save_token, load_token

class SaberisAuthenticationError(Exception):
    """Custom exception for Saberis authentication failures."""
    pass

class SaberisAPIClient:
    def __init__(self):
        self.base_url = SABERIS_BASE_URL
        # This is the long-lived token from the .env file used to get session tokens.
        self.permanent_auth_token = SABERIS_AUTH_TOKEN
        # This will hold the short-lived session token (a string), loaded from the Google Sheet.
        self._session_token: Optional[str] = load_token()

    def _fetch_new_session_token(self) -> str:
        """
        Fetches a new short-lived session token from the Saberis API using the permanent token.
        Saves the new token to the Google Sheet and returns it.
        """
        print("INFO: Fetching new Saberis session token...")
        token_url = f"{self.base_url}/api/v1/token"
        try:
            # The API expects a GET request with the permanent token as a query parameter.
            response = requests.get(token_url, params={"authToken": self.permanent_auth_token}, timeout=30)
            response.raise_for_status()
            
            # The response body is the raw session token string.
            token = response.text.strip('"')
            
            if not token:
                raise SaberisAuthenticationError("Received an empty session token from Saberis.")
            
            # save_token now correctly accepts a string.
            save_token(token)
            self._session_token = token
            print("INFO: Successfully fetched and saved new Saberis session token.")
            return self._session_token

        except requests.exceptions.RequestException as e:
            print(f"ERROR: Could not connect to Saberis to get a session token: {e}")
            # Raise the custom exception to be caught by the UI layer or calling function.
            raise SaberisAuthenticationError(f"Could not connect to Saberis to get a session token. Original error: {e}") from e

    def _get_valid_session_token(self) -> str:
        """
        Ensures a valid session token is available, fetching a new one if the cache is empty.
        """
        if self._session_token:
            return self._session_token
        return self._fetch_new_session_token()

    def _execute_request(self, endpoint: str, retry_on_401: bool = True) -> Any:
        """
        Executes a GET request to a Saberis API endpoint with proper auth and retry logic.
        """
        try:
            token = self._get_valid_session_token()
            url = f"{self.base_url}{endpoint}"
            headers = {"Authorization": f"Bearer {token}"}
            
            response = requests.get(url, headers=headers, timeout=30)
            
            # If the token was invalid (401), clear it, get a new one, and retry the request once.
            if response.status_code == 401 and retry_on_401:
                print("WARN: Saberis API returned 401. Session token may have expired. Refreshing...")
                self._session_token = None # Clear the expired token from the instance cache
                # _fetch_new_session_token will get a new token and save it.
                self._fetch_new_session_token()
                # Retry the request, but this time don't allow another retry to prevent infinite loops.
                return self._execute_request(endpoint, retry_on_401=False)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"ERROR: Saberis API request to '{endpoint}' failed: {e}")
            return None # Return None on network errors

    def get_unexported_documents(self) -> Optional[List[Dict[str, Any]]]:
        """Gets the list of available, unexported documents."""
        return self._execute_request("/api/v1/export")

    def get_export_document_by_id(self, doc_guid: str) -> Optional[Dict[str, Any]]:
        """Gets the full JSON document for a given document GUID."""
        return self._execute_request(f"/api/v1/export/json/{doc_guid}")
