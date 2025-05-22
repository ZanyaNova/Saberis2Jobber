# jobber_models.py (Revised)
"""
Data models for Saberis and Jobber, and transformation logic.
"""
from __future__ import annotations  # Allows forward references for type hints

import hashlib
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, TypedDict, Optional, Any, Union, cast, Dict

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
    Customer: SaberisCustomerDict # This is correctly typed
    Shipping: SaberisShippingDict # Using the specific TypedDict if applicable, or Dict[str, Any] if truly varied

class SaberisLineItemDict(TypedDict, total=False):
    """Structure expected within a Saberis 'Line' object."""
    Type: str
    type: str
    Text: str
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
    description: str 
    quantity: float = 1.0
    list_price: float = 0.0
    selling_price: float = 0.0 
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

        if item_type.lower() == "text":
            return SaberisLineItem(type="Text", description=parsed_saberis_description)

        # For "Product" type items
        def safe_float(value: Any) -> float:
            if value is None or value == "": return 0.0
            try: return float(value)
            except (ValueError, TypeError): return 0.0

        # START OF MODIFIED CODE BLOCK 2 - Parsing new fields in SaberisLineItem.from_json
        quantity_prod = safe_float(obj.get("Quantity", 1))
        list_price_prod = safe_float(obj.get("List", 0))
        selling_price_prod = safe_float(obj.get("Selling", 0)) # This becomes Jobber unitPrice
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
            description=parsed_saberis_description, # Original Saberis description
            quantity=quantity_prod,
            list_price=list_price_prod,
            selling_price=selling_price_prod,
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

        groups_data_from_json: Any = order_node.get("Group")

        if isinstance(groups_data_from_json, dict):
            single_group_dict: SaberisSingleGroupWithItemsDict = cast(SaberisSingleGroupWithItemsDict, groups_data_from_json)
            raw_lines_list: List[SaberisLineItemDict] = single_group_dict.get("Item", [])
            
            for raw_item_dict in raw_lines_list:
                if raw_item_dict:
                    processed_lines.append(SaberisLineItem.from_json(raw_item_dict))

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
    message_lines: List[str] = []
    jobber_custom_fields: List[Dict[str, Any]] = []

    for li in order.lines:
        if li.type == "Text":
            if li.description.startswith("Catalog="):
                catalog_value = li.description.split("=", 1)[1].strip()
                jobber_custom_fields.append({
                    # TODO: Replace with actual customFieldConfigurationId from Jobber for "Saberis Catalog"
                    "customFieldConfigurationId": "placeholder_saberis_catalog_id",
                    "valueText": catalog_value
                })
            elif "=" in li.description: # For other key=value text lines
                key, value = li.description.split("=", 1)
                key = key.strip()
                value = value.strip()
                # TODO: Replace with actual customFieldConfigurationId from Jobber.
                # Might want a mapping from Saberis key (e.g., "Door Style") to a specific ID,
                # or a more generic "Saberis Attribute" custom field.
                jobber_custom_fields.append({
                    "customFieldConfigurationId": f"placeholder_saberis_attribute_{key.lower().replace(' ', '_')}_id",
                    "valueText": f"{key}: {value}" # Or just `value` if the key is implied by the Jobber CF
                })
                message_lines.append(li.description)
            else: 
                 message_lines.append(li.description)

    message = "\n".join(message_lines)

    jobber_lines: List[QuoteLineInput] = []

    for li in order.lines:
        if li.type != "Product": continue

        # Construct human-readable name for Jobber
        jobber_item_name = li.description # Default to original Saberis description
        if li.product_code and li.description:
            jobber_item_name = f"{li.product_code} ID: {li.description}"
        elif li.product_code:
            jobber_item_name = li.product_code
        elif li.description: # Fallback if only description is present
             jobber_item_name = li.description
        else: # Fallback if neither product_code nor description is present
            jobber_item_name = "Unnamed Product"


        # Construct the elaborate description string for Jobber
        desc_parts: List[str] = []
        if li.description: # Original Saberis "Description" field
            desc_parts.append(f"Orig. ID: {li.description}")
        if li.sku:
            desc_parts.append(f"SKU: {li.sku}")
        # Using list_price from SaberisLineItem, not selling_price which is Jobber's unit_price
        if li.list_price > 0: # Only add if there's a list price
            desc_parts.append(f"List: ${li.list_price:.2f}")
        # Cost is already mapped to unit_cost, but can be included if desired for visibility
        # if li.cost > 0:
        #     desc_parts.append(f"Cost: ${li.cost:.2f}")
        if li.product_type_saberis:
            desc_parts.append(f"Saberis Type: {li.product_type_saberis}")
        if li.uom:
            desc_parts.append(f"UOM: {li.uom}")
        if li.volume:
            desc_parts.append(f"Volume: {li.volume}")
        if li.weight:
            desc_parts.append(f"Weight: {li.weight}")
        if li.manufacturer_part_number:
            desc_parts.append(f"Manuf. P/N: {li.manufacturer_part_number}")
        if li.manufacturer_sku:
            desc_parts.append(f"Manuf. SKU: {li.manufacturer_sku}")
        
        jobber_item_description = " | ".join(desc_parts) if desc_parts else None

        unit_cost_for_jobber = li.cost if li.cost > 0 else None # Saberis 'Cost' becomes Jobber 'unitCost'
        
        jobber_lines.append(
            QuoteLineInput(
                name=jobber_item_name,
                quantity=li.quantity,
                unit_price=li.selling_price, # Saberis 'Selling' becomes Jobber 'unitPrice'
                description=jobber_item_description,
                unit_cost=unit_cost_for_jobber,
                taxable=False, # Defaulting taxable to False, adjust as needed
                # save_to_products_and_services=False # Set this if you added it to QuoteLineInput
            )
        )

    if not jobber_lines: # Ensure there's at least one line item
        jobber_lines.append(QuoteLineInput(name="Misc. Items", quantity=1.0, unit_price=0.0, save_to_products_and_services=False))

    # TODO: Get actual quoteNumber from spreadsheet or other source
    quote_num_placeholder: Optional[int] = 12345 # Placeholder for quote_number

    return QuoteCreateInput(
        client_id=client_id, property_id=property_id, title=title,
        message=message, line_items=jobber_lines,
        quote_number=quote_num_placeholder, # Added
        # TODO: Set a real contract disclaimer if needed, or load from config
        contract_disclaimer="Standard terms and conditions apply.", # Added, example
        custom_fields=jobber_custom_fields # Added
    )