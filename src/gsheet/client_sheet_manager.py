from gspread import Worksheet, Cell
from .gsheet_config import GSHEET_RECORDSHEET, GSHEET_BRANDSHEET, GSHEET_MARKUP
from typing import Final

DEFAULT_MARKUP: float = 0.035

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

def get_brand_or_catalog_markup(catalog_or_brand: str) -> float:
    """
    Finds the markup for a given catalog or brand name.

    Searches the first two columns for the identifier and returns the
    corresponding markup from the third column. If not found or if the
    markup is invalid, returns the default markup.
    """
    try:
        found_cell: Cell | None = GSHEET_MARKUP.find(catalog_or_brand) # type: ignore

        if found_cell is None or found_cell.col > 2:
            return DEFAULT_MARKUP

        markup_value_str = GSHEET_MARKUP.cell(found_cell.row, 3).value

        if markup_value_str:
            markup = float(markup_value_str)
            # Return the found markup if it's a positive number, otherwise default.
            return markup if markup > 0 else DEFAULT_MARKUP

    except (ValueError, TypeError):
        # Catches errors if the cell value is not a valid number (e.g., "N/A").
        print(f"Warning: Invalid markup value found for '{catalog_or_brand}'. Using default.")
        pass
    
    return DEFAULT_MARKUP


def get_adjacent_value(sheet: Worksheet, search_value: str, columns_over: int = 1) -> str | None:
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
    adjacent_cell_value = sheet.cell(found_cell.row, found_cell.col + columns_over).value

    if adjacent_cell_value is None:
        return None

    # Ensure the function returns a string if a non-None value was found.
    return str(adjacent_cell_value)
