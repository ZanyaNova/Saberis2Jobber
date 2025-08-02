"""
Configuration for Google Sheets.
Loads sensitive information from environment variables.
Ensures required variables are strings and present.
"""
import gspread
from gspread import Client, Spreadsheet, Worksheet
import os
import json
from typing import Final
from dotenv import load_dotenv
import base64

load_dotenv()

# --- Google Sheets API Authentication ---
try:
    creds_base64_str = os.environ.get('GOOGLE_CREDENTIALS_BASE64')
    print("--- STARTING AUTH DEBUG ---")
    print(f"DEBUG: Value of GOOGLE_CREDENTIALS_BASE64 is None? {creds_base64_str is None}")
    print(f"DEBUG: Value of GOOGLE_CREDENTIALS_BASE64 is empty string? {creds_base64_str == ''}")
    print(f"DEBUG: First 10 chars of value: {str(creds_base64_str)[:10] if creds_base64_str else 'N/A'}")
    print("--- FINISHED AUTH DEBUG ---")
    if creds_base64_str:
        print("INFO: Authenticating with Google Sheets using Base64 credentials from environment variable.")
        creds_json_str = base64.b64decode(creds_base64_str).decode('utf-8')
        creds_dict = json.loads(creds_json_str)
        account_client: Client = gspread.service_account_from_dict(creds_dict)
    else:
        # Fallback for local development
        print("INFO: GOOGLE_CREDENTIALS_BASE64 not set. Falling back to default service_account.json file.")
        account_client: Client = gspread.service_account()

    # Make the single, final assignment to the constant
    GSHEET_ACCOUNT: Final[Client] = account_client

except Exception as e:
    raise RuntimeError(
        "Failed to authenticate with Google Sheets from Base64 credentials. "
        "Please ensure GOOGLE_CREDENTIALS_BASE64 is set correctly. "
        f"Original error: {e}"
    ) from e


# --- Workbook URL ---
WORKBOOK_URL_ENV: Final[str | None] = os.environ.get('WORKBOOK_URL')

if not WORKBOOK_URL_ENV:
    raise ValueError(
        "The 'WORKBOOK_URL' environment variable is not set. "
        "Please set it in your .env file or system environment."
    )

# --- Open Workbook ---
try:
    GSHEET_WORKBOOK: Final[Spreadsheet] = GSHEET_ACCOUNT.open_by_url(WORKBOOK_URL_ENV)
except gspread.exceptions.APIError as e:
    raise RuntimeError(
        f"Failed to open Google Sheets workbook with URL: {WORKBOOK_URL_ENV}. "
        "Ensure the URL is correct and the service account has access permissions. "
        f"Original error: {e}"
    ) from e
except Exception as e:
    raise RuntimeError(
        f"An unexpected error occurred while trying to open the workbook: {WORKBOOK_URL_ENV}. "
        f"Original error: {e}"
    ) from e


# --- Open Workbook and Specific Worksheet: Config ---
# This sheet will store key-value pairs for configuration, like API tokens.
CONFIG_SHEET_NAME: Final[str] = "Config"
try:
    # First, just try to get the worksheet.
    config_sheet: Worksheet = GSHEET_WORKBOOK.worksheet(CONFIG_SHEET_NAME)
except gspread.exceptions.WorksheetNotFound:
    # If it doesn't exist, try to create it.
    print(f"INFO: Worksheet '{CONFIG_SHEET_NAME}' not found. Attempting to create it now.")
    try:
        config_sheet = GSHEET_WORKBOOK.add_worksheet(title=CONFIG_SHEET_NAME, rows=10, cols=2)
        # Set up headers for the new sheet
        config_sheet.update(values=[['Key', 'Value']], range_name='A1:B1')
        config_sheet.format('A1:B1', {'textFormat': {'bold': True}})
        print(f"INFO: Successfully created new worksheet '{CONFIG_SHEET_NAME}'.")
    except gspread.exceptions.APIError as api_error:
        # If creating it fails because it *already* exists (the race condition),
        # we can now be confident it's safe to just fetch it.
        print(f"INFO: Could not create worksheet (it likely already exists). Fetching it. Details: {api_error}")
        config_sheet = GSHEET_WORKBOOK.worksheet(CONFIG_SHEET_NAME)

# Assign the final, confirmed worksheet object to the constant.
GSHEET_CONFIG_SHEET: Final[Worksheet] = config_sheet

