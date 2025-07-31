"""
Client for interacting with the Saberis API.
"""
import requests
from typing import Optional, List, Dict, Any

from .saberis_config import SABERIS_AUTH_TOKEN, SABERIS_BASE_URL
from .saberis_token_storage import save_token, load_token

class SaberisAuthenticationError(Exception):
    """Custom exception for Saberis authentication failures."""
    pass

class SaberisAPIClient:
    def __init__(self):
        self.base_url = SABERIS_BASE_URL
        self.auth_token_param = SABERIS_AUTH_TOKEN
        self._token: Optional[str] = load_token()

    def _get_auth_token(self) -> Optional[str]:
        """Retrieves a new auth token from the Saberis API."""
        if self._token:
            return self._token
            
        token_url = f"{self.base_url}/api/v1/token"
        try:
            # The API expects a GET request with the token as a query parameter
            response = requests.get(token_url, params={"authToken": self.auth_token_param}, timeout=30)
            response.raise_for_status()
            
            # The response body is a raw string, not JSON
            token = response.text.strip('"')
            
            if token:
                save_token(token)
                self._token = token
                return self._token
            # If no token is returned, raise an error
            raise SaberisAuthenticationError("Received an empty token from Saberis.")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Saberis auth token: {e}")
            # Raise the custom exception to be caught by the UI layer
            raise SaberisAuthenticationError(f"Could not connect to Saberis to get an authentication token. Please check the `SABERIS_AUTH_TOKEN` in your .env file and ensure the Saberis service is available. Original error: {e}") from e
    
    def get_unexported_documents(self) -> Optional[List[Dict[str, Any]]]:
        """Gets the list of available, unexported documents."""
        token = self._get_auth_token()
        if not token:
            return None

        exports_url = f"{self.base_url}/api/v1/export"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.get(exports_url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching unexported documents from Saberis: {e}")
            return None

    def get_export_document_by_id(self, doc_guid: str) -> Optional[Dict[str, Any]]:
        """Gets the full JSON document for a given document GUID."""
        token = self._get_auth_token()
        if not token:
            return None

        document_url = f"{self.base_url}/api/v1/export/json/{doc_guid}"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            response = requests.get(document_url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching document '{doc_guid}' from Saberis: {e}")
            return None