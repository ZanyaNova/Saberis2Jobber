from .gsheet_config import GSHEET_LOGSHEET, LOG_PRIORITY_THRESHOLD
from datetime import datetime
import gspread

def add_sheet_log(priority: int, context: str, message: str):
    """
    Adds a log entry to the Google Sheet if the priority meets the threshold.
    Also prints the log message to the console.

    Args:
        priority (int): The priority of the log message (0-5, lower is more critical).
        context (str): The context of the log message (e.g., function name, module).
        message (str): The log message content.
    """

    print(f"[{priority}] {context}: {message}")

    if LOG_PRIORITY_THRESHOLD >= priority:
        try:
            timestamp_val = datetime.now().isoformat()
            row_to_append = [timestamp_val, priority, context, message] #type: ignore

            GSHEET_LOGSHEET.append_row(
                row_to_append, #type: ignore
                value_input_option='USER_ENTERED' #type: ignore
            ) 
        except gspread.exceptions.APIError as e:
            print(f"!!! APIError writing to Google Sheet: {e}")
        except Exception as e:
            print(f"!!! Unexpected error writing to Google Sheet: {e}")

