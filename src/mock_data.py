# src/mock_data.py
from typing import List, TypedDict

class MockJobberQuote(TypedDict):
    """Represents the essential data for a Jobber Quote tile in the UI."""
    id: str
    client_name: str
    address: str
    approved_date: str
    total: str

def generate_mock_quotes() -> List[MockJobberQuote]:
    """
    Generates a static list of Jobber quotes for UI prototyping.
    In the future, this will be replaced by a real Jobber API call.
    """
    return [
        {
            "id": "jobber_quote_1",
            "client_name": "Affinity Homes",
            "address": "123 Main St, Anytown, USA",
            "approved_date": "2025-06-20",
            "total": "$15,250.00"
        },
        {
            "id": "jobber_quote_2",
            "client_name": "Burnich Construction",
            "address": "456 Oak Ave, Someville, USA",
            "approved_date": "2025-06-18",
            "total": "$32,100.50"
        },
        {
            "id": "jobber_quote_3",
            "client_name": "Meier Residences",
            "address": "789 Pine Ln, Otherplace, USA",
            "approved_date": "2025-06-15",
            "total": "$8,750.00"
        },
    ]