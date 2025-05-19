# jobber_client_module.py (Revised with Pylance error fixes)
"""
Jobber API Client for making GraphQL requests.
Integrates with jobber_auth_flow to use valid access tokens.
"""
import requests
from typing import Any, Optional, Tuple, List, TypedDict, Union, Dict, cast # Added cast

# Import application-level models from jobber_models
from jobber_models import SaberisOrder, QuoteCreateInput, SaberisLineItem, QuoteLineInput, ShippingAddress

# --- Assumed external configurations and functions ---
JOBBER_GRAPHQL_URL = "https://api.getjobber.com/api/graphql"

def get_valid_access_token_placeholder() -> Optional[str]:
    return "dummy_valid_access_token_for_client_module"

def clear_tokens_placeholder() -> None:
    print("Auth: Tokens would be cleared here (placeholder in jobber_client_module).")


# --- GraphQL TypedDicts (Specific to Jobber API Structure) ---
# (These GQL TypedDicts remain unchanged)
# --- General GraphQL Structures ---
class GraphQLErrorLocation(TypedDict, total=False): line: int; column: int
class GraphQLErrorExtension(TypedDict, total=False): code: str
class GraphQLErrorDetail(TypedDict):
    message: str
    path: Optional[List[Union[str, int]]]
    locations: Optional[List[GraphQLErrorLocation]]
    extensions: Optional[GraphQLErrorExtension]
class GraphQLResponseWrapper(TypedDict):
    data: Optional[Dict[str, Any]]
    errors: Optional[List[GraphQLErrorDetail]]
class UserError(TypedDict): message: str; path: List[Union[str, int]]

# --- Client Creation GQL TypedDicts ---
class ClientEmailInputGQL(TypedDict, total=False): address: str; primary: Optional[bool]
class ClientPhoneInputGQL(TypedDict, total=False): number: str; primary: Optional[bool]; type: Optional[str]
class ClientMutationInputGQL(TypedDict, total=False):
    name: str; firstName: Optional[str]; lastName: Optional[str]
    emails: Optional[List[ClientEmailInputGQL]]; phones: Optional[List[ClientPhoneInputGQL]]
class ClientCreateVariablesGQL(TypedDict): input: ClientMutationInputGQL
class ClientObjectGQL(TypedDict): id: str; name: str
class ClientCreateDataPayloadGQL(TypedDict): client: Optional[ClientObjectGQL]; userErrors: Optional[List[UserError]]
class ClientCreateResponseDataGQL(TypedDict): clientCreate: Optional[ClientCreateDataPayloadGQL]

# --- Property Creation GQL TypedDicts ---
class PropertyAddressInputGQL(TypedDict, total=False):
    street: Optional[str]; street2: Optional[str]; city: Optional[str]
    province: Optional[str]; postalCode: Optional[str]; country: Optional[str]
class PropertyMutationInputGQL(TypedDict): clientId: str; address: PropertyAddressInputGQL
class PropertyCreateVariablesGQL(TypedDict): input: PropertyMutationInputGQL
class PropertyObjectGQL(TypedDict): id: str; address: Optional[PropertyAddressInputGQL]
class PropertyCreateDataPayloadGQL(TypedDict): property: Optional[PropertyObjectGQL]; userErrors: Optional[List[UserError]]
class PropertyCreateResponseDataGQL(TypedDict): propertyCreate: Optional[PropertyCreateDataPayloadGQL]

# --- Quote Line Item for GQL Mutation ---
class QuoteLineItemGQL(TypedDict, total=False):
    description: str; quantity: float; unitPrice: float
    unitCost: Optional[float]; taxable: Optional[bool]

# --- Quote Creation GQL TypedDicts ---
class QuoteCreationOptionsGQL(TypedDict, total=False): draft: Optional[bool]
class QuoteMutationInputGQL(TypedDict, total=False):
    clientId: str; propertyId: str; title: str; message: Optional[str]
    lineItems: List[QuoteLineItemGQL]; creationOptions: Optional[QuoteCreationOptionsGQL]
class QuoteCreateVariablesGQL(TypedDict): input: QuoteMutationInputGQL
class QuoteObjectGQL(TypedDict): id: str; quoteNumber: Optional[str]; quoteStatus: str
class QuoteCreateDataPayloadGQL(TypedDict): quote: Optional[QuoteObjectGQL]; userErrors: Optional[List[UserError]]
class QuoteCreateResponseDataGQL(TypedDict): quoteCreate: Optional[QuoteCreateDataPayloadGQL]

