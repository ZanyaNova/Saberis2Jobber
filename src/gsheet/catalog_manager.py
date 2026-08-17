# catalog_manager.py (with dataclass)

import time
from typing import Dict, List, Final, cast, Optional, Any
from dataclasses import dataclass

from gspread import Worksheet, exceptions

from .gsheet_config import GSHEET_CATALOG_DATA

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


class CatalogManager:
    """
    Manages product data from a single Google Sheet.
    Multiple pricing presets (multiplier/margin pairs) can be stored per catalog ID.
    """

    def __init__(self, worksheet: Worksheet, max_age_seconds: int = 90):
        self.worksheet: Worksheet = worksheet
        self._max_age_seconds: int = max_age_seconds
        self._cache: Dict[str, List[CatalogItem]] = {}
        self.last_updated: float = 0.0
        self._refresh()

    def _is_stale(self) -> bool:
        return (time.time() - self.last_updated) > self._max_age_seconds

    def _refresh(self) -> None:
        """Fetches all data from the sheet and rebuilds the cache."""
        print("⏳ Refreshing catalog cache...")
        all_rows = cast(List[List[str]], self.worksheet.get_all_values())
        data_rows = all_rows[1:] if all_rows else []

        cache: Dict[str, List[CatalogItem]] = {}
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

            item = CatalogItem(catalog_id=catalog_id, brand=brand, multiplier=multiplier, margin=margin)
            if catalog_id not in cache:
                cache[catalog_id] = []
            cache[catalog_id].append(item)

        self._cache = cache
        total_entries = sum(len(v) for v in cache.values())
        self.last_updated = time.time()
        print(f"✅ Catalog cache refreshed: {len(cache)} catalog IDs, {total_entries} total entries.")

    def _ensure_fresh(self) -> None:
        if self._is_stale():
            self._refresh()

    def get_brand(self, catalog_id: str) -> Optional[str]:
        self._ensure_fresh()
        items = self._cache.get(catalog_id, [])
        return next((item.brand for item in items if item.brand), None)

    def get_catalog_data(self, catalog_id: str) -> Dict[str, Any]:
        """Returns the brand and list of pricing presets for a catalog ID."""
        self._ensure_fresh()
        items = self._cache.get(catalog_id, [])
        brand = next((item.brand for item in items if item.brand), None)
        presets = [
            {"multiplier": item.multiplier, "margin": item.margin}
            for item in items
            if item.multiplier is not None and item.margin is not None
        ]
        return {
            "catalog_id": catalog_id,
            "brand": brand,
            "presets": presets,
        }

    def add_catalog_preset(self, catalog_id: str, multiplier: float, margin: float) -> bool:
        """Appends a new pricing preset row for a catalog ID."""
        print(f"Adding preset for '{catalog_id}': (Multiplier: {multiplier}, Margin: {margin})...")
        try:
            self._ensure_fresh()
            for item in self._cache.get(catalog_id, []):
                if item.multiplier is not None and item.margin is not None:
                    if abs(item.multiplier - multiplier) < 0.001 and abs(item.margin - margin) < 0.001:
                        print(f"Preset already exists for '{catalog_id}', skipping.")
                        return True
            self.worksheet.append_row([catalog_id, "", multiplier, margin])
            self.last_updated = 0.0
            print(f"Added preset for '{catalog_id}'.")
            return True
        except exceptions.GSpreadException as e:
            print(f"🚨 Failed to add preset for '{catalog_id}'. Error: {e}")
            return False

    def delete_catalog_preset(self, catalog_id: str, multiplier: float, margin: float) -> bool:
        """Finds and deletes the matching pricing preset row from the sheet."""
        print(f"Deleting preset for '{catalog_id}': (Multiplier: {multiplier}, Margin: {margin})...")
        try:
            all_rows = cast(List[List[str]], self.worksheet.get_all_values())
            for i, row in enumerate(all_rows[1:], start=2):
                if not row or not row[CATALOG_COL - 1]:
                    continue
                if row[CATALOG_COL - 1].strip() != catalog_id:
                    continue
                try:
                    row_mult = float(row[MULTIPLIER_COL - 1]) if len(row) >= MULTIPLIER_COL and row[MULTIPLIER_COL - 1] else None
                    row_margin = float(row[MARGIN_COL - 1]) if len(row) >= MARGIN_COL and row[MARGIN_COL - 1] else None
                except (ValueError, TypeError):
                    continue
                if row_mult is not None and row_margin is not None:
                    if abs(row_mult - multiplier) < 0.001 and abs(row_margin - margin) < 0.001:
                        self.worksheet.delete_rows(i)
                        self.last_updated = 0.0
                        print(f"Deleted preset for '{catalog_id}'.")
                        return True
            print(f"No matching preset found for '{catalog_id}'.")
            return False
        except exceptions.GSpreadException as e:
            print(f"🚨 Failed to delete preset for '{catalog_id}'. Error: {e}")
            return False


# --- Global Instance ---
catalog_manager = CatalogManager(GSHEET_CATALOG_DATA)
