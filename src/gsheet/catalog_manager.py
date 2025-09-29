# catalog_manager.py (with dataclass)

import time
from typing import Dict, List, Final, cast, Optional
from dataclasses import dataclass

from gspread import Worksheet, exceptions

# Assume this is your single, consolidated sheet
from .gsheet_config import GSHEET_CATALOG_DATA

# --- Data Structure ---
@dataclass
class CatalogItem:
    """A structured representation of a row in our catalog sheet."""
    catalog_id: str
    brand: Optional[str]
    multiplier: Optional[float]
    margin: Optional[float]

# Column positions in the Google Sheet (1-based index)
CATALOG_COL: Final[int] = 1
BRAND_COL: Final[int] = 2
MULTIPLIER_COL: Final[int] = 3
MARGIN_COL: Final[int] = 4

# --- The All-in-One Manager ---

class CatalogManager:
    """
    Manages product data from a single Google Sheet.
    Lookups are keyed by catalog ID and return a structured CatalogItem.
    """

    def __init__(self, worksheet: Worksheet, max_age_seconds: int = 90):
        self.worksheet: Worksheet = worksheet
        self._max_age_seconds: int = max_age_seconds
        self._cache: Dict[str, CatalogItem] = {}
        self.last_updated: float = 0.0
        self._refresh()

    def _is_stale(self) -> bool:
        """Checks if the cache is past its max age."""
        return (time.time() - self.last_updated) > self._max_age_seconds

    def _refresh(self) -> None:
        """Fetches all data from the sheet and rebuilds the cache."""
        print("⏳ Refreshing catalog cache...")
        all_rows = cast(List[List[str]], self.worksheet.get_all_values())
        data_rows = all_rows[1:] if all_rows else []

        cache: Dict[str, CatalogItem] = {}
        for row in data_rows:
            if not row or not row[CATALOG_COL - 1]:
                continue
            
            catalog_id = row[CATALOG_COL - 1].strip()
            
            brand = None
            if len(row) >= BRAND_COL and row[BRAND_COL - 1]:
                brand = row[BRAND_COL - 1].strip()

            multiplier: Optional[float] = None
            if len(row) >= MULTIPLIER_COL and row[MULTIPLIER_COL - 1]:
                try:
                    multiplier = float(row[MULTIPLIER_COL - 1])
                except (ValueError, TypeError):
                    pass 

            margin: Optional[float] = None
            if len(row) >= MARGIN_COL and row[MARGIN_COL - 1]:
                try:
                    margin = float(row[MARGIN_COL - 1])
                except (ValueError, TypeError):
                    pass
            
            cache[catalog_id] = CatalogItem(
                catalog_id=catalog_id,
                brand=brand, 
                multiplier=multiplier, 
                margin=margin
            )
        
        self._cache = cache
        self.last_updated = time.time()
        print(f"✅ Catalog cache refreshed with {len(cache)} items.")

    def _ensure_fresh(self) -> None:
        """Convenience method to refresh the cache if it's stale."""
        if self._is_stale():
            self._refresh()

    def get_brand(self, catalog_id: str) -> str | None:
        """Gets the brand for a catalog ID."""
        return self.get_catalog_item(catalog_id).brand 

    def get_catalog_item(self, catalog_id: str) -> CatalogItem:
        """
        Gets the entire CatalogItem object for a given ID.
        If not found, returns a default item with the requested catalog_id.
        """
        self._ensure_fresh()
        item = self._cache.get(catalog_id)
        
        if item:
            return item
        else:
            print(f"No entry in cache for catalog_id: {catalog_id}, returning an item with null pricing.")
            # Construct a new item with null values for pricing factors
            return CatalogItem(
                catalog_id=catalog_id,
                brand=None,
                multiplier=None,
                margin=None
            )


    def set_pricing_factors(self, catalog_id: str, multiplier: float, margin: float) -> bool:
        """
        Sets the pricing factors for a catalog ID. Updates or creates a row.
        """
        print(f"Attempting to set pricing for '{catalog_id}' to (Multiplier: {multiplier}, Margin: {margin})...")
        try:
            cell = self.worksheet.find(catalog_id, in_column=CATALOG_COL) #type:ignore

            if cell:
                range_to_update = f'C{cell.row}:D{cell.row}'
                self.worksheet.update(range_name=range_to_update, values=[[multiplier, margin]])
                print(f"Updated existing entry for '{catalog_id}'.")
            else:
                self.worksheet.append_row([catalog_id, "", multiplier, margin])
                print(f"Created new entry for '{catalog_id}'.")

            self.last_updated = 0.0
            return True

        except exceptions.GSpreadException as e:
            print(f"🚨 Failed to set pricing for '{catalog_id}'. Error: {e}")
            return False

# --- Global Instance ---
catalog_manager = CatalogManager(GSHEET_CATALOG_DATA)