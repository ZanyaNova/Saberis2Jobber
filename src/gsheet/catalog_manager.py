import time
from typing import Dict, List, Final, Tuple, cast

from gspread import Worksheet, exceptions

# Assume this is your single, consolidated sheet
from .gsheet_config import GSHEET_CATALOG_DATA

# --- Constants ---
DEFAULT_MARKUP: Final[float] = 0.035
CATALOG_COL: Final[int] = 1
BRAND_COL: Final[int] = 2
MARKUP_COL: Final[int] = 3

# --- The All-in-One Manager ---

class CatalogManager:
    """
    Manages product data from a single Google Sheet.
    The sheet is expected to have: Catalog (col 1), Brand (col 2), Markup (col 3).
    All lookups are keyed by the catalog ID.
    """

    def __init__(self, worksheet: Worksheet, max_age_seconds: int = 90):
        self.worksheet: Worksheet = worksheet
        self._max_age_seconds: int = max_age_seconds
        # The cache stores a tuple: (brand, markup)
        self._cache: Dict[str, Tuple[str, float]] = {}
        self.last_updated: float = 0.0
        self._refresh()

    def _is_stale(self) -> bool:
        """Checks if the cache is past its max age."""
        return (time.time() - self.last_updated) > self._max_age_seconds

    def _refresh(self) -> None:
        """Fetches all data from the sheet and rebuilds the cache."""
        print("⏳ Refreshing catalog cache...")
        all_rows = cast(List[List[str]], self.worksheet.get_all_values())
        # Skip header row
        data_rows = all_rows[1:] if all_rows else []

        cache: Dict[str, Tuple[str, float]] = {}
        for row in data_rows:
            # Skip rows without a catalog ID
            if not row or not row[CATALOG_COL - 1]:
                continue
            
            catalog_id = row[CATALOG_COL - 1]
            
            # 1. Determine the brand: Use brand column, or fall back to catalog ID
            brand = catalog_id
            if len(row) >= BRAND_COL and row[BRAND_COL - 1]:
                brand = row[BRAND_COL - 1]

            # 2. Determine the markup: Use markup column, or fall back to default
            markup = DEFAULT_MARKUP
            if len(row) >= MARKUP_COL:
                try:
                    markup_val = float(row[MARKUP_COL - 1])
                    # Only accept valid, positive markups
                    if markup_val > 0:
                        markup = markup_val
                except (ValueError, TypeError):
                    # Value was not a valid number, so we use the default
                    pass
            
            cache[catalog_id] = (brand, markup)
            print(catalog_id + " | " + brand + " = " + str(markup))
        
        self._cache = cache
        self.last_updated = time.time()
        print(f"✅ Catalog cache refreshed with {len(cache)} items.")

    def _ensure_fresh(self) -> None:
        """Convenience method to refresh the cache if it's stale."""
        if self._is_stale():
            self._refresh()

    def get_brand(self, catalog_id: str) -> str:
        """Gets the brand for a catalog ID. Returns the catalog ID if no brand is set."""
        self._ensure_fresh()
        # The brand is the first item in the cached tuple.
        # If catalog_id is not in cache, default tuple's 1st item is catalog_id.
        return self._cache.get(catalog_id, (catalog_id, 0.0))[0]

    def get_markup(self, catalog_id: str) -> float:
        """Gets the markup for a catalog ID. Returns the default markup if not set."""
        self._ensure_fresh()
        # The markup is the second item.
        # If catalog_id not in cache, default tuple's 2nd item is DEFAULT_MARKUP.
        print("===Markup=== " + str(self._cache.get(catalog_id, ( "", DEFAULT_MARKUP)))[1])
        return self._cache.get(catalog_id, ( "", DEFAULT_MARKUP))[1]

    def set_markup(self, catalog_id: str, markup: float) -> bool:
        """
        Sets the markup for a catalog ID.
        Updates the row if the catalog ID exists, otherwise creates a new row.
        """
        print(f"Attempting to set markup for '{catalog_id}' to {markup}...")
        try:
            # This is a write operation, so we accept one API call to find the cell.
            cell = self.worksheet.find(catalog_id, in_column=CATALOG_COL) #type:ignore

            if cell:
                # Catalog exists, update the markup in that row
                self.worksheet.update_cell(cell.row, MARKUP_COL, markup)
                print(f"Updated existing entry for '{catalog_id}'.")
            else:
                # Catalog is new, create a new row for it
                # We leave the brand column empty; it will default to the catalog ID on read.
                self.worksheet.append_row([catalog_id, "", markup])
                print(f"Created new entry for '{catalog_id}'.")

            # Force a refresh on the next read to ensure the cache is in sync.
            self.last_updated = 0.0
            return True

        except exceptions.GSpreadException as e:
            print(f"🚨 Failed to set markup for '{catalog_id}'. Error: {e}")
            return False

# --- Global Instance ---
# You'll import and use this single manager across your application.
catalog_manager = CatalogManager(GSHEET_CATALOG_DATA)