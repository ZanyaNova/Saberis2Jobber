# src/saberis_ingestion.py

import os
import json
import uuid
import shutil
from datetime import datetime
from typing import List, TypedDict

# ---------------------------------------------------------------------------
# Type Definitions for the Saberis JSON structure we are ingesting
# ---------------------------------------------------------------------------

# By defining these types, we inform Pylance of the expected data shape.
class _SaberisShippingDict(TypedDict, total=False):
    Address: str
    City: str
    StateOrProvince: str
    # ... other fields we don't need for ingestion

class _SaberisCustomerDict(TypedDict, total=False):
    Name: str
    # ... other fields

class _SaberisOrderDict(TypedDict, total=False):
    Username: str
    Date: str
    Customer: _SaberisCustomerDict
    Shipping: _SaberisShippingDict
    # ... other fields

class _SaberisOrderDocumentDict(TypedDict, total=False):
    Order: _SaberisOrderDict

class _SaberisWrapperDict(TypedDict, total=False):
    SaberisOrderDocument: _SaberisOrderDocumentDict

# ---------------------------------------------------------------------------
# Main Ingestion Logic
# ---------------------------------------------------------------------------

# This is the TypedDict we defined in the previous step
class SaberisExportRecord(TypedDict):
    saberis_id: str
    original_filename: str
    stored_path: str
    ingested_at: str
    export_date: str
    customer_name: str
    username: str
    shipping_address: str
    sent_to_jobber: bool

# Define file and directory paths
SRC_DIR: str = os.path.dirname(os.path.abspath(__file__))
EXAMPLE_DOCS_DIR: str = os.path.join(SRC_DIR, "example_docs")
PROCESSED_EXPORTS_DIR: str = os.path.join(SRC_DIR, "processed_exports")
MANIFEST_FILE: str = os.path.join(SRC_DIR, "saberis_exports.json")

def ingest_saberis_exports() -> List[SaberisExportRecord]:
    """
    Scans the example_docs folder, processes new JSON files, and updates the manifest.
    Returns the complete, sorted list of records.
    """
    os.makedirs(PROCESSED_EXPORTS_DIR, exist_ok=True)
    if not os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, 'w') as f:
            json.dump([], f)

    with open(MANIFEST_FILE, 'r') as f:
        manifest: List[SaberisExportRecord] = json.load(f)

    for filename in os.listdir(EXAMPLE_DOCS_DIR):
        if filename.endswith(".json"):
            source_path = os.path.join(EXAMPLE_DOCS_DIR, filename)
            
            try:
                with open(source_path, 'r') as f:
                    # Cast the loaded JSON to our new typed dictionary
                    doc: _SaberisWrapperDict = json.load(f)
                
                # Now, Pylance understands the structure, and '.get' is fully typed.
                # We use .get() for safety in case a key is missing.
                order_data = doc.get("SaberisOrderDocument", {}).get("Order", {})
                
                customer_name = order_data.get("Customer", {}).get("Name", "N/A")
                username = order_data.get("Username", "N/A")
                export_date = order_data.get("Date", "N/A")
                
                shipping = order_data.get("Shipping", {})
                address_parts = [
                    shipping.get('Address'),
                    shipping.get('City'),
                    shipping.get('StateOrProvince')
                ]
                shipping_address = ", ".join(part for part in address_parts if part)
                saberis_id = str(uuid.uuid4())
                destination_filename = f"{saberis_id}.json"
                destination_path = os.path.join(PROCESSED_EXPORTS_DIR, destination_filename)

                new_record: SaberisExportRecord = {
                    "saberis_id": saberis_id,
                    "original_filename": filename,
                    "stored_path": destination_path,
                    "ingested_at": datetime.now().isoformat(),
                    "export_date": export_date,
                    "customer_name": customer_name,
                    "username": username,
                    "shipping_address": shipping_address,
                    "sent_to_jobber": False
                }

                shutil.move(source_path, destination_path)
                manifest.append(new_record)
                print(f"Successfully ingested: {filename}")

            except (json.JSONDecodeError, KeyError, IOError) as e:
                print(f"Error processing file {filename}: {e}")

    with open(MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=4)
        
    manifest.sort(key=lambda record: record['ingested_at'], reverse=True)
    
    return manifest