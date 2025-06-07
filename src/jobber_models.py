# jobber_models.py (Revised)
"""
Data models for Saberis and Jobber, and transformation logic.
"""
from __future__ import annotations  # Allows forward references for type hints

import re
import hashlib
import json
from .gsheet.client_sheet_manager import get_brand_if_available
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, TypedDict, Optional, Any, Union, cast, Dict
from .text_utilities import remove_curly_braces_and_content

# ---------------------------------------------------------------------------
# Type Definitions for Saberis Input Structures (Raw JSON Parsing)
# ---------------------------------------------------------------------------

class SaberisShippingDict(TypedDict, total=False):
    """Structure expected within Saberis 'Shipping' field."""
    address: str
    city: str
    state: str
    postalCode: str
    country: str

class SaberisCustomerDict(TypedDict, total=False):
    """Structure expected within Saberis 'Customer' field."""
    Name: str

class SaberisHeaderDict(TypedDict, total=False):
    """Structure expected within Saberis 'Header' field."""
    Username: str
    Date: str
    Customer: SaberisCustomerDict 
    Shipping: SaberisShippingDict 
    
class SaberisLineItemDict(TypedDict, total=False):
    """Structure expected within a Saberis 'Line' object."""
    Type: str
    type: str
    Text: str
    LineID: int
    Description: str
    Quantity: Union[str, float, int]
    List: Union[str, float, int]
    Selling: Union[str, float, int]
    Cost: Union[str, float, int]

class SaberisGroupDict(TypedDict, total=False):
    """Structure expected within a Saberis 'Group' object."""
    Line: List[SaberisLineItemDict] # This is correctly typed

class SaberisSingleGroupWithItemsDict(TypedDict, total=False):
    """Structure for a single 'Group' object directly containing an 'Item' list."""
    GroupType: Optional[Any] # Or a more specific type for GroupType if known
    Item: List[SaberisLineItemDict] 

class SaberisDocumentDict(TypedDict, total=False):
    """Overall Saberis document structure."""
    Header: SaberisHeaderDict
    Group: List[SaberisGroupDict]

CANADIAN_PROVINCE_TERRITORY_CODES = {
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU",
    "ON", "PE", "QC", "SK", "YT"
}

FIELDs_TO_PUT_IN_TITLE = {
    "Door Selection", "Cabinet Style"
}

def _create_empty_str_dict() -> Dict[str, str]:
    """Helper to provide a typed empty dictionary for the dataclass factory."""
    return {}

# ---------------------------------------------------------------------------
# Saberis Application Models
# ---------------------------------------------------------------------------

class ShippingAddress(TypedDict):
    """Shipping address as stored and used by SaberisOrder."""
    street1: str
    street2: Optional[str]
    city: str
    province: str
    postalCode: str
    country: str

@dataclass
class SaberisLineItem:
    """
    Represents a product line item in a Saberis order, now enriched with 
    contextual data from its parent group in the original file.
    """
    # Core product data from the JSON object
    type: str
    line_id: int
    description: str  # Original description from the product line, e.g., "TP182484"
    quantity: float
    list_price: float
    cost: float
    
    # Contextual data from preceding "Text" lines that define the product's group
    catalog: str
    attributes: Dict[str, str]
    
    # Other existing fields
    product_code: Optional[str] = None
    sku: Optional[str] = None
    uom: Optional[str] = None
    manufacturer_part_number: Optional[str] = None
    manufacturer_sku: Optional[str] = None
    volume: Optional[str] = None
    weight: Optional[str] = None
    product_type_saberis: Optional[str] = None

    @staticmethod
    def from_json(obj: SaberisLineItemDict, context: Dict[str, str]) -> SaberisLineItem:
        """
        Create a SaberisLineItem from a raw dictionary, enriching it with
        context (catalog, style, etc.) gathered during the main parsing loop.
        
        This method should only be called for "Product" type items.
        """
        def safe_float(value: Any) -> float:
            if value is None or value == "": return 0.0
            try: return float(value)
            except (ValueError, TypeError): return 0.0
       
        context_copy = context.copy()
        popped_context = context_copy.pop("Catalog", None)

        # Create the base object with data from the line item itself
        item = SaberisLineItem(
            type="Product",
            catalog = popped_context or "Unknown Catalog",
            attributes= context_copy,
            line_id=int(obj.get("LineID") or -1),
            description=str(obj.get("Description") or ""),
            quantity=safe_float(obj.get("Quantity", 1.0)),
            list_price=safe_float(obj.get("List", 0.0)),
            cost=safe_float(obj.get("Cost", 0.0)),
            product_code=str(obj.get("ProductCode") or "") or None,
            sku=str(obj.get("SKU") or "") or None,
            uom=str(obj.get("UOM") or "") or None,
            manufacturer_part_number=str(obj.get("ManufacturerPartNumber") or "") or None,
            manufacturer_sku=str(obj.get("ManufacturerSKU") or "") or None,
            volume=str(obj.get("Volume") or "") or None,
            weight=str(obj.get("Weight") or "") or None,
            product_type_saberis=str(obj.get("ProductType") or "") or None
        )
        

        return item

