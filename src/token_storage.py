import json
import time
import os
from typing import Optional, Dict, Any
from jobber_config import TOKEN_FILE_PATH

# In-memory cache to reduce file I/O, not strictly necessary for a single worker.
_token_cache: Optional[Dict[str, Any]] = None

def save_tokens(access_token: str, refresh_token: Optional[str], expires_at: Optional[float]) -> None:
    global _token_cache
    tokens: Dict[str, str | None | float] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "saved_at": time.time()
    }
    try:
        with open(TOKEN_FILE_PATH, 'w') as f:
            json.dump(tokens, f)
        _token_cache = tokens
        print(f"Tokens saved to {TOKEN_FILE_PATH}")
    except IOError as e:
        print(f"Error saving tokens to {TOKEN_FILE_PATH}: {e}")
        # Fallback or raise critical error depending on requirements
        _token_cache = None # Invalidate cache on error


def load_tokens() -> Optional[Dict[str, Any]]:
    global _token_cache
    if _token_cache:
        return _token_cache

    if not os.path.exists(TOKEN_FILE_PATH):
        print(f"Token file {TOKEN_FILE_PATH} not found.")
        return None
    try:
        with open(TOKEN_FILE_PATH, 'r') as f:
            tokens = json.load(f)
            _token_cache = tokens
            return tokens
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading tokens from {TOKEN_FILE_PATH}: {e}")
        _token_cache = None
        return None

def clear_tokens() -> None:
    """Removes the token file."""
    global _token_cache
    try:
        if os.path.exists(TOKEN_FILE_PATH):
            os.remove(TOKEN_FILE_PATH)
        _token_cache = None
        print(f"Tokens cleared from {TOKEN_FILE_PATH}")
    except IOError as e:
        print(f"Error clearing tokens from {TOKEN_FILE_PATH}: {e}")