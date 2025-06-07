# jobber_models.py (Revised)
"""
Data models for Saberis and Jobber, and transformation logic.
"""
from __future__ import annotations  # Allows forward references for type hints

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
    """Represents a line item in a Saberis order."""
    type: str
    line_id: int
    description: str 
    quantity: float = 1.0
    list_price: float = 0.0
    cost: float = 0.0         

    # New fields to capture more data
    product_code: Optional[str] = None
    sku: Optional[str] = None
    uom: Optional[str] = None
    manufacturer_part_number: Optional[str] = None
    manufacturer_sku: Optional[str] = None
    volume: Optional[str] = None
    weight: Optional[str] = None
    product_type_saberis: Optional[str] = None # To store Saberis "ProductType"

    @staticmethod
    def from_json(obj: SaberisLineItemDict) -> SaberisLineItem:
        """Create a SaberisLineItem from a SaberisLineItemDict."""
        item_type_raw = obj.get("Type") or obj.get("type")
        item_type = str(item_type_raw or "")

        # Original description from Saberis (e.g., "W1539;L{10c}" or text content)
        saberis_description_content = obj.get("Description")
        if not saberis_description_content:
            saberis_description_content = obj.get("Text")
        parsed_saberis_description = str(saberis_description_content or "")
        
        #Line ID
        parsed_line_id: int
        gotten_line_id = obj.get("LineID")
        if gotten_line_id is None:
            parsed_line_id = -1
            print("Item ", parsed_saberis_description, " had no LineID")
        else:
            parsed_line_id = gotten_line_id
            

        if item_type.lower() == "text":
            return SaberisLineItem(type="Text", line_id=parsed_line_id, description=parsed_saberis_description)

        # For "Product" type items
        def safe_float(value: Any) -> float:
            if value is None or value == "": return 0.0
            try: return float(value)
            except (ValueError, TypeError): return 0.0

        line_id = int(obj.get("LineID") or -1)
        quantity_prod = safe_float(obj.get("Quantity", 1))
        list_price_prod = safe_float(obj.get("List", 0))
        cost_prod = safe_float(obj.get("Cost", 0))             # This becomes Jobber unitCost
        product_code_val = str(obj.get("ProductCode") or "")
        sku_val = str(obj.get("SKU") or "")
        uom_val = str(obj.get("UOM") or "")
        manu_part_num_val = str(obj.get("ManufacturerPartNumber") or "")
        manu_sku_val = str(obj.get("ManufacturerSKU") or "")
        volume_val = str(obj.get("Volume") or "")
        weight_val = str(obj.get("Weight") or "")
        product_type_saberis_val = str(obj.get("ProductType") or "")
        
        return SaberisLineItem(
            type="Product",
            line_id = line_id,
            description=parsed_saberis_description, # Original Saberis description
            quantity=quantity_prod,
            list_price=list_price_prod,
            cost=cost_prod,
            product_code=product_code_val if product_code_val else None,
            sku=sku_val if sku_val else None,
            uom=uom_val if uom_val else None,
            manufacturer_part_number=manu_part_num_val if manu_part_num_val else None,
            manufacturer_sku=manu_sku_val if manu_sku_val else None,
            volume=volume_val if volume_val else None,
            weight=weight_val if weight_val else None,
            product_type_saberis=product_type_saberis_val if product_type_saberis_val else None
        )
        # END OF MODIFIED CODE BLOCK 2

