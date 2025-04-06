import gspread
from dotenv import load_dotenv
import os

def get_client_id(saberis_id: str) -> str:
    load_dotenv()

    g_account = gspread.service_account()
    client_workbook = g_account.open_by_url(os.environ.get('WORKBOOK_ID'))
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

        first_empty_row = len(saberis_column) + 1

        sht_records.update_cell(first_empty_row, saberis_column_index, saberis_id)
        sht_records.update_cell(first_empty_row, jobber_column_index, placeholder_jobber_id)

        print('New jobber ID created: ', placeholder_jobber_id)

        return None
    
    print('Succcess! Jobber ID for', saberis_id, 'is', jobber_id)
    return jobber_id


def get_adjacent_value(sheet, search_value: str) -> str:
    found_cell = sheet.find(search_value)
    if found_cell is None:
        return None

    return sheet.cell(found_cell.row, found_cell.col + 1).value



get_client_id("ClientName3")