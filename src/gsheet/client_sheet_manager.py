import gspread
from dotenv import load_dotenv
import os
from sheet_logging import add_sheet_log

def get_client_id(saberis_id: str) -> str:
    load_dotenv()

    g_account = gspread.service_account()
    client_workbook = g_account.open_by_url(os.environ.get('WORKBOOK_URL'))
    sht_records = client_workbook.worksheet("Records")

    jobber_id = get_adjacent_value(sht_records, saberis_id)

    if jobber_id is None:
        print('No record found for', saberis_id)
        """ call jobber createClient api and retun that instead. """

        """Add New Records to Spreadsheet"""
        placeholder_jobber_id = saberis_id + '_fake_jobber_id'
        saberis_column_index = 1
        jobber_column_index = saberis_column_index + 1

        saberis_column = sht_records.col_values(saberis_column_index)

        new_row_index = len(saberis_column) + 1

        sht_records.update_cell(new_row_index, saberis_column_index, saberis_id)
        sht_records.update_cell(new_row_index, jobber_column_index, placeholder_jobber_id)

        print('New jobber ID created: ', placeholder_jobber_id)

        log_message = f'No entry found for {saberis_id}. Successfully created new Jobber client ID: {placeholder_jobber_id}'

        add_sheet_log(0, 'client_sheet_manager', log_message)

        return None
    
    print('Succcess! Jobber ID for', saberis_id, 'is', jobber_id)
    return jobber_id


def get_adjacent_value(sheet, search_value: str) -> str:
    found_cell = sheet.find(search_value)
    if found_cell is None:
        return None

    return sheet.cell(found_cell.row, found_cell.col + 1).value



get_client_id("KiahsBestClient45")