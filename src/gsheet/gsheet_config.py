"""
Configuration for Google Sheets.
Loads sensitive information from environment variables.
Ensures required variables are strings and present.
"""
import gspread
from gspread import Client, Spreadsheet, Worksheet
import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()

# --- Google Sheets API Authentication ---
try:
    GSHEET_ACCOUNT: Final[Client] = gspread.service_account()
except Exception as e:
    # Provide a more informative error message if service account setup fails
    raise RuntimeError(
        "Failed to authenticate with Google Sheets using service account. "
        "Ensure 'credentials.json' (or your specified service account file) is correctly set up. "
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

# --- Open Workbook and Specific Worksheet: Log ---
LOG_SHEET_NAME: Final[str] = "Log"  # Define the sheet name as a constant

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
BRAND_SHEET_NAME: Final[str] = "CatalogToBrand"  # Define the sheet name as a constant

try:
    GSHEET_BRANDSHEET: Final[Worksheet] = GSHEET_WORKBOOK.worksheet(BRAND_SHEET_NAME)
except gspread.exceptions.WorksheetNotFound:
    raise ValueError(
        f"The worksheet named '{BRAND_SHEET_NAME}' was not found in the workbook: {WORKBOOK_URL_ENV}. "
        "Please ensure the sheet exists and the name is correct."
    )
except Exception as e:
    raise RuntimeError(
        f"An unexpected error occurred while trying to access worksheet '{BRAND_SHEET_NAME}'. "
        f"Original error: {e}"
    ) from e

# --- Open Workbook and Specific Worksheet: Markup ---
MARKUP_SHEET_NAME: Final[str] = "Markup"  
GSHEET_MARKUP = GSHEET_BRANDSHEET