@dataclass
class SaberisOrder:
    """Represents a complete Saberis order."""
    username: str
    created_at: datetime
    customer_name: str
    shipping_address: ShippingAddress
    catalog_id: str
    group_style: str
    lines: List[SaberisLineItem] = field(default_factory=list) #type: ignore

    @classmethod
    def from_json(cls, doc: SaberisDocumentDict) -> SaberisOrder: # doc is the entire parsed JSON
        """Create a SaberisOrder from a SaberisDocumentDict."""

        saberis_order_document_node = doc.get("SaberisOrderDocument", {})
        order_node = saberis_order_document_node.get("Order", {})

        username = str(order_node.get("Username") or "unknown")
        date_str = str(order_node.get("Date") or "1970-01-01")
        try:
            created_at = datetime.strptime(date_str, "%Y.%m.%d")
        except (ValueError, TypeError):
            try:
                created_at = datetime.strptime(date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                print(f"Warning: Could not parse date '{date_str}'. Using 1970-01-01.")
                created_at = datetime(1970, 1, 1)

        customer_info = order_node.get("Customer", {})
        customer_name = str(customer_info.get("Name") or "Unnamed Client")

        shipping_raw = order_node.get("Shipping", {})
        
        # Extract StateOrProvince and determine country
        state_or_province_str = str(shipping_raw.get("StateOrProvince") or "").upper().strip()
        
        inferred_country = "US" # Default to USA
        if state_or_province_str in CANADIAN_PROVINCE_TERRITORY_CODES:
            inferred_country = "CA"

        ship_addr: ShippingAddress = {
            "street1": str(shipping_raw.get("Address") or ""),
            "street2": "",
            "city": str(shipping_raw.get("City") or ""),
            "province": state_or_province_str, # Store the processed state/province code
            "postalCode": str(shipping_raw.get("ZipOrPostal") or ""),
            "country": inferred_country,
        }

        processed_lines: List[SaberisLineItem] = []
        catalog_id_found: str = "Catalog ID not found"
        group_style_found: str = "No group style found"

        groups_data_from_json: Any = order_node.get("Group")

        if isinstance(groups_data_from_json, dict):
            single_group_dict: SaberisSingleGroupWithItemsDict = cast(SaberisSingleGroupWithItemsDict, groups_data_from_json)
            raw_lines_list: List[SaberisLineItemDict] = single_group_dict.get("Item", [])
            
            for raw_item_dict in raw_lines_list:
                if raw_item_dict:
                    processed_item = SaberisLineItem.from_json(raw_item_dict)
                    processed_lines.append(processed_item)
                    if "Catalog=" in processed_item.description:
                        catalog_id_found = processed_item.description.split("Catalog=")[1]
                        catalog_id_found = get_brand_if_available(catalog_id_found)
                    if int(processed_item.line_id) == 2:
                        print(processed_item.description)
                        group_style_found = processed_item.description.partition("Pricelevel=")[2] or processed_item.description

        elif isinstance(groups_data_from_json, list):
            list_of_group_dicts: List[SaberisGroupDict] = cast(List[SaberisGroupDict], groups_data_from_json)
            
            for group_dict_item in list_of_group_dicts:
                if group_dict_item:
                    raw_lines_list: List[SaberisLineItemDict] = group_dict_item.get("Line", [])
                    
                    for raw_item_dict in raw_lines_list:
                        if raw_item_dict:
                            processed_lines.append(SaberisLineItem.from_json(raw_item_dict))

        return cls(
            username=username,
            created_at=created_at,
            customer_name=customer_name,
            shipping_address=ship_addr,
            catalog_id=catalog_id_found,
            group_style=group_style_found,
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
    """Transforms a SaberisOrder into a Jobber QuoteCreateInput."""
    title = order.first_catalog_code()

    jobber_lines: List[QuoteLineInput] = []

    for li in order.lines:
        if li.type != "Product": continue

        # Construct human-readable name for Jobber
        product_name = order.catalog_id
        if li.description:
            product_name += " | " + remove_curly_braces_and_content(li.description)
        elif li.product_code:
            product_name += " product_id_missing_for: " + li.product_code
        else:
            product_name = "Unnamed Product"
        
        product_name += " | Style: " + order.group_style

        unit_cost_for_jobber = li.cost if li.cost > 0 else None # Saberis 'Cost' becomes Jobber 'unitCost'
        
        jobber_lines.append(
            QuoteLineInput(
                name=product_name,
                quantity=li.quantity,
                unit_price=li.cost,
                description= "Full item ID: " + li.description,
                unit_cost=unit_cost_for_jobber,
                taxable=False, 
            )
        )

    if not jobber_lines: # Ensure there's at least one line item
        jobber_lines.append(QuoteLineInput(name="Misc. Items", quantity=1.0, unit_price=0.0, save_to_products_and_services=False))

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