@dataclass
class SaberisOrder:
    """Represents a complete Saberis order."""
    username: str
    created_at: datetime
    customer_name: str
    shipping_address: ShippingAddress
    lines: List[SaberisLineItem] = field(default_factory=list) #type: ignore

    @classmethod
    def from_json(cls, doc: SaberisDocumentDict) -> SaberisOrder:
        """Create a SaberisOrder from a SaberisDocumentDict."""
        
        saberis_order_document_node = doc.get("SaberisOrderDocument", {})
        order_node = saberis_order_document_node.get("Order", {})

        # ... (parsing for username, date, customer_name, shipping_address remains the same) ...
        username = str(order_node.get("Username") or "unknown")
        date_str = str(order_node.get("Date") or "1970-01-01")
        try:
            created_at = datetime.strptime(date_str, "%Y.%m.%d")
        except (ValueError, TypeError):
            created_at = datetime(1970, 1, 1) # Fallback

        customer_info = order_node.get("Customer", {})
        customer_name = str(customer_info.get("Name") or "Unnamed Client")

        shipping_raw = order_node.get("Shipping", {})
        ship_addr: ShippingAddress = {
            "street1": str(shipping_raw.get("Address") or ""),
            "street2": "",
            "city": str(shipping_raw.get("City") or ""),
            "province": str(shipping_raw.get("StateOrProvince") or ""),
            "postalCode": str(shipping_raw.get("ZipOrPostal") or ""),
            "country": "US", # Or logic to determine country
        }

        processed_lines: List[SaberisLineItem] = []
        
        # This context dictionary holds the state for the current group of products.
        # It will be updated as we iterate through the line items.
        context: Dict[str, str] = _create_empty_str_dict()

        # Unify the logic to get a single list of raw line items to process
        groups_data_from_json: Any = order_node.get("Group")
        raw_lines_list: List[SaberisLineItemDict] = []

        single_group_dict = cast(SaberisSingleGroupWithItemsDict, groups_data_from_json)
        raw_lines_list = single_group_dict.get("Item", [])

        # Helper regex Pattern looks for W=, H=, and D= and captures the numbers that follow.
        # It's flexible enough to handle spaces and the quote marks.
        dimension_pattern = re.compile(r'W=.*H=.*D=') #type:ignore

        # Process the unified list of raw line items
        for raw_item_dict in raw_lines_list:
            if not raw_item_dict:
                continue

            item_type = raw_item_dict.get("Type", "").lower()
            description = raw_item_dict.get("Description", "")

            # If it's a "Text" line, check if it sets a context attribute
            if item_type == "text" and "=" in description:
                if dimension_pattern.search(description): #type:ignore
                    continue

                try:
                    key, value = description.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    if key == "Catalog":
                        context[key] = get_brand_if_available(value)
                    else:
                        context[key] = value

                except ValueError:
                    # Not a key-value pair, ignore
                    pass
            
            # If it's a "Product" line, create an enriched item using the current context
            elif item_type == "product":
                processed_item = SaberisLineItem.from_json(raw_item_dict, context.copy())
                processed_lines.append(processed_item)

        return cls(
            username=username,
            created_at=created_at,
            customer_name=customer_name,
            shipping_address=ship_addr,
            lines=processed_lines,
        )

    def first_catalog_code(self) -> str:
        for li in self.lines:
            if li.type == "Text" and li.description.startswith("Catalog="):
                parts = li.description.split("=", 1)
                if len(parts) > 1: return parts[1].strip()
        return "NA"

    def unique_key(self) -> str:
        payload_dict = [asdict(li) for li in self.lines] # asdict works on dataclasses
        payload_str = json.dumps(payload_dict, sort_keys=True)
        payload_bytes = payload_str.encode('utf-8')
        md5_part = hashlib.md5(payload_bytes).hexdigest()[:4]
        date_str = self.created_at.strftime("%Y%m%d")
        catalog_code = self.first_catalog_code()
        return f"{self.username}_{date_str}_{catalog_code}_{md5_part}"