# --- Open Workbook and Specific Worksheet: Saberis Exports ---
# This sheet will store the JSON data for each processed Saberis export.
EXPORTS_SHEET_NAME: Final[str] = "SaberisExports"
try:
    # First, just try to get the worksheet.
    exports_sheet: Worksheet = GSHEET_WORKBOOK.worksheet(EXPORTS_SHEET_NAME)
except gspread.exceptions.WorksheetNotFound:
    # If it doesn't exist, try to create it.
    print(f"INFO: Worksheet '{EXPORTS_SHEET_NAME}' not found. Attempting to create it now.")
    try:
        exports_sheet = GSHEET_WORKBOOK.add_worksheet(title=EXPORTS_SHEET_NAME, rows=100, cols=4)
        # Set up headers for the new sheet. We will store most data as a JSON string.
        exports_sheet.update(values=[['saberis_id', 'original_filename', 'ingested_at', 'data']], range_name='A1:D1')
        exports_sheet.format('A1:D1', {'textFormat': {'bold': True}})
        print(f"INFO: Successfully created new worksheet '{EXPORTS_SHEET_NAME}'.")
    except gspread.exceptions.APIError as api_error:
        # If creating it fails because it *already* exists (a race condition),
        # we can now be confident it's safe to just fetch it.
        print(f"INFO: Could not create worksheet (it likely already exists). Fetching it. Details: {api_error}")
        exports_sheet = GSHEET_WORKBOOK.worksheet(EXPORTS_SHEET_NAME)

# Assign the final, confirmed worksheet object to the constant.
GSHEET_SABERIS_EXPORTS: Final[Worksheet] = exports_sheet

# --- Open Workbook and Specific Worksheet: Log ---
LOG_SHEET_NAME: Final[str] = "Log"

try:
    GSHEET_LOGSHEET: Final[Worksheet] = GSHEET_WORKBOOK.worksheet(LOG_SHEET_NAME)
except gspread.exceptions.WorksheetNotFound:
    raise ValueError(
        f"The worksheet named '{LOG_SHEET_NAME}' was not found in the workbook: {WORKBOOK_URL_ENV}. "
        "Please ensure the sheet exists and the name is correct."
    )
except Exception as e:
    raise RuntimeError(
        f"An unexpected error occurred while trying to access worksheet '{LOG_SHEET_NAME}'. "
        f"Original error: {e}"
    ) from e

# --- Log Priority Threshold ---
LOG_PRIORITY_THRESHOLD_ENV_VAR_NAME: Final[str] = 'LOG_PRIORITY_THRESHOLD'
LOG_PRIORITY_THRESHOLD_STR: Final[str | None] = os.environ.get(LOG_PRIORITY_THRESHOLD_ENV_VAR_NAME)

if LOG_PRIORITY_THRESHOLD_STR is None:
    raise ValueError(
        f"The '{LOG_PRIORITY_THRESHOLD_ENV_VAR_NAME}' environment variable is not set. "
        "Please set it in your .env file or system environment to an integer between 0 and 5."
    )

try:
    LOG_PRIORITY_THRESHOLD: Final[int] = int(LOG_PRIORITY_THRESHOLD_STR)
except ValueError:
    raise ValueError(
        f"The '{LOG_PRIORITY_THRESHOLD_ENV_VAR_NAME}' environment variable ('{LOG_PRIORITY_THRESHOLD_STR}') "
        "is not a valid integer. Please set it to an integer between 0 and 5."
    )

if not (0 <= LOG_PRIORITY_THRESHOLD <= 5):
    raise ValueError(
        f"The '{LOG_PRIORITY_THRESHOLD_ENV_VAR_NAME}' ({LOG_PRIORITY_THRESHOLD}) must be an integer "
        "between 0 and 5 (inclusive)."
    )

# --- Open Workbook and Specific Worksheet: Brand ---
CATALOG_DATA_NAME: Final[str] = "CatalogData"  

try:
    GSHEET_CATALOG_DATA: Final[Worksheet] = GSHEET_WORKBOOK.worksheet(CATALOG_DATA_NAME)
except gspread.exceptions.WorksheetNotFound:
    raise ValueError(
        f"The worksheet named '{CATALOG_DATA_NAME}' was not found in the workbook: {WORKBOOK_URL_ENV}. "
        "Please ensure the sheet exists and the name is correct."
    )
except Exception as e:
    raise RuntimeError(
        f"An unexpected error occurred while trying to access worksheet '{CATALOG_DATA_NAME}'. "
        f"Original error: {e}"
    ) from e