# --- Quote Sending GQL TypedDicts ---
class QuoteSendByIdVariablesGQL(TypedDict): quoteId: str
class QuoteSendDataPayloadGQL(TypedDict): quote: Optional[QuoteObjectGQL]; userErrors: Optional[List[UserError]]
class QuoteSendResponseDataGQL(TypedDict): quoteSend: Optional[QuoteSendDataPayloadGQL]

GraphQLMutationVariables = Union[
    ClientCreateVariablesGQL, PropertyCreateVariablesGQL, QuoteCreateVariablesGQL,
    QuoteSendByIdVariablesGQL, Dict[str, Any]
]
GraphQLData = Dict[str, Any]


class JobberClient:
    def __init__(self, api_version: str = "2025-01-20"):
        self.api_version = api_version
        self.access_token: Optional[str] = None
        self._get_valid_access_token_func = get_valid_access_token_placeholder
        self._clear_tokens_func = clear_tokens_placeholder

    def _get_headers(self) -> Dict[str, str]:
        if not self.access_token:
            self.access_token = self._get_valid_access_token_func()
        if not self.access_token:
            raise ConnectionRefusedError(
                "Jobber API: No valid access token available. Please authorize the application."
            )
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "X-JOBBER-GRAPHQL-VERSION": self.api_version,
        }

    def _post(self, query: str, variables: Optional[GraphQLMutationVariables] = None) -> GraphQLData:
        headers = self._get_headers()
        payload: Dict[str, Any] = {"query": query, "variables": variables or {}}
        resp: Optional[requests.Response] = None
        try:
            resp = requests.post(JOBBER_GRAPHQL_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            gql_response: GraphQLResponseWrapper = resp.json()

            # Fix for Pylance Error 1:
            errors_list = gql_response.get("errors")
            if errors_list: # Check if the list exists and is not empty (truthy)
                error_messages = [err.get('message', 'Unknown GraphQL error') for err in errors_list]
                error_detail = f"GraphQL errors for query '{query[:100]}...': {'; '.join(error_messages)}. Full errors: {errors_list}"
                print(error_detail)
                raise RuntimeError(error_detail)

            response_data = gql_response.get("data")
            if response_data is None:
                raise RuntimeError(f"GraphQL response missing 'data' key or 'data' is null, and no top-level errors. Response: {gql_response}")
            return response_data

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                print("Jobber API call returned 401 Unauthorized. Token might be invalid or expired.")
                self._clear_tokens_func()
                self.access_token = None
                raise ConnectionRefusedError(
                    "Jobber API: Token became unauthorized during use. Please re-authorize."
                ) from e
            error_text = e.response.text if e.response is not None else str(e)
            print(f"Jobber API HTTPError: {e.response.status_code if e.response else 'N/A'} - {error_text}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"Network request to Jobber API failed: {e}")
            raise
        except ValueError as e:
            status_code_info = f"Status: {resp.status_code}" if resp is not None else "Status: N/A (resp not available)"
            response_text_snippet = resp.text[:200] if resp is not None else "N/A"
            raise RuntimeError(f"Jobber API did not return valid JSON. {status_code_info}. Response snippet: {response_text_snippet}") from e

    def create_client_and_property(self, order: SaberisOrder) -> Tuple[str, str]:
        client_name = order.customer_name
        client_create_mutation = """
        mutation ClientCreate($input: ClientCreateInput!) {
          clientCreate(input: $input) { client { id name } userErrors { message path } }
        }"""
        client_mutation_input_gql: ClientMutationInputGQL = {"name": client_name}
        client_variables: ClientCreateVariablesGQL = {"input": client_mutation_input_gql}
        client_id: str
        try:
            raw_client_response_data: GraphQLData = self._post(client_create_mutation, client_variables)
            client_create_payload_dict = raw_client_response_data.get("clientCreate")
            if not isinstance(client_create_payload_dict, dict):
                raise RuntimeError(f"Unexpected response structure for clientCreate: {raw_client_response_data}")
            client_create_data: ClientCreateDataPayloadGQL = client_create_payload_dict # type: ignore
            user_errors = client_create_data.get("userErrors")
            if user_errors:
                error_messages = [f"{e.get('path', 'N/A')}: {e.get('message', 'Unknown error')}" for e in user_errors]
                raise RuntimeError(f"Error creating Jobber client: {'; '.join(error_messages)}")
            client_object = client_create_data.get("client")
            if not client_object or not client_object.get("id"):
                raise RuntimeError(f"Client creation response missing client ID or client object: {client_create_data}")
            client_id = client_object["id"]
            print(f"Successfully created Jobber client '{client_name}' with ID: {client_id}")
        except Exception as e:
            print(f"Failed to create Jobber client for '{client_name}': {e}")
            raise

        property_create_mutation = """
        mutation PropertyCreate($input: PropertyCreateInput!) {
          propertyCreate(input: $input) { property { id address { street city province postalCode } } userErrors { message path } }
        }"""
        saberis_addr: ShippingAddress = order.shipping_address
        temp_property_address: Dict[str, Any] = { # Use a temporary general dict
            "street": saberis_addr.get("address"),
            "city": saberis_addr.get("city"),
            "province": saberis_addr.get("state"),
            "postalCode": saberis_addr.get("postalCode"),
            "country": saberis_addr.get("country")
        }
        # Fix for Pylance Error 2 (Part 1: Create a new dict correctly typed for filtering)
        # The result of the comprehension is a standard dict, not PropertyAddressInputGQL.
        filtered_address_dict = {k: v for k, v in temp_property_address.items() if v is not None and v != ""} # Also filter empty strings

        # Fix for Pylance Error 2 (Part 2: Cast the filtered dict to the specific TypedDict)
        # This tells Pylance we are confident the filtered dict conforms to PropertyAddressInputGQL.
        # Note: This assumes that PropertyAddressInputGQL allows for missing fields (total=False).
        property_address_gql: PropertyAddressInputGQL = cast(PropertyAddressInputGQL, filtered_address_dict)

        property_mutation_input_gql: PropertyMutationInputGQL = {
            "clientId": client_id,
            "address": property_address_gql # Now correctly typed
        }
        property_variables: PropertyCreateVariablesGQL = {"input": property_mutation_input_gql}
        property_id: str
        try:
            raw_property_response_data: GraphQLData = self._post(property_create_mutation, property_variables)
            property_create_payload_dict = raw_property_response_data.get("propertyCreate")
            if not isinstance(property_create_payload_dict, dict):
                raise RuntimeError(f"Unexpected response structure for propertyCreate: {raw_property_response_data}")
            property_create_data: PropertyCreateDataPayloadGQL = property_create_payload_dict # type: ignore
            user_errors = property_create_data.get("userErrors")
            if user_errors:
                error_messages = [f"{e.get('path', 'N/A')}: {e.get('message', 'Unknown error')}" for e in user_errors]
                raise RuntimeError(f"Error creating Jobber property: {'; '.join(error_messages)}")
            property_object = property_create_data.get("property")
            if not property_object or not property_object.get("id"):
                raise RuntimeError(f"Property creation response missing property ID or property object: {property_create_data}")
            property_id = property_object["id"]
            print(f"Successfully created Jobber property for client {client_id} with ID: {property_id}")
        except Exception as e:
            print(f"Failed to create Jobber property for client {client_id}: {e}")
            raise
        return client_id, property_id

    def create_and_send_quote(self, app_quote_payload: QuoteCreateInput) -> str:
        quote_lines_for_gql: List[QuoteLineItemGQL] = []
        for li_model in app_quote_payload.line_items:
            item_gql: QuoteLineItemGQL = {
                "description": li_model.name,
                "quantity": li_model.quantity,
                "unitPrice": li_model.unit_price,
            }
            if li_model.unit_cost is not None:
                item_gql["unitCost"] = li_model.unit_cost

            # Fix for Pylance Error 3:
            # li_model.taxable is bool, QuoteLineItemGQL.taxable is Optional[bool].
            # Direct assignment is fine. The "is not None" check was incorrect for a non-Optional bool.
            item_gql["taxable"] = li_model.taxable

            quote_lines_for_gql.append(item_gql)

        quote_mutation_input_gql: QuoteMutationInputGQL = {
            "clientId": app_quote_payload.client_id,
            "propertyId": app_quote_payload.property_id,
            "title": app_quote_payload.title,
            "message": app_quote_payload.message,
            "lineItems": quote_lines_for_gql,
        }
        variables_create: QuoteCreateVariablesGQL = {"input": quote_mutation_input_gql}
        create_mutation = """
        mutation QuoteCreate($input: QuoteCreateInput!) {
          quoteCreate(input: $input) { quote { id quoteNumber quoteStatus } userErrors { message path } }
        }"""
        print(f"Creating quote with title: '{app_quote_payload.title}' for client: {app_quote_payload.client_id}")
        raw_data_create: GraphQLData = self._post(create_mutation, variables_create)

        quote_create_payload_dict = raw_data_create.get("quoteCreate")
        if not isinstance(quote_create_payload_dict, dict):
             raise RuntimeError(f"Quote creation response missing 'quoteCreate' key or not a dict. Response: {raw_data_create}")
        quote_create_result: QuoteCreateDataPayloadGQL = quote_create_payload_dict # type: ignore
        user_errors_create = quote_create_result.get("userErrors")
        if user_errors_create:
            error_messages = [f"{e.get('path', 'N/A')}: {e.get('message', 'Unknown error')}" for e in user_errors_create]
            raise RuntimeError(f"Quote creation failed. Errors: {'; '.join(error_messages)}. Input: {variables_create}")
        quote_object = quote_create_result.get("quote")
        if not quote_object or not quote_object.get("id"):
            raise RuntimeError(f"Quote creation response missing quote object or quote ID. Response: {quote_create_result}")
        quote_id: str = quote_object["id"]
        print(f"Quote created with ID: {quote_id}. Status: {quote_object.get('quoteStatus')}. Now sending.")

        send_mutation = """
        mutation QuoteSend($quoteId: ID!) {
          quoteSend(id: $quoteId) { quote { id quoteStatus } userErrors { message path } }
        }"""
        variables_send: QuoteSendByIdVariablesGQL = {"quoteId": quote_id}
        try:
            raw_data_send: GraphQLData = self._post(send_mutation, variables_send)
            quote_send_payload_dict = raw_data_send.get("quoteSend")
            if not isinstance(quote_send_payload_dict, dict):
                print(f"Warning: Quote sending response for {quote_id} missing 'quoteSend' key or not a dict. Response: {raw_data_send}")
                return quote_id
            send_result: QuoteSendDataPayloadGQL = quote_send_payload_dict # type: ignore
            user_errors_send = send_result.get("userErrors")
            if user_errors_send:
                error_messages = [f"{e.get('path', 'N/A')}: {e.get('message', 'Unknown error')}" for e in user_errors_send]
                print(f"Warning: Quote sending for {quote_id} encountered errors: {'; '.join(error_messages)}. Response: {send_result}")
            else:
                sent_quote_details = send_result.get("quote")
                new_status = sent_quote_details["quoteStatus"] if sent_quote_details else "Unknown"
                print(f"Quote {quote_id} sent successfully. New status: {new_status}")
        except Exception as e:
            print(f"Warning: Failed to send quote {quote_id} after creation due to an error: {e}")
        return quote_id

# Example Usage (Illustrative)
if __name__ == "__main__":
    from datetime import datetime

    client = JobberClient()
    sample_shipping_addr: ShippingAddress = {
        "address": "123 Example St", "city": "Exampleville", "state": "EX",
        "postalCode": "E1X 2M3", "country": "EXA"
    }
    sample_saberis_order = SaberisOrder(
        username="testuser_client", created_at=datetime.now(),
        customer_name="Example Construction Inc.", shipping_address=sample_shipping_addr,
        lines=[SaberisLineItem(type="Product", description="Foundation Work", quantity=1, selling_price=1500.00)]
    )
    created_client_id: Optional[str] = None
    created_property_id: Optional[str] = None
    try:
        print("\n--- Testing Client and Property Creation ---")
        created_client_id, created_property_id = client.create_client_and_property(sample_saberis_order)
        print(f"Test: Created Client ID: {created_client_id}, Property ID: {created_property_id}")

        if created_client_id and created_property_id:
             sample_quote_app_payload = QuoteCreateInput(
                 client_id=created_client_id, property_id=created_property_id,
                 title="Project Estimate Alpha", message="Estimate for the initial phase of construction.",
                 line_items=[QuoteLineInput(name="Site Prep", quantity=1.0, unit_price=250.00, taxable=False)]
             )
             try:
                 print("\n--- Testing Quote Creation and Sending ---")
                 created_quote_id = client.create_and_send_quote(sample_quote_app_payload)
                 print(f"Test: Created and (attempted to) send Quote ID: {created_quote_id}")
             except Exception as e:
                 print(f"Test Error creating/sending quote: {e}")
    except Exception as e:
        print(f"Test Error during client/property creation: {e}")