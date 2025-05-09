"""
Data models for Saberis and Jobber, and transformation logic.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# Saberis Models
# ---------------------------------------------------------------------------
@dataclass
class SaberisLineItem:
    type: str  
    description: str
    quantity: float = 1.0
    list_price: float = 0.0
    selling_price: float = 0.0
    cost: float = 0.0

    @staticmethod
    def from_json(obj: dict[str, Any]) -> SaberisLineItem:
        item_type = obj.get("Type") or obj.get("type")
        if item_type == "Text":
            return SaberisLineItem(type="Text", description=obj.get("Text", ""))
        # Assume "Product"
        return SaberisLineItem(
            type="Product",
            description=obj.get("Description", "Unnamed Product"),
            quantity=float(obj.get("Quantity", 1)),
            list_price=float(obj.get("List", 0)),
            selling_price=float(obj.get("Selling", 0)),
            cost=float(obj.get("Cost", 0)),
        )

@dataclass
class SaberisOrder:
    username: str
    created_at: datetime
    customer_name: str
    shipping_address: dict[str, str]
    lines: List[SaberisLineItem]

    @staticmethod
    def from_json(doc: dict[str, Any]) -> SaberisOrder:
        header = doc.get("Header", {})
        shipping = header.get("Shipping", {}) or {}
        ship_addr = {k: shipping.get(k, "") for k in ("address", "city", "state", "postalCode", "country")}
        lines: List[SaberisLineItem] = []
        for group in doc.get("Group", []):
            for raw in group.get("Line", []):
                lines.append(SaberisLineItem.from_json(raw))
        return SaberisOrder(
            username=header.get("Username", "unknown"),
            created_at=datetime.strptime(header.get("Date", "1970-01-01"), "%Y-%m-%d"),
            customer_name=header.get("Customer", {}).get("Name", "Unnamed Client"),
            shipping_address=ship_addr,
            lines=lines,
        )

    def first_catalog_code(self) -> str:
        for li in self.lines:
            if li.type == "Text" and li.description.startswith("Catalog="):
                return li.description.split("=", 1)[1]
        return "NA"

    def unique_key(self) -> str:
        payload = json.dumps([asdict(li) for li in self.lines], sort_keys=True).encode()
        md5_part = hashlib.md5(payload).hexdigest()[:4]
        return f"{self.username}_{self.created_at:%Y%m%d}_{self.first_catalog_code()}_{md5_part}"

# ---------------------------------------------------------------------------
# Jobber Transformation Models & Logic
# ---------------------------------------------------------------------------
@dataclass
class QuoteLineInput:
    name: str
    quantity: float
    unit_price: float
    unit_cost: Optional[float] = None 
    taxable: bool = False

@dataclass
class QuoteCreateInput:
    client_id: str
    property_id: str
    title: str
    message: str
    line_items: List[QuoteLineInput]

def saberis_to_jobber(order: SaberisOrder, client_id: str, property_id: str) -> QuoteCreateInput:
    title = order.first_catalog_code()
    message_lines: List[str] = []
    for li in order.lines:
        if li.type == "Text" and not li.description.startswith("Catalog="):
            message_lines.append(li.description)
    message = "\n".join(message_lines)

    jobber_lines: List[QuoteLineInput] = []
    for li in order.lines:
        if li.type != "Product":
            continue
        jobber_lines.append(
            QuoteLineInput(
                name=li.description,
                quantity=li.quantity,
                unit_price=li.selling_price,
                unit_cost=li.cost if li.cost else None, 
                taxable=False,
            )
        )
    if not jobber_lines:
        jobber_lines.append(QuoteLineInput(name="Misc. Items", quantity=1, unit_price=0))

    return QuoteCreateInput(
        client_id=client_id,
        property_id=property_id,
        title=title,
        message=message,
        line_items=jobber_lines,
    )