import json
import time
import os
from typing import Optional

from .jobber_config import TOKEN_FILE_PATH

from dataclasses import dataclass, field

@dataclass
class TokenData:
    access_token: str
    refresh_token: Optional[str] = None # Default value if not always present
    expires_at: Optional[float] = None  # Use float for timestamp
    saved_at: float = field(default_factory=time.time) # Auto-set on creation


_token_cache: Optional[TokenData] = None

def save_tokens(access_token: str, refresh_token: Optional[str], expires_at: Optional[float]) -> None:
    global _token_cache

    tokens_data = TokenData(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at
    )

    try:
        with open(TOKEN_FILE_PATH, 'w') as f:
            json.dump(vars(tokens_data), f)

        _token_cache = tokens_data
        print(f"Tokens saved to {TOKEN_FILE_PATH}")

    except IOError as e:
        print(f"Error saving tokens to {TOKEN_FILE_PATH}: {e}")
        _token_cache = None # Invalidate cache on error


def load_tokens() -> Optional[TokenData]:
    global _token_cache

    if _token_cache:
        # Optionally add a check here if the cached data is "stale"
        # e.g., based on saved_at and some cache duration, but for this simple case,
        # hitting the file might be desired more often in a multi-process environment.
        # Given the file-based storage is the bottleneck for concurrency anyway,
        # the cache provides limited benefit across processes.
        return _token_cache

    if not os.path.exists(TOKEN_FILE_PATH):
        print(f"Token file {TOKEN_FILE_PATH} not found.")
        return None

    try:
        with open(TOKEN_FILE_PATH, 'r') as f:
            token_dict = json.load(f)

        # Create a TokenData instance from the loaded dictionary
        # Handle potential missing keys gracefully if the file format could change
        tokens_data = TokenData(
            access_token=token_dict.get("access_token"),
            refresh_token=token_dict.get("refresh_token"),
            expires_at=token_dict.get("expires_at"),
            saved_at=token_dict.get("saved_at", time.time()) # Use default if saved_at wasn't in old file
        )

        if not tokens_data.access_token:
             print("Warning: Loaded token data is missing access_token.")
             return None

        _token_cache = tokens_data
        return tokens_data

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
        _token_cache = None # Clear cache
        print(f"Tokens cleared from {TOKEN_FILE_PATH}")
    except IOError as e:
        print(f"Error clearing tokens from {TOKEN_FILE_PATH}: {e}")