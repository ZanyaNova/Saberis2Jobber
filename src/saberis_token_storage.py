"""
Manages storage for the Saberis API token.
"""
import json
import os
import time
from typing import Optional, TypedDict

from .saberis_config import SABERIS_TOKEN_FILE_PATH

# Define the shape of the token data for clarity and type safety
class SaberisTokenData(TypedDict):
    token: str
    expires_at: float

_token_cache: Optional[str] = None
_token_expiry: Optional[float] = None

def save_token(token: str, expires_in: int = 86400):
    """Saves the Saberis token and its expiry time to a file and caches it."""
    global _token_cache, _token_expiry
    
    expires_at = time.time() + expires_in
    # Use the TypedDict to create a well-defined dictionary
    token_data: SaberisTokenData = {"token": token, "expires_at": expires_at}

    try:
        with open(SABERIS_TOKEN_FILE_PATH, 'w') as f:
            json.dump(token_data, f)
        
        _token_cache = token
        _token_expiry = expires_at
        print("Saberis token saved successfully.")
    except IOError as e:
        print(f"Error saving Saberis token: {e}")

def load_token() -> Optional[str]:
    """Loads a valid Saberis token from cache or file."""
    global _token_cache, _token_expiry

    if _token_cache and _token_expiry and time.time() < _token_expiry:
        return _token_cache

    if not os.path.exists(SABERIS_TOKEN_FILE_PATH):
        return None

    try:
        with open(SABERIS_TOKEN_FILE_PATH, 'r') as f:
            # Cast the loaded data to our TypedDict
            token_data: SaberisTokenData = json.load(f)
        
        if time.time() < token_data.get("expires_at", 0):
            _token_cache = token_data["token"]
            _token_expiry = token_data["expires_at"]
            return _token_cache
        else:
            print("Saberis token has expired.")
            return None
            
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading Saberis token: {e}")
        return None