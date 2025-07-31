import json
from typing import Dict, Any, Optional, cast
from .gsheet.gsheet_config import GSHEET_CONFIG_SHEET

# The key we will search for in the 'Key' column of our Config sheet.
KEY_NAME = "SABERIS_TOKEN_JSON"

def load_token() -> Optional[Dict[str, Any]]:
    """
    Loads the Saberis token dictionary from the Google Sheet.

    It searches the 'Config' sheet for a cell with the value of KEY_NAME,
    then reads the JSON string from the adjacent cell to the right.

    Returns:
        The token dictionary if found and valid, otherwise None.
    """
    print(f"INFO: Attempting to load '{KEY_NAME}' from Google Sheet...")
    try:
        # .find() returns a Cell object or None if not found.
        key_cell = GSHEET_CONFIG_SHEET.find(KEY_NAME, in_column=1) #type:ignore

        # Explicitly check for None. This is the correct way to handle "not found".
        if key_cell is None:
            print(f"INFO: Key '{KEY_NAME}' not found in the Config sheet.")
            return None

        # Get the value from the adjacent cell in the 'Value' column.
        token_str = GSHEET_CONFIG_SHEET.cell(key_cell.row, key_cell.col + 1).value
        
        if not token_str:
            print(f"INFO: Found key '{KEY_NAME}' but its value is empty.")
            return None

        # The value from the sheet is a string, so we need to parse it as JSON.
        return cast(Dict[str, Any], json.loads(token_str))

    except json.JSONDecodeError:
        print(f"ERROR: Could not decode the value for '{KEY_NAME}'. Ensure it is valid JSON in the sheet.")
        return None
    except Exception as e:
        # This will catch other potential gspread or network errors.
        print(f"ERROR: An unexpected error occurred while loading the token from the sheet: {e}")
        return None

def save_token(token: Dict[str, Any]) -> None:
    """
    Saves the Saberis token dictionary as a JSON string to the Google Sheet.

    If the key already exists, it updates the value. If not, it appends a new row.
    """
    print(f"INFO: Saving '{KEY_NAME}' to Google Sheet...")
    try:
        # Convert the token dictionary to a JSON string for storage.
        token_str = json.dumps(token)
        
        # Try to find the key first to see if we need to update or append.
        key_cell = GSHEET_CONFIG_SHEET.find(KEY_NAME, in_column=1) #type:ignore
        
        # If find() returns a Cell object, update the adjacent cell.
        if key_cell:
            GSHEET_CONFIG_SHEET.update_cell(key_cell.row, key_cell.col + 1, token_str)
            print(f"INFO: Successfully updated token for '{KEY_NAME}'.")
        # If find() returns None, the key wasn't found, so create it.
        else:
            print(f"INFO: Key '{KEY_NAME}' not found. Appending a new row.")
            GSHEET_CONFIG_SHEET.append_row([KEY_NAME, token_str])
            print(f"INFO: Successfully created and saved token for '{KEY_NAME}'.")

    except Exception as e:
        print(f"ERROR: An unexpected error occurred while saving the token to the sheet: {e}")
