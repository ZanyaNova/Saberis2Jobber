import os
import json
from typing import Dict, Any, Optional

# The single, clear environment variable name we will use.
ENV_VAR_NAME = "JOBBER_API_TOKEN"

def load_token() -> Optional[Dict[str, Any]]:
    """
    Loads the Jobber token dictionary from the JOBBER_API_TOKEN environment variable.
    
    Returns:
        The token dictionary if the variable exists and is valid JSON, otherwise None.
    """
    token_str = os.getenv(ENV_VAR_NAME)
    if not token_str:
        print(f"Warning: {ENV_VAR_NAME} environment variable not found.")
        return None
    try:
        return json.loads(token_str)
    except json.JSONDecodeError:
        print(f"Error: Could not decode {ENV_VAR_NAME}. Ensure it is valid JSON.")
        return None

def save_token(token: Dict[str, Any]) -> None:
    """
    "Saves" the Jobber token in a stateless environment.
    
    This function's main purpose is to display the token dictionary as a JSON string
    so it can be manually copied and updated in the .env file or hosting provider's
    environment variables.
    """
    print("\n--- NEW/UPDATED JOBBER TOKEN ---")
    print("To persist this token, copy the following line into your .env file:")
    print(f"{ENV_VAR_NAME}='{json.dumps(token)}'")
    print("----------------------------------\n")

def clear_tokens() -> None:
    """
    "Clears" the tokens by instructing the user to remove the environment variable.
    In a stateless environment, we can't delete the variable, so we guide the user.
    """
    print("\n--- CLEAR JOBBER TOKEN ---")
    print(f"To clear the token, remove the {ENV_VAR_NAME} line from your .env file.")
    print("--------------------------\n")
