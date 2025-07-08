# src/saberis_ingestion.py
import os
import json
import uuid
from datetime import datetime
from typing import List, TypedDict

from .saberis_api_client import SaberisAPIClient

# ... (Type Definitions for Saberis JSON remain the same) ...
class _SaberisShippingDict(TypedDict, total=False):
    Address: str
    City: str
    StateOrProvince: str

class _SaberisCustomerDict(TypedDict, total=False):
    Name: str

class _SaberisOrderDict(TypedDict, total=False):
    Username: str
    Date: str
    Customer: _SaberisCustomerDict
    Shipping: _SaberisShippingDict

class _SaberisOrderDocumentDict(TypedDict, total=False):
    Order: _SaberisOrderDict

class SaberisWrapperDict(TypedDict, total=False):
    SaberisOrderDocument: _SaberisOrderDocumentDict

class SaberisExportRecord(TypedDict):
    saberis_id: str
    original_filename: str # This will now be the Saberis doc GUID
    stored_path: str
    ingested_at: str
    export_date: str
    customer_name: str
    username: str
    shipping_address: str
    sent_to_jobber: bool

# Define file and directory paths
SRC_DIR: str = os.path.dirname(os.path.abspath(__file__))
PROCESSED_EXPORTS_DIR: str = os.path.join(SRC_DIR, "processed_exports")
MANIFEST_FILE: str = os.path.join(SRC_DIR, "saberis_exports.json")

def ingest_saberis_exports() -> List[SaberisExportRecord]:
    """
    Scans for new Saberis exports via the API, processes them, and updates the manifest.
    Returns the complete, sorted list of records.
    """
    os.makedirs(PROCESSED_EXPORTS_DIR, exist_ok=True)
    if not os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, 'w') as f:
            json.dump([], f)

    with open(MANIFEST_FILE, 'r') as f:
        manifest: List[SaberisExportRecord] = json.load(f)
        processed_guids = {record['original_filename'] for record in manifest}

    client = SaberisAPIClient()
    unexported_docs = client.get_unexported_documents()

    if not unexported_docs:
        print("No new documents to ingest or API call failed.")
        manifest.sort(key=lambda record: record['ingested_at'], reverse=True)
        return manifest
        
    for doc_header in unexported_docs:
        doc_guid = doc_header.get("guid") # Use 'guid' as the identifier
        if not doc_guid or doc_guid in processed_guids:
            continue
            
        print(f"Found new document: {doc_guid}. Fetching full data...")
        doc = client.get_export_document_by_id(doc_guid)

        if not doc:
            print(f"Failed to fetch document {doc_guid}")
            continue

        try:
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

            saberis_uuid = str(uuid.uuid4())
            destination_filename = f"{saberis_uuid}.json"
            destination_path = os.path.join(PROCESSED_EXPORTS_DIR, destination_filename)

            new_record: SaberisExportRecord = {
                "saberis_id": saberis_uuid,
                "original_filename": doc_guid, # Store the GUID
                "stored_path": destination_path,
                "ingested_at": datetime.now().isoformat(),
                "export_date": export_date,
                "customer_name": customer_name,
                "username": username,
                "shipping_address": shipping_address,
                "sent_to_jobber": False
            }

            with open(destination_path, 'w') as f:
                json.dump(doc, f, indent=2)

            manifest.append(new_record)
            processed_guids.add(doc_guid)
            print(f"Successfully ingested and stored: {doc_guid}")

        except (KeyError, IOError) as e:
            print(f"Error processing document {doc_guid}: {e}")

    with open(MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=4)
        
    manifest.sort(key=lambda record: record['ingested_at'], reverse=True)
    
    return manifest