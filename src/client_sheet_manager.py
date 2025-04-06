import gspread
from dotenv import load_dotenv
import os

def get_client_id(saberis_id: str) -> str:
    load_dotenv()

    g_account = gspread.service_account()
    client_workbook = g_account.open_by_url(os.environ.get('WORKBOOK_ID'))
    sht_records = client_workbook.worksheet("Records")



    print(sht_records.get('A1'))


def get_adjacent_value(sheet, search_value: str) -> str:
    found_cell = sheet.find(search_value)
    if found_cell is None:
        return None

    return sheet.cell(found_cell.row, found_cell.col + 1).value


get_client_id("ClientName1")