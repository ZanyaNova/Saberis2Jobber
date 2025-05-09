import gspread
from dotenv import load_dotenv
import os
from datetime import datetime

def add_sheet_log(priority: str, context: str, message: str):
    load_dotenv()

    g_account = gspread.service_account()
    client_workbook = g_account.open_by_url(os.environ.get('WORKBOOK_URL'))
    sht_records = client_workbook.worksheet("Log")

    logs = sht_records.col_values(1)
    new_row_index = len(logs) + 1

    timestamp_column_index = 1
    severity_column_index = timestamp_column_index + 1
    context_column_index = severity_column_index + 1
    message_column_index = context_column_index + 1

    priority_threshold = int(os.environ.get('LOG_PRIORITY_THRESHOLD'))

    if priority_threshold >= priority:
    # Get current time in Google Sheets epoch time (seconds since 1899-12-30)
        current_time = (datetime.now() - datetime(1899, 12, 30)).total_seconds() / 86400
        
        sht_records.update_cell(new_row_index, timestamp_column_index, current_time)
        sht_records.update_cell(new_row_index, severity_column_index, priority)
        sht_records.update_cell(new_row_index, context_column_index, context)
        sht_records.update_cell(new_row_index, message_column_index, message)

    print(f"[{priority}] {context}: {message}")







