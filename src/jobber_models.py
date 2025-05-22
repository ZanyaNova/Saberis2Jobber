# jobber_models.py (Revised)
"""
Data models for Saberis and Jobber, and transformation logic.
"""
from __future__ import annotations  # Allows forward references for type hints

import hashlib
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, TypedDict, Optional, Any, Union, cast

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

# ---------------------------------------------------------------------------
# Saberis Application Models
# ---------------------------------------------------------------------------

# Reverting to TypedDict for ShippingAddress as it was simple and likely original intent
class ShippingAddress(TypedDict):
    """Shipping address as stored and used by SaberisOrder."""
    address: str
    city: str
    state: str
    postalCode: str
    country: str

@dataclass
class SaberisLineItem: # Reverted name
    """Represents a line item in a Saberis order."""
    type: str
    description: str
    quantity: float = 1.0
    list_price: float = 0.0
    selling_price: float = 0.0
    cost: float = 0.0

    @staticmethod
    def from_json(obj: SaberisLineItemDict) -> SaberisLineItem: # Corrected signature for Pylance Error 4
        """Create a SaberisLineItem from a SaberisLineItemDict."""
        item_type_raw = obj.get("Type") or obj.get("type")
        item_type = str(item_type_raw or "")

        if item_type.lower() == "text":
            description = str(obj.get("Text") or "")
            return SaberisLineItem(type="Text", description=description)

        description_prod = str(obj.get("Description") or "Unnamed Product")

        def safe_float(value: Any) -> float:
            if value is None or value == "": return 0.0
            try: return float(value)
            except (ValueError, TypeError): return 0.0

        quantity_prod = safe_float(obj.get("Quantity", 1))
        list_price_prod = safe_float(obj.get("List", 0))
        selling_price_prod = safe_float(obj.get("Selling", 0))
        cost_prod = safe_float(obj.get("Cost", 0))

        return SaberisLineItem(
            type="Product", description=description_prod, quantity=quantity_prod,
            list_price=list_price_prod, selling_price=selling_price_prod, cost=cost_prod,
        )

@dataclass
class SaberisOrder: # Reverted name
    """Represents a complete Saberis order."""
    username: str
    created_at: datetime
    customer_name: str
    shipping_address: ShippingAddress # Using the TypedDict version
    lines: List[SaberisLineItem] = field(default_factory=list)

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
            # Fallback if the above fails, or if you want to keep the old %Y-%m-%d
            try:
                created_at = datetime.strptime(date_str, "%Y-%m-%d")
            except (ValueError, TypeError):
                print(f"Warning: Could not parse date '{date_str}'. Using 1970-01-01.")
                created_at = datetime(1970, 1, 1)

        customer_info = order_node.get("Customer", {})
        customer_name = str(customer_info.get("Name") or "Unnamed Client")

        shipping_raw = order_node.get("Shipping", {})
        ship_addr: ShippingAddress = {
            "address": str(shipping_raw.get("Address") or ""), # From JSON "Address"
            "city": str(shipping_raw.get("City") or ""),       # From JSON "City"
            "state": str(shipping_raw.get("StateOrProvince") or ""), # From JSON "StateOrProvince"
            "postalCode": str(shipping_raw.get("ZipOrPostal") or ""), # From JSON "ZipOrPostal"
            "country": str(shipping_raw.get("country") or "USA"),
        }

        processed_lines: List[SaberisLineItem] = [] # Initialize an empty list for SaberisLineItem objects

        groups_data_from_json: Any = order_node.get("Group")

        if isinstance(groups_data_from_json, dict):

            single_group_dict: SaberisSingleGroupWithItemsDict = cast(SaberisSingleGroupWithItemsDict, groups_data_from_json)
            raw_lines_list: List[SaberisLineItemDict] = single_group_dict.get("Item", [])
            
            for raw_item_dict in raw_lines_list:
                if raw_item_dict:
                    processed_lines.append(SaberisLineItem.from_json(raw_item_dict))

        elif isinstance(groups_data_from_json, list): #TODO Determine if this is a redundant check, cus saberis may not actually do this.
            # Case 2: "Group" is a list of group dictionaries.
            # Each dictionary in this list is expected to be SaberisGroupDict compatible.
            list_of_group_dicts: List[SaberisGroupDict] = cast(List[SaberisGroupDict], groups_data_from_json)
            
            for group_dict_item in list_of_group_dicts:
                if group_dict_item: # Check if the group dictionary item is not None
                    # Each SaberisGroupDict is expected to have its line items under a "Line" key.
                    raw_lines_list: List[SaberisLineItemDict] = group_dict_item.get("Line", [])
                    
                    for raw_item_dict in raw_lines_list:
                        # raw_item_dict is expected to be SaberisLineItemDict compatible
                        if raw_item_dict: # Check if the item dictionary is not None or empty
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
class QuoteLineInput: # Reverted name
    """Represents a line item in a Jobber quote, application-level model."""
    name: str
    quantity: float
    unit_price: float
    unit_cost: Optional[float] = None
    taxable: bool = False

@dataclass
class QuoteCreateInput: # Reverted name
    """Input for creating a Jobber quote, application-level model."""
    client_id: str
    property_id: str
    title: str
    message: str
    line_items: List[QuoteLineInput] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Transformation Logic
# ---------------------------------------------------------------------------
def saberis_to_jobber(order: SaberisOrder, client_id: str, property_id: str) -> QuoteCreateInput: 
    """Transforms a SaberisOrder into a Jobber QuoteCreateInput."""
    title = order.first_catalog_code()
    message_lines: List[str] = []
    for li in order.lines:
        if li.type == "Text" and not li.description.startswith("Catalog="):
            message_lines.append(li.description)
    message = "\n".join(message_lines)

    jobber_lines: List[QuoteLineInput] = []
    for li in order.lines:
        if li.type != "Product": continue
        unit_cost = li.cost if li.cost > 0 else None
        jobber_lines.append(
            QuoteLineInput(
                name=li.description, quantity=li.quantity, unit_price=li.selling_price,
                unit_cost=unit_cost, taxable=False,
            )
        )
    if not jobber_lines:
        jobber_lines.append(QuoteLineInput(name="Misc. Items", quantity=1.0, unit_price=0.0))

    return QuoteCreateInput(
        client_id=client_id, property_id=property_id, title=title,
        message=message, line_items=jobber_lines,
    )