# src/saberis_token_storage.py
from typing import Optional
from .gsheet.gsheet_config import GSHEET_CONFIG_SHEET

KEY_NAME = "SABERIS_SESSION_TOKEN" # Renamed for clarity

def load_token() -> Optional[str]:
    """
    Loads the raw Saberis session token string from the Google Sheet.
    """
    print(f"INFO: Attempting to load '{KEY_NAME}' from Google Sheet...")
    try:
        key_cell = GSHEET_CONFIG_SHEET.find(KEY_NAME, in_column=1) #type:ignore
        if key_cell is None:
            return None
        
        # Return the raw string value from the adjacent cell
        token_str = GSHEET_CONFIG_SHEET.cell(key_cell.row, key_cell.col + 1).value
        return token_str if token_str else None

    except Exception as e:
        print(f"ERROR: An unexpected error occurred while loading the token: {e}")
        return None

def save_token(token: str) -> None:
    """
    Saves the raw Saberis session token string to the Google Sheet.
    """
    print(f"INFO: Saving '{KEY_NAME}' to Google Sheet...")
    try:
        key_cell = GSHEET_CONFIG_SHEET.find(KEY_NAME, in_column=1) #type:ignore
        
        if key_cell:
            GSHEET_CONFIG_SHEET.update_cell(key_cell.row, key_cell.col + 1, token)
            print(f"INFO: Successfully updated token for '{KEY_NAME}'.")
        else:
            GSHEET_CONFIG_SHEET.append_row([KEY_NAME, token])
            print(f"INFO: Successfully created and saved token for '{KEY_NAME}'.")

    except Exception as e:
        print(f"ERROR: An unexpected error occurred while saving the token: {e}")