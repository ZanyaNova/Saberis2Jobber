from gspread import Worksheet, Cell
from sheet_logging import add_sheet_log
from gsheet_config import GSHEET_RECORDSHEET, GSHEET_BRANDSHEET
from typing import Final

def get_client_id(saberis_id: str) -> str:

    jobber_id = get_adjacent_value(GSHEET_RECORDSHEET, saberis_id)

    if jobber_id == "" or jobber_id is None:
        print('No record found for', saberis_id)
        # call jobber createClient api and retun that instead.

        placeholder_jobber_id = saberis_id + '_fake_jobber_id'
        print ('NOT PRODUCTION READY: using fake jobber ID, need to create a client and get the real one')
        SABERIS_COLUMN_INDEX: Final[int] = 1
        JOBBER_COLUMN_INDEX: Final[int] = SABERIS_COLUMN_INDEX + 1

        saberis_column_values = GSHEET_RECORDSHEET.col_values(SABERIS_COLUMN_INDEX)

        new_row_index = len(saberis_column_values) + 1

        GSHEET_RECORDSHEET.update_cell(new_row_index, SABERIS_COLUMN_INDEX, saberis_id)
        GSHEET_RECORDSHEET.update_cell(new_row_index, JOBBER_COLUMN_INDEX, placeholder_jobber_id)

        print('New jobber ID created: ', placeholder_jobber_id)

        log_message = f'No entry found for {saberis_id}. Successfully created new Jobber client ID: {placeholder_jobber_id}'

        add_sheet_log(0, 'client_sheet_manager', log_message)

        return placeholder_jobber_id
    
    print('Succcess! Jobber ID for', saberis_id, 'is', jobber_id)
    return jobber_id


def get_brand_if_available(catalog_id: str) -> str:
    """
    Finds and returns the brand associated with a catalog id in the google sheet.
    If none is found, it creates a line entry in the sheet for a human to associate
    a brand with later and returns the catalog id.
    """
    found_value = get_adjacent_value(GSHEET_BRANDSHEET, catalog_id) 

    if found_value is str:
        return found_value
    
    # Return early if the cell already exists, it's still waiting on humans to add the brand
    found_key_cell: Cell | None = GSHEET_BRANDSHEET.find(catalog_id) #type: ignore
    if found_key_cell is Cell:
        return catalog_id
    
    # Since its not been found, add ID to end of list 
    CATALOG_ID_COLUMN_INDEX: Final[int] = 1
    catalog_column_values: list[int | float | str | None] = GSHEET_RECORDSHEET.col_values(CATALOG_ID_COLUMN_INDEX)
    new_row_index: int = len(catalog_column_values) + 1
    GSHEET_RECORDSHEET.update_cell(new_row_index, CATALOG_ID_COLUMN_INDEX, catalog_id)
    return catalog_id


def get_adjacent_value(sheet: Worksheet, search_value: str) -> str | None:
    """
    Finds a cell with search_value and returns the string value of the cell
    to its right. Returns None if search_value is not found or the adjacent
    cell is empty.
    """
    # sheet.find() returns either a gspread.Cell object or None.
    found_cell: Cell | None = sheet.find(search_value) #type: ignore

    if found_cell is None:
        return None

    # If found_cell is not None, it's a gspread.Cell object.
    # Accessing .row and .col is safe here.
    # The .value of a cell can be str, int, float, bool, or None if the cell is empty.
    adjacent_cell_value = sheet.cell(found_cell.row, found_cell.col + 1).value

    if adjacent_cell_value is None:
        return None

    # Ensure the function returns a string if a non-None value was found.
    return str(adjacent_cell_value)



get_client_id("KiahsBestClient46")