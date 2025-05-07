from __future__ import annotations
import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, List, Optional

# ---------------------------------------------------------------------------
# models.py (embedded)
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
    def from_json(obj: dict[str, Any]) -> "SaberisLineItem":
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
    def from_json(doc: dict[str, Any]) -> "SaberisOrder":
        header = doc.get("Header", {})
        shipping = header.get("Shipping", {}) or {}
        # Flatten address dict to always include the same keys
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

    # ---------------------------------------------------------------------
    # Helpers that the worker will use
    # ---------------------------------------------------------------------
    def first_catalog_code(self) -> str:
        for li in self.lines:
            if li.type == "Text" and li.description.startswith("Catalog="):
                return li.description.split("=", 1)[1]
        return "NA"

    def unique_key(self) -> str:
        """Human‑readable deterministic idempotency key."""
        payload = json.dumps([asdict(li) for li in self.lines], sort_keys=True).encode()
        md5_part = hashlib.md5(payload).hexdigest()[:4]
        return f"{self.username}_{self.created_at:%Y%m%d}_{self.first_catalog_code()}_{md5_part}"


# ---------------------------------------------------------------------------
# transform.py (embedded)
# ---------------------------------------------------------------------------
@dataclass
class QuoteLineInput:
    name: str
    quantity: float
    unit_price: float
    unit_cost: float | None = None
    taxable: bool = False


@dataclass
class QuoteCreateInput:
    client_id: str  # Jobber ID (or temp slug ― stubbed for now)
    property_id: str
    title: str
    message: str
    line_items: List[QuoteLineInput]


def saberis_to_jobber(order: SaberisOrder, client_id: str, property_id: str) -> QuoteCreateInput:
    # Title and message extraction ---------------------------------------
    title = order.first_catalog_code()
    message_lines: List[str] = []
    for li in order.lines:
        if li.type == "Text" and not li.description.startswith("Catalog="):
            message_lines.append(li.description)
    message = "\n".join(message_lines)

    # Line items ----------------------------------------------------------
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
        # Ensure quote isn't empty – create a placeholder $0 line
        jobber_lines.append(QuoteLineInput(name="Misc. Items", quantity=1, unit_price=0))

    return QuoteCreateInput(
        client_id=client_id,
        property_id=property_id,
        title=title,
        message=message,
        line_items=jobber_lines,
    )


# ---------------------------------------------------------------------------
# jobber_client.py (embedded)
# ---------------------------------------------------------------------------
class JobberClient:

    ENDPOINT = "https://api.getjobber.com/api/graphql"

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("JOBBER_TOKEN", "stub-token")

    # ––––– Internal helpers –––––
    def _post(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        import requests  # local import to keep optional dependency

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        payload = {"query": query, "variables": variables or {}}
        # NOTE: With token == "stub-token" this *will* 401; in the playground you
        # can paste the generated query + vars manually.
        resp = requests.post(self.ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            raise RuntimeError(data["errors"])
        return data["data"]

    # ––––– Public API –––––
    def create_client_and_property(self, order: SaberisOrder) -> tuple[str, str]:
        """Creates a new client + property.  Returns (client_id, property_id).

        NOTE: for this stub we generate dummy ids so downstream code can run
        without touching the network.  Replace with real GraphQL calls later.
        """
        fake_id = lambda prefix: f"{prefix}_{hash(order.unique_key()) & 0xFFFF:04x}"
        return fake_id("client"), fake_id("property")

    def create_and_send_quote(self, payload: QuoteCreateInput) -> str:
        """Creates a quote and immediately sends it (auto‑send).  Returns quote_id."""
        # Build variables according to Jobber's expected shape
        quote_lines = [
            {
                "description": li.name,
                "quantity": li.quantity,
                "unitPrice": li.unit_price,
                **({"unitCost": li.unit_cost} if li.unit_cost is not None else {}),
            }
            for li in payload.line_items
        ]
        variables = {
            "input": {
                "clientId": payload.client_id,
                "propertyId": payload.property_id,
                "title": payload.title,
                "message": payload.message,
                "lineItems": quote_lines,
                # Autodraft flag may be needed; Jobber docs unclear – we’ll try without.
            }
        }
        # -----------------------------------------------------------------
        # Quote creation mutation (educated guess)
        # -----------------------------------------------------------------
        create_mutation = """
        mutation QuoteCreate($input: QuoteCreateInput!) {
          quoteCreate(input: $input) {
            quote { id quoteNumber quoteStatus }
            userErrors { message path }
          }
        }
        """
        data = self._post(create_mutation, variables)
        quote = data["quoteCreate"]["quote"]
        quote_id = quote["id"]

        # -----------------------------------------------------------------
        # Auto‑send mutation (educated guess)
        # -----------------------------------------------------------------
        send_mutation = """
        mutation QuoteSend($id: ID!) {
          quoteSend(id: $id) {
            quote { id quoteStatus }
            userErrors { message path }
          }
        }
        """
        self._post(send_mutation, {"id": quote_id})
        return quote_id


# ---------------------------------------------------------------------------
# sheet_helpers.py (embedded) – upgrades to client_sheet_manager.py & sheet_logging.py
# ---------------------------------------------------------------------------
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    gspread = None  # type: ignore

class SheetContext:
    """Context mgr that opens the workbook once per poll cycle."""

    def __init__(self, sheet_key_env="GOOGLE_SHEET_KEY", creds_json_env="GOOGLE_SVC_CREDS"):
        self.sheet_key = os.getenv(sheet_key_env)
        self.creds_json = os.getenv(creds_json_env)
        if not (self.sheet_key and self.creds_json):
            raise RuntimeError("Google Sheets env vars not set – skipping Sheets ops.")
        self.gc = None
        self.wb = None

    def __enter__(self):
        if gspread is None:
            raise RuntimeError("gspread not installed.")
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(self.creds_json, scope)
        self.gc = gspread.authorize(creds)
        self.wb = self.gc.open_by_key(self.sheet_key)
        return self.wb

    def __exit__(self, exc_type, exc_val, exc_tb):
        # gspread doesn’t need explicit close
        pass


# ---------------------------------------------------------------------------
# worker.py (embedded)
# ---------------------------------------------------------------------------
POLL_SECONDS = 30


def poll_once(jobber: JobberClient) -> None:
    """One poll cycle – fetch *stub* Saberis docs, process, update sheets."""
    # TODO: Replace with real Saberis HTTP fetch; for now load sample JSON file(s)
    import glob, pathlib

    BASE_DIR = pathlib.Path(__file__).parent.parent
    DOC_DIR  = BASE_DIR / "example_docs"

    for path in glob.glob(str(DOC_DIR / "*.json")):
        doc = json.loads(pathlib.Path(path).read_text())
        order = SaberisOrder.from_json(doc)

        # Check dashboard (skipped for stub) –> assume new every time
        client_id, property_id = jobber.create_client_and_property(order)
        quote_payload = saberis_to_jobber(order, client_id, property_id)
        quote_id = jobber.create_and_send_quote(quote_payload)
        print(f"Created & sent quote {quote_id} for {order.unique_key()}")


# ---------------------------------------------------------------------------
# main guard
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    jc = JobberClient(token=os.getenv("JOBBER_TOKEN", "stub-token"))
    print("Starting Saberis → Jobber worker (stub‑auth mode). Press Ctrl‑C to exit.")
    try:
        while True:
            poll_once(jc)
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("Stopped.")
