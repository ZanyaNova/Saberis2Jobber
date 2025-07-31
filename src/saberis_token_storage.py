import os
import json
from typing import Dict, Any

def load_token() -> Dict[str, Any] | None:
    """
    Loads the Saberis token from the SABERIS_TOKEN_JSON environment variable.
    """
    token_str = os.getenv("SABERIS_TOKEN_JSON")
    if not token_str:
        print("Warning: SABERIS_TOKEN_JSON environment variable not found.")
        return None
    try:
        return json.loads(token_str)
    except json.JSONDecodeError:
        print("Error: Could not decode SABERIS_TOKEN_JSON. Ensure it is valid JSON.")
        return None

def save_token(token: Dict[str, Any]) -> None:
    """
    In a stateless production environment, this function's main purpose is to
    display the token so it can be manually updated in the environment variables.
    """
    print("--- NEW SABERIS TOKEN ---")
    print("To update, copy the following line into your .env file or hosting provider's environment variables:")
    print(f"SABERIS_TOKEN_JSON='{json.dumps(token)}'")
    print("-------------------------")