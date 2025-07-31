import json
import uuid
from datetime import datetime
from typing import List, TypedDict, Any

from .saberis_api_client import SaberisAPIClient
from .gsheet.gsheet_config import GSHEET_SABERIS_EXPORTS

class SaberisExportRecord(TypedDict):
    saberis_id: str
    original_filename: str # This will now be the Saberis doc GUID
    stored_path: str # We'll keep this field but it will be empty or null
    ingested_at: str
    export_date: str
    customer_name: str
    username: str
    shipping_address: str
    sent_to_jobber: bool
    raw_data: Any

def ingest_saberis_exports() -> List[SaberisExportRecord]:
    """
    Scans for new Saberis exports via the API, processes them, and updates the
    SaberisExports Google Sheet. Returns the complete, sorted list of records.
    """
    print("INFO: Ingesting from Google Sheet based storage.")
    # Fetch all existing records from the sheet. get_all_records() returns a list of dicts.
    sheet_records = GSHEET_SABERIS_EXPORTS.get_all_records()
    manifest: List[SaberisExportRecord] = []
    processed_guids = set()

    for record in sheet_records:
        try:
            # The 'data' cell contains a JSON string, so we parse it.
            data_dict = json.loads(record.get('data', '{}'))
            
            # Reconstruct the full record object in memory
            full_record = {
                "saberis_id": record.get('saberis_id'),
                "original_filename": record.get('original_filename'),
                "ingested_at": record.get('ingested_at'),
                **data_dict # Unpack the JSON data here
            }
            manifest.append(full_record)
            processed_guids.add(record.get('original_filename'))
        except json.JSONDecodeError:
            print(f"WARN: Could not parse JSON data for record: {record.get('saberis_id')}. Skipping.")
            continue

    client = SaberisAPIClient()
    unexported_docs = client.get_unexported_documents()

    if not unexported_docs:
        print("No new documents to ingest or API call failed.")
        manifest.sort(key=lambda r: r['ingested_at'], reverse=True)
        return manifest
        
    new_rows_to_append = []
    for doc_header in unexported_docs:
        doc_guid = doc_header.get("guid")
        if not doc_guid or doc_guid in processed_guids:
            continue
            
        print(f"Found new document: {doc_guid}. Fetching full data...")
        doc = client.get_export_document_by_id(doc_guid)

        if not doc:
            print(f"Failed to fetch document {doc_guid}")
            continue

        order_data = doc.get("SaberisOrderDocument", {}).get("Order", {})
        
        # This is the data we'll store in the JSON blob
        data_to_store = {
            "customer_name": order_data.get("Customer", {}).get("Name", "N/A"),
            "username": order_data.get("Username", "N/A"),
            "export_date": order_data.get("Date", "N/A"),
            "shipping_address": ", ".join(filter(None, [
                order_data.get("Shipping", {}).get('Address'),
                order_data.get("Shipping", {}).get('City'),
                order_data.get("Shipping", {}).get('StateOrProvince')
            ])),
            "sent_to_jobber": False,
            "raw_data": doc, # Store the entire original document
            "stored_path": "" # No longer used
        }

        # This is the row that gets written to the Google Sheet
        new_row = [
            str(uuid.uuid4()),      # saberis_id
            doc_guid,               # original_filename
            datetime.now().isoformat(), # ingested_at
            json.dumps(data_to_store) # The JSON blob
        ]
        new_rows_to_append.append(new_row)
        processed_guids.add(doc_guid)

    if new_rows_to_append:
        GSHEET_SABERIS_EXPORTS.append_rows(new_rows_to_append, value_input_option='USER_ENTERED')
        print(f"Successfully appended {len(new_rows_to_append)} new records to the Google Sheet.")
        # Re-fetch the manifest to include the newly added items
        return ingest_saberis_exports()

    manifest.sort(key=lambda r: r['ingested_at'], reverse=True)
    return manifest

def prune_saberis_exports(keep_count: int = 3) -> int:
    """
    Deletes the oldest Saberis export records from the Google Sheet, keeping
    only the specified number of most recent records.
    """
    print(f"INFO: Pruning exports, keeping the most recent {keep_count}.")
    all_records = GSHEET_SABERIS_EXPORTS.get_all_records()

    if len(all_records) <= keep_count:
        print("INFO: No records to prune.")
        return 0

    # Sort by ingested_at date, descending (newest first)
    all_records.sort(key=lambda r: r.get('ingested_at', ''), reverse=True)

    # Determine which rows to delete. The sheet is 1-indexed, plus a header row.
    # So, the index of a record in the list corresponds to `record_index + 2` in the sheet.
    num_to_delete = len(all_records) - keep_count
    start_index_to_delete = keep_count + 2 # +1 for header, +1 for 1-based index
    end_index_to_delete = start_index_to_delete + num_to_delete - 1

    GSHEET_SABERIS_EXPORTS.delete_rows(start_index_to_delete, end_index_to_delete)
    
    print(f"SUCCESS: Pruned {num_to_delete} old export records from the Google Sheet.")
    return num_to_delete