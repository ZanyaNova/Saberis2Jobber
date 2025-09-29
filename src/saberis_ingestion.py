import json
import uuid
import gzip
import base64
from datetime import datetime
from typing import Any, List, Set, TypedDict, cast
from gspread.utils import ValueInputOption

from .saberis_api_client import SaberisAPIClient
from .gsheet.gsheet_config import GSHEET_SABERIS_EXPORTS

# ---------------------------------------------------------------------------
# Helper functions for compact JSON storage in Google Sheets
# ---------------------------------------------------------------------------

def _compress(obj: Any) -> str:
    """Return a gzipped + base‑64 string representation of *obj*."""
    raw_bytes = json.dumps(obj, separators=(",", ":")).encode()
    gz_bytes = gzip.compress(raw_bytes, compresslevel=9)
    return "gz64:" + base64.b64encode(gz_bytes).decode()


def _decompress(blob: str) -> Any:
    """Inverse of :func:`_compress`.

    Accepts either a legacy plain‑JSON string or a ``gz64:...`` string and
    returns the original Python object.
    """
    if not blob.startswith("gz64:"):
        return json.loads(blob)
    gz_bytes = base64.b64decode(blob[5:])
    raw_bytes = gzip.decompress(gz_bytes)
    return json.loads(raw_bytes)

# ---------------------------------------------------------------------------
# Manifest record type
# ---------------------------------------------------------------------------

class SaberisDataBlob(TypedDict):
    customer_name: str
    username: str
    export_date: str
    shipping_address: str
    sent_to_jobber: bool
    raw_data_gz64: str
    stored_path: str


class SaberisExportRecord(TypedDict):
    saberis_id: str
    original_filename: str
    ingested_at: str
    # Nested data from the JSON blob
    customer_name: str
    username: str
    export_date: str
    shipping_address: str
    sent_to_jobber: bool
    raw_data: Any # This will hold the decompressed, raw JSON
    raw_data_gz64: str # Keep the compressed version
    stored_path: str


# ---------------------------------------------------------------------------
# Ingestion logic
# ---------------------------------------------------------------------------

def ingest_saberis_exports() -> List[SaberisExportRecord]:
    """Synchronise new Saberis exports into the Google Sheet and return the full manifest."""

    print("INFO: Ingesting Saberis exports from Google Sheet…")

    sheet_records = GSHEET_SABERIS_EXPORTS.get_all_records()
    manifest: List[SaberisExportRecord] = []
    processed_guids: Set[str] = set()

    # --- 1. Read existing sheet rows ---------------------------------------------------
    for record in sheet_records:
        try:
            # FIX: Ensure the value is a string before parsing
            raw_json_from_sheet = record.get("data", "{}")
            if not isinstance(raw_json_from_sheet, str):
                raw_json_from_sheet = json.dumps(raw_json_from_sheet)

            data_dict = cast(SaberisDataBlob, json.loads(raw_json_from_sheet))

            # ⟲ Inflate compressed payloads on‑the‑fly
            raw_data = {}
            if "raw_data_gz64" in data_dict:
                try:
                    raw_data = _decompress(data_dict["raw_data_gz64"])
                except Exception as e:
                    print(f"WARN: Failed to decompress Saberis doc {record.get('saberis_id')}: {e}")
                    continue

            # FIX: Construct the record with explicit casting for each field
            full_record: SaberisExportRecord = {
                "saberis_id": str(record.get("saberis_id", "")),
                "original_filename": str(record.get("original_filename", "")),
                "ingested_at": str(record.get("ingested_at", "")),
                "customer_name": data_dict.get("customer_name", "N/A"),
                "username": data_dict.get("username", "N/A"),
                "export_date": data_dict.get("export_date", "N/A"),
                "shipping_address": data_dict.get("shipping_address", ""),
                "sent_to_jobber": data_dict.get("sent_to_jobber", False),
                "raw_data_gz64": data_dict.get("raw_data_gz64", ""),
                "stored_path": data_dict.get("stored_path", ""),
                "raw_data": raw_data,
            }
            manifest.append(full_record)
            # FIX: Ensure the guid is a string before adding to the set
            processed_guids.add(str(record.get("original_filename")))

        except (json.JSONDecodeError, TypeError) as e:
            print(f"WARN: Malformed JSON in row for saberis_id={record.get('saberis_id')}: {e}")
            continue

    # --- 2. Ask Saberis for anything we haven't stored yet -----------------------------
    client = SaberisAPIClient()
    unexported_docs = client.get_unexported_documents() or []

    new_rows: List[List[Any]] = []

    for doc_header in unexported_docs:
        guid = doc_header.get("guid")
        if not guid or guid in processed_guids:
            continue

        print(f"INFO: Found new Saberis doc {guid}. Downloading…")
        doc_json = client.get_export_document_by_id(guid)
        # DEBUG:
        print(json.dumps(doc_json, indent=2))

        if not doc_json:
            print(f"WARN: Could not download Saberis doc {guid}; skipping.")
            continue

        order_node = doc_json.get("SaberisOrderDocument", {}).get("Order", {})

        # FIX: Define the type of data_blob explicitly
        data_blob: SaberisDataBlob = {
            "customer_name": order_node.get("Customer", {}).get("Name", "N/A"),
            "username": order_node.get("Username", "N/A"),
            "export_date": order_node.get("Date", "N/A"),
            "shipping_address": ", ".join(filter(None, [
                order_node.get("Shipping", {}).get("Address"),
                order_node.get("Shipping", {}).get("City"),
                order_node.get("Shipping", {}).get("StateOrProvince"),
            ])),
            "sent_to_jobber": False,
            "raw_data_gz64": _compress(doc_json),
            "stored_path": "",
        }

        # FIX: Define the type of new_row explicitly
        new_row: List[Any] = [
            str(uuid.uuid4()),
            guid,
            datetime.now().isoformat(),
            json.dumps(data_blob, separators=(",", ":")),
        ]
        new_rows.append(new_row)
        processed_guids.add(guid)


    # --- 3. Append & deduplicate -------------------------------------------------------
    if new_rows:
        GSHEET_SABERIS_EXPORTS.append_rows(new_rows, value_input_option=ValueInputOption.raw)
        print(f"INFO: Appended {len(new_rows)} new rows to the Google Sheet.")

        for _, guid, *_ in new_rows:
            dup_cells = GSHEET_SABERIS_EXPORTS.findall(guid) or [] #type:ignore
            if len(dup_cells) > 1:
                for cell in sorted(dup_cells[1:], key=lambda c: c.row, reverse=True):
                    GSHEET_SABERIS_EXPORTS.delete_rows(cell.row)
                print(f"INFO: Removed {len(dup_cells) - 1} duplicate row(s) for {guid}.")

        return ingest_saberis_exports()

    # --- 4. Return manifest sorted by newest first -------------------------------------
    manifest.sort(key=lambda r: r["ingested_at"], reverse=True)
    return manifest

# ---------------------------------------------------------------------------
# House‑keeping utilities
# ---------------------------------------------------------------------------

def prune_saberis_exports(keep_count: int = 3) -> int:
    """Keep only the *keep_count* most‑recent exports; delete the rest from the sheet."""

    print(f"INFO: Pruning Saberis exports, retaining {keep_count} latest entries…")
    records = GSHEET_SABERIS_EXPORTS.get_all_records()
    if len(records) <= keep_count:
        print("INFO: Nothing to prune – sheet already small.")
        return 0

    records.sort(key=lambda r: str(r.get("ingested_at", "")), reverse=True)

    rows_to_delete = range(keep_count + 2, len(records) + 2)
    for row_idx in reversed(rows_to_delete):
        GSHEET_SABERIS_EXPORTS.delete_rows(row_idx)

    deleted = len(rows_to_delete)
    print(f"SUCCESS: Pruned {deleted} old export row(s).")
    return deleted