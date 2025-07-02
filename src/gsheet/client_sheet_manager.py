from gspread import Worksheet, Cell

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
    # The .value of a cell can be str, int, float, bool, or None if the cell is empty.
    adjacent_cell_value = sheet.cell(found_cell.row, found_cell.col + columns_over).value

    if adjacent_cell_value is None:
        return None

    # Ensure the function returns a string if a non-None value was found.
    return str(adjacent_cell_value)