# ---------------------------------------------------------------------------
# Jobber Application Models (Dataclasses) - For Transformation Output
# ---------------------------------------------------------------------------
@dataclass
class QuoteLineInput: 
    """Represents a line item in a Jobber quote, application-level model."""
    name: str 
    quantity: float
    unit_price: float # Derived from Saberis 'Selling'
    description: Optional[str] = None # This will be the new elaborate string for Jobber
    unit_cost: Optional[float] = None # Derived from Saberis 'Cost'
    taxable: bool = False
    save_to_products_and_services: bool = False 

@dataclass
class QuoteCreateInput: 
    """Input for creating a Jobber quote, application-level model."""
    client_id: str
    property_id: str
    title: str
    message: str
    line_items: List[QuoteLineInput] = field(default_factory=list) #type: ignore
    quote_number: Optional[int] = None 
    contract_disclaimer: Optional[str] = None
    # Using Dict for simplicity here, will be strongly typed to GQL model in client module
    custom_fields: Optional[List[Dict[str, Any]]] = field(default_factory=list) #type: ignore


# ---------------------------------------------------------------------------
# Transformation Logic
# ---------------------------------------------------------------------------
def saberis_to_jobber(order: SaberisOrder, client_id: str, property_id: str) -> QuoteCreateInput:
    """Transforms a SaberisOrder into a Jobber QuoteCreateInput using generic attributes."""
    
    title = order.first_catalog_code() or "Cabinet Quote"
    jobber_lines: List[QuoteLineInput] = []

    for li in order.lines:
        if li.type != "Product":
            continue

        # --- Construct the Jobber line item NAME ---
        # The name still uses the specifically handled attributes.
        product_name_parts = [
            li.catalog,
            remove_curly_braces_and_content(li.description)
        ]

        # --- Construct the Jobber line item DESCRIPTION ---
        # This part is now fully generic and future-proof.
        description_parts: list[str] = []
        
        # Loop through the generic attributes dictionary and format them.
        for key, value in li.attributes.items():
            description_parts.append(f"{key}: {value}")
            if key in FIELDs_TO_PUT_IN_TITLE:
                product_name_parts.append(value)
        
        # Join name and job description arrays into one
        product_name = " | ".join(filter(None, product_name_parts))
        jobber_description = "\n".join(description_parts)

        jobber_lines.append(
            QuoteLineInput(
                name=product_name,
                quantity=li.quantity,
                unit_price=li.cost,
                description=jobber_description,
                unit_cost=li.cost if li.cost > 0 else None,
                taxable=False,
            )
        )

    if not jobber_lines:
        jobber_lines.append(QuoteLineInput(name="Misc. Items", quantity=1.0, unit_price=0.0))

    # TODO: Get actual quoteNumber from spreadsheet or other source
    quote_num_placeholder: Optional[int] = 12345 # Placeholder for quote_number

    return QuoteCreateInput(
        client_id=client_id, 
        property_id=property_id, 
        title=title,
        message="No message",
        line_items=jobber_lines,
        quote_number=quote_num_placeholder, # Added
        # TODO: Set a real contract disclaimer if needed, or load from config
        contract_disclaimer="Standard terms and conditions apply.", # Added, example
    )