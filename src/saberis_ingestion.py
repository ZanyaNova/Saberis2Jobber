import json
import uuid
import gzip
import base64
from datetime import datetime
from typing import Any, List, Set, TypedDict

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

class SaberisExportRecord(TypedDict):
    saberis_id: str
    original_filename: str  # Saberis document GUID
    stored_path: str        # Kept for compatibility, now always ""
    ingested_at: str
    export_date: str
    customer_name: str
    username: str
    shipping_address: str
    sent_to_jobber: bool
    raw_data: Any

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
            raw_json = record.get("data", "{}")
            data_dict = json.loads(raw_json)

            # ⟲ Inflate compressed payloads on‑the‑fly
            if "raw_data_gz64" in data_dict and "raw_data" not in data_dict:
                try:
                    data_dict["raw_data"] = _decompress(data_dict.pop("raw_data_gz64"))
                except Exception as e:  # pragma: no cover – safety net
                    print(f"WARN: Failed to decompress Saberis doc {record.get('saberis_id')}: {e}")
                    continue

            full_record: SaberisExportRecord = {
                "saberis_id": record.get("saberis_id"),
                "original_filename": record.get("original_filename"),
                "ingested_at": record.get("ingested_at"),
                **data_dict,
            }
            manifest.append(full_record)
            processed_guids.add(record.get("original_filename"))
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
        if not doc_json:
            print(f"WARN: Could not download Saberis doc {guid}; skipping.")
            continue

        order_node = doc_json.get("SaberisOrderDocument", {}).get("Order", {})

        data_blob = {
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

        new_row = [
            str(uuid.uuid4()),           # saberis_id
            guid,                        # original_filename (doc GUID)
            datetime.now().isoformat(),  # ingested_at
            json.dumps(data_blob, separators=(",", ":")),  # compact JSON for the data column
        ]
        new_rows.append(new_row)
        processed_guids.add(guid)

    # --- 3. Append & deduplicate -------------------------------------------------------
    if new_rows:
        GSHEET_SABERIS_EXPORTS.append_rows(new_rows, value_input_option="RAW")
        print(f"INFO: Appended {len(new_rows)} new rows to the Google Sheet.")

        # Lightweight duplicate guard: keep the first occurrence of each GUID.
        for _, guid, *_ in new_rows:
            dup_cells = GSHEET_SABERIS_EXPORTS.findall(guid) or []  # search entire sheet
            if len(dup_cells) > 1:
                # Keep the earliest row (lowest row number)
                for cell in sorted(dup_cells[1:], key=lambda c: c.row, reverse=True):
                    GSHEET_SABERIS_EXPORTS.delete_rows(cell.row)
                print(f"INFO: Removed {len(dup_cells) - 1} duplicate row(s) for {guid}.")

        # Recurse once to include freshly added rows in manifest (safe at our volumes).
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

    # Newest first
    records.sort(key=lambda r: r.get("ingested_at", ""), reverse=True)

    # Calculate sheet row indices (header row = 1, data starts at 2)
    rows_to_delete = range(keep_count + 2, len(records) + 2)  # inclusive of header offset
    for row_idx in reversed(rows_to_delete):  # delete bottom‑up to preserve indices
        GSHEET_SABERIS_EXPORTS.delete_rows(row_idx)

    deleted = len(rows_to_delete)
    print(f"SUCCESS: Pruned {deleted} old export row(s).")
    return deleted
