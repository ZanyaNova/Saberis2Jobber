# jobber_client_module.py
"""
Jobber API Client for making GraphQL requests.
Integrates with jobber_auth_flow to use valid access tokens.
"""
import requests
import re
from typing import Any, Optional, Tuple, List, TypedDict, Union, Dict, cast

from jobber_auth_flow import get_valid_access_token # Using the real auth flow
from jobber_models import SaberisOrder, QuoteCreateInput, SaberisLineItem, QuoteLineInput, ShippingAddress

JOBBER_GRAPHQL_URL = "https://api.getjobber.com/api/graphql"

# Placeholder functions are now removed as per Key Action 1


# --- GraphQL TypedDicts (Specific to Jobber API Structure) ---
# --- General GraphQL Structures ---
class GraphQLErrorLocation(TypedDict, total=False): line: int; column: int
class GraphQLErrorExtension(TypedDict, total=False): code: str
class GraphQLErrorDetail(TypedDict):
    message: str
    path: Optional[List[Union[str, int]]]
    locations: Optional[List[GraphQLErrorLocation]]
    extensions: Optional[GraphQLErrorExtension]
class GraphQLResponseWrapper(TypedDict):
    data: Optional[Dict[str, Any]] # 'data' key in the raw GraphQL response
    errors: Optional[List[GraphQLErrorDetail]]
class UserError(TypedDict): message: str; path: List[Union[str, int]] # Jobber's userError structure

# --- Client Creation GQL TypedDicts ---
class ClientEmailInputGQL(TypedDict, total=False): address: str; primary: Optional[bool]
class ClientPhoneInputGQL(TypedDict, total=False): number: str; primary: Optional[bool]; type: Optional[str] # e.g. "work", "mobile"
class ClientMutationInputGQL(TypedDict, total=False):
    name: str; firstName: Optional[str]; lastName: Optional[str]
    emails: Optional[List[ClientEmailInputGQL]]; phones: Optional[List[ClientPhoneInputGQL]]
class ClientCreateVariablesGQL(TypedDict): input: ClientMutationInputGQL
class ClientObjectGQL(TypedDict): id: str; name: str # Structure of 'client' object in response
class ClientCreateDataPayloadGQL(TypedDict): client: Optional[ClientObjectGQL]; userErrors: Optional[List[UserError]] # Structure of 'clientCreate' in response data
# ClientCreateResponseDataGQL (Optional - if you want to type the whole 'data' field for this specific mutation)
# class ClientCreateResponseDataGQL(TypedDict): clientCreate: Optional[ClientCreateDataPayloadGQL]


# --- Property Creation GQL TypedDicts ---
class PropertyAddressInputGQL(TypedDict, total=False):
    street: Optional[str]; street2: Optional[str]; city: Optional[str]
    province: Optional[str]; postalCode: Optional[str]; country: Optional[str]
class PropertyMutationInputGQL(TypedDict): clientId: str; address: PropertyAddressInputGQL
class PropertyCreateVariablesGQL(TypedDict): input: PropertyMutationInputGQL
class PropertyObjectGQL(TypedDict): id: str; address: Optional[PropertyAddressInputGQL] # Structure of 'property' object
class PropertyCreateDataPayloadGQL(TypedDict): property: Optional[PropertyObjectGQL]; userErrors: Optional[List[UserError]] # Structure of 'propertyCreate' in response data
# PropertyCreateResponseDataGQL (Optional)
# class PropertyCreateResponseDataGQL(TypedDict): propertyCreate: Optional[PropertyCreateDataPayloadGQL]


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
class QuoteObjectGQL(TypedDict): id: str; quoteNumber: Optional[str]; quoteStatus: str # Structure of 'quote' object
class QuoteCreateDataPayloadGQL(TypedDict): quote: Optional[QuoteObjectGQL]; userErrors: Optional[List[UserError]] # Structure of 'quoteCreate' in response data
# QuoteCreateResponseDataGQL (Optional)
# class QuoteCreateResponseDataGQL(TypedDict): quoteCreate: Optional[QuoteCreateDataPayloadGQL]


# --- Quote Sending GQL TypedDicts ---
class QuoteSendByIdVariablesGQL(TypedDict): quoteId: str # If mutation is quoteSend(id: $quoteId)
# If mutation is quoteSend(input: {id: $quoteId}), then:
# class QuoteSendInputGQL(TypedDict): id: str
# class QuoteSendVariablesGQL(TypedDict): input: QuoteSendInputGQL
class QuoteSendDataPayloadGQL(TypedDict): quote: Optional[QuoteObjectGQL]; userErrors: Optional[List[UserError]] # Structure of 'quoteSend' in response data
# QuoteSendResponseDataGQL (Optional)
# class QuoteSendResponseDataGQL(TypedDict): quoteSend: Optional[QuoteSendDataPayloadGQL]


# General type for variables passed to _post; can be expanded with more specific variable types
GraphQLMutationVariables = Union[
    ClientCreateVariablesGQL, PropertyCreateVariablesGQL, QuoteCreateVariablesGQL,
    QuoteSendByIdVariablesGQL, # Add other specific variable types here
    Dict[str, Any] # Fallback for less strictly typed variables
]
# General type for the 'data' field returned by _post after extracting from GraphQLResponseWrapper
GraphQLData = Dict[str, Any]


class JobberClient:
    def __init__(self, api_version: str = "2025-01-20"):
        self.api_version = api_version
        self.access_token: Optional[str] = None # Cached token for the client instance

    def _get_headers(self) -> Dict[str, str]:
        """Retrieves valid token and prepares headers for API requests."""
        # Always attempt to get the latest valid token via the auth flow
        current_token = get_valid_access_token()
        if not current_token:
            # This error will be caught by the calling methods or main.py's worker loop
            raise ConnectionRefusedError(
                "Jobber API: No valid access token available. Please authorize or check token refresh."
            )
        self.access_token = current_token # Cache for potential reuse by this instance if needed
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "X-JOBBER-GRAPHQL-VERSION": self.api_version,
        }

    def _post(self, query: str, variables: Optional[GraphQLMutationVariables] = None) -> GraphQLData:
        """Helper method to make POST requests to the Jobber GraphQL API."""
        headers = self._get_headers() # Ensures a valid token is used or raises ConnectionRefusedError
        payload: Dict[str, Any] = {"query": query, "variables": variables or {}}

        query_name_match: Optional[re.Match[str]] = re.search(r'(mutation|query)\s+(\w+)', query, re.IGNORECASE)
        query_operation_name: str
        if query_name_match:
            query_operation_name = query_name_match.group(2)
        else:
            query_operation_name = "UnnamedOperation"
        
        log_query_identifier = f"GraphQL {query_operation_name}"

        print(f"INFO: Sending {log_query_identifier}. Variables: {variables is not None}")
        resp: Optional[requests.Response] = None

        try:
            resp = requests.post(JOBBER_GRAPHQL_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status() # Raises HTTPError for 4xx/5xx responses

            try:
                gql_response_dict = resp.json()
                if not isinstance(gql_response_dict, dict):
                    print(f"ERROR: Jobber API response for {log_query_identifier} was not the expected dictionary structure. Type: {type(gql_response_dict)}. Response: {str(gql_response_dict)[:200]}")
                    raise ValueError(f"Response JSON was not a dictionary, got {type(gql_response_dict)}")
                # Cast to the wrapper TypedDict that includes 'data' and 'errors' keys
                gql_response: GraphQLResponseWrapper = cast(GraphQLResponseWrapper, gql_response_dict)

            except ValueError as e: # Handles non-JSON responses or if JSON isn't a dict
                status_code_info = f"Status: {resp.status_code}" # resp is guaranteed to be a Response object here
                response_text_snippet = resp.text[:200]        # "
                print(f"ERROR: Jobber API response for {log_query_identifier} was not valid JSON or had unexpected structure. {status_code_info}. Original error: {e}. Response snippet: {response_text_snippet}")
                raise RuntimeError(f"Jobber API did not return valid JSON for {log_query_identifier}. {status_code_info}. Snippet: {response_text_snippet}") from e
            
            errors_list: Optional[List[GraphQLErrorDetail]] = gql_response.get("errors")
            if errors_list:
                error_messages_list: List[str] = []
                print(f"ERROR: GraphQL errors for {log_query_identifier}:")
                for i, err_detail_item in enumerate(errors_list):
                    current_err_message = err_detail_item.get('message', 'Unknown GraphQL error')
                    error_messages_list.append(current_err_message)
                    print(f"  Error {i+1}:")
                    print(f"    Message: {current_err_message}")
                    path: Optional[List[Union[str, int]]] = err_detail_item.get('path')
                    if path: print(f"    Path: {path}")
                    extensions_data: Optional[GraphQLErrorExtension] = err_detail_item.get('extensions')
                    if extensions_data:
                        error_code: Optional[str] = extensions_data.get('code')
                        if error_code: print(f"    Code: {error_code}")
                    locations_data: Optional[List[GraphQLErrorLocation]] = err_detail_item.get('locations')
                    if locations_data:
                        for loc_idx, loc_item in enumerate(locations_data):
                            line: Optional[int] = loc_item.get('line')
                            column: Optional[int] = loc_item.get('column')
                            print(f"    Location {loc_idx+1}: Line {line if line is not None else 'N/A'}, Column {column if column is not None else 'N/A'}")
                raise RuntimeError(f"GraphQL errors for {log_query_identifier}: {'; '.join(error_messages_list)}")

            response_data: Optional[Dict[str, Any]] = gql_response.get("data")
            if response_data is None: # No 'data' key implies an issue if no 'errors' were present either
                print(f"ERROR: GraphQL response for {log_query_identifier} missing 'data' key or 'data' is null, and no top-level errors. Response: {gql_response}")
                raise RuntimeError(f"GraphQL response for {log_query_identifier} missing 'data' or 'data' is null. Response: {gql_response}")
            
            print(f"SUCCESS: {log_query_identifier} completed successfully.")
            # response_data is Dict[str, Any], which matches GraphQLData, so no type: ignore needed.
            return response_data

        except requests.exceptions.HTTPError as e:
            # Handle HTTP errors (4xx, 5xx)
            status_code_str = str(e.response.status_code) if e.response is not None else "N/A"
            error_text_snippet = (e.response.text[:200] + "...") if e.response is not None and e.response.text else str(e)
            print(f"ERROR: HTTPError for {log_query_identifier}. Status: {status_code_str}. Response: {error_text_snippet}")
            if e.response is not None and e.response.status_code == 401:
                print(f"AUTH_ERROR: Jobber API call for {log_query_identifier} returned 401 Unauthorized.")
                self.access_token = None # Clear cached token
                # ConnectionRefusedError signals auth failure to the caller
                raise ConnectionRefusedError(
                    f"Jobber API: Token became unauthorized during {log_query_identifier}. A refresh attempt might have failed or is needed."
                ) from e
            raise # Re-raise other HTTPError for general handling
        
        except requests.exceptions.Timeout as e:
            print(f"ERROR: Timeout occurred while calling Jobber API for {log_query_identifier}: {e}")
            raise 
        except requests.exceptions.ConnectionError as e: # More specific than RequestException
            print(f"ERROR: Connection error while calling Jobber API for {log_query_identifier}: {e}")
            raise
        except requests.exceptions.RequestException as e: # Catch other request-related exceptions
            error_type_name = type(e).__name__
            print(f"ERROR: A network request to Jobber API failed for {log_query_identifier} ({error_type_name}): {e}")
            raise

    def create_client_and_property(self, order: SaberisOrder) -> Tuple[str, str]:
        """Creates a client and then a property for that client in Jobber."""
        client_name = order.customer_name
        print(f"INFO: Attempting to create Jobber client for: '{client_name}'")

        client_create_mutation = """
        mutation ClientCreate($input: ClientCreateInput!) {
          clientCreate(input: $input) { client { id name } userErrors { message path } }
        }"""
        client_mutation_input_gql: ClientMutationInputGQL = {"name": client_name}
        # TODO: Consider adding emails/phones from order if available
        # e.g., if order.contact_email: client_mutation_input_gql["emails"] = [{"address": order.contact_email, "primary": True}]
        
        client_variables: ClientCreateVariablesGQL = {"input": client_mutation_input_gql}
        client_id: str
        try:
            # _post returns Dict[str, Any] which is GraphQLData
            raw_client_response_data: GraphQLData = self._post(client_create_mutation, client_variables)
            
            client_create_payload_dict = raw_client_response_data.get("clientCreate")
            if not isinstance(client_create_payload_dict, dict):
                print(f"ERROR: Unexpected response structure for clientCreate for '{client_name}'. Expected dict, got {type(client_create_payload_dict)}. Response: {raw_client_response_data}")
                raise RuntimeError(f"Unexpected response structure for clientCreate: {raw_client_response_data}")
            # Cast to the specific TypedDict for 'clientCreate' payload
            client_create_data: ClientCreateDataPayloadGQL = cast(ClientCreateDataPayloadGQL, client_create_payload_dict)
            
            user_errors = client_create_data.get("userErrors")
            if user_errors:
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors]
                print(f"ERROR: Jobber userErrors creating client '{client_name}': {'; '.join(error_messages)}")
                raise RuntimeError(f"Error creating Jobber client '{client_name}': {'; '.join(error_messages)}")

            client_object = client_create_data.get("client")
            if not client_object or not client_object.get("id"):
                print(f"ERROR: Client creation response missing client ID or client object for '{client_name}'. Response: {client_create_data}")
                raise RuntimeError(f"Client creation response missing client ID or client object for '{client_name}': {client_create_data}")

            client_id = client_object["id"] # id is required in ClientObjectGQL
            print(f"SUCCESS: Created Jobber client '{client_object.get('name', client_name)}' with ID: {client_id}")

        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            # Catch specific errors from _post or this method's logic
            print(f"ERROR: Failed to create Jobber client for '{client_name}': {e}")
            raise
        except Exception as e: # Catch any other unexpected errors
            print(f"ERROR: Unexpected error creating Jobber client for '{client_name}': {e}")
            raise

        # --- Property Creation ---
        print(f"INFO: Attempting to create Jobber property for client ID: {client_id}")
        property_create_mutation = """
        mutation PropertyCreate($input: PropertyCreateInput!) {
          propertyCreate(input: $input) { property { id address { street city province postalCode } } userErrors { message path } }
        }"""
        saberis_addr: ShippingAddress = order.shipping_address
        # Filter None values from Saberis address to build PropertyAddressInputGQL
        temp_property_address: Dict[str, Any] = {
            "street": saberis_addr.get("address"), "city": saberis_addr.get("city"),
            "province": saberis_addr.get("state"), "postalCode": saberis_addr.get("postalCode"),
            "country": saberis_addr.get("country")
        }
        filtered_address_dict = {k: v for k, v in temp_property_address.items() if v is not None and v != ""}
        property_address_gql: PropertyAddressInputGQL = cast(PropertyAddressInputGQL, filtered_address_dict)

        property_mutation_input_gql: PropertyMutationInputGQL = {"clientId": client_id, "address": property_address_gql}
        property_variables: PropertyCreateVariablesGQL = {"input": property_mutation_input_gql}
        property_id: str
        try:
            raw_property_response_data: GraphQLData = self._post(property_create_mutation, property_variables)
            
            property_create_payload_dict = raw_property_response_data.get("propertyCreate")
            if not isinstance(property_create_payload_dict, dict):
                print(f"ERROR: Unexpected response structure for propertyCreate for client ID '{client_id}'. Expected dict, got {type(property_create_payload_dict)}. Response: {raw_property_response_data}")
                raise RuntimeError(f"Unexpected response structure for propertyCreate: {raw_property_response_data}")
            property_create_data: PropertyCreateDataPayloadGQL = cast(PropertyCreateDataPayloadGQL, property_create_payload_dict)
            
            user_errors = property_create_data.get("userErrors")
            if user_errors:
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors]
                print(f"ERROR: Jobber userErrors creating property for client ID '{client_id}': {'; '.join(error_messages)}")
                raise RuntimeError(f"Error creating Jobber property for client ID '{client_id}': {'; '.join(error_messages)}")

            property_object = property_create_data.get("property")
            if not property_object or not property_object.get("id"):
                print(f"ERROR: Property creation response missing property ID or property object for client ID '{client_id}'. Response: {property_create_data}")
                raise RuntimeError(f"Property creation response missing property ID or property object for client ID '{client_id}': {property_create_data}")
            
            property_id = property_object["id"] # id is required in PropertyObjectGQL
            print(f"SUCCESS: Created Jobber property with ID: {property_id} for client ID: {client_id}")
        
        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            print(f"ERROR: Failed to create Jobber property for client ID '{client_id}': {e}")
            raise
        except Exception as e:
            print(f"ERROR: Unexpected error creating Jobber property for client ID '{client_id}': {e}")
            raise
            
        return client_id, property_id

    def create_and_send_quote(self, app_quote_payload: QuoteCreateInput) -> Tuple[Optional[str], str]:
        """Creates and then attempts to send a quote in Jobber. Returns (quote_id, status_message)."""
        quote_id: Optional[str] = None
        status_message: str = "Quote processing initiated."

        print(f"INFO: Preparing to create quote with title: '{app_quote_payload.title}' for client: {app_quote_payload.client_id}")
        
        quote_lines_for_gql: List[QuoteLineItemGQL] = []
        for li_model in app_quote_payload.line_items:
            item_gql: QuoteLineItemGQL = {
                "description": li_model.name, "quantity": li_model.quantity,
                "unitPrice": li_model.unit_price, "taxable": li_model.taxable # bool is assignable to Optional[bool]
            }
            if li_model.unit_cost is not None:
                item_gql["unitCost"] = li_model.unit_cost
            quote_lines_for_gql.append(item_gql)

        quote_mutation_input_gql: QuoteMutationInputGQL = {
            "clientId": app_quote_payload.client_id, "propertyId": app_quote_payload.property_id,
            "title": app_quote_payload.title, "message": app_quote_payload.message,
            "lineItems": quote_lines_for_gql
        }
        variables_create: QuoteCreateVariablesGQL = {"input": quote_mutation_input_gql}
        create_mutation = """
        mutation QuoteCreate($input: QuoteCreateInput!) {
          quoteCreate(input: $input) { quote { id quoteNumber quoteStatus } userErrors { message path } }
        }"""
        
        try:
            print(f"INFO: Creating quote with title: '{app_quote_payload.title}' for client: {app_quote_payload.client_id}")
            raw_data_create: GraphQLData = self._post(create_mutation, variables_create)

            quote_create_payload_dict = raw_data_create.get("quoteCreate")
            if not isinstance(quote_create_payload_dict, dict):
                status_message = f"Quote creation response missing 'quoteCreate' key or not a dict. Response: {raw_data_create}"
                print(f"ERROR: {status_message}")
                raise RuntimeError(status_message)
            quote_create_result: QuoteCreateDataPayloadGQL = cast(QuoteCreateDataPayloadGQL, quote_create_payload_dict)
            
            user_errors_create = quote_create_result.get("userErrors")
            if user_errors_create:
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors_create]
                status_message = f"Quote creation failed with user errors: {'; '.join(error_messages)}"
                print(f"ERROR: {status_message}. Input: {variables_create.get('input', {}).get('title', 'N/A')}")
                raise RuntimeError(status_message) # No quote_id, raise error

            quote_object = quote_create_result.get("quote")
            if not quote_object or not quote_object.get("id"): # id is required in QuoteObjectGQL
                status_message = f"Quote creation response missing quote object or quote ID for title '{app_quote_payload.title}'."
                print(f"ERROR: {status_message}. Response: {quote_create_result}")
                raise RuntimeError(status_message)

            quote_id = quote_object["id"]
            initial_status = quote_object.get('quoteStatus', 'Unknown') # quoteStatus is required in QuoteObjectGQL
            status_message = f"Quote created (ID: {quote_id}, Status: {initial_status})."
            print(f"SUCCESS: {status_message} For title: '{app_quote_payload.title}'. Now attempting to send.")

        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            # These are errors from _post or local logic during creation
            status_message = f"Quote creation failed for '{app_quote_payload.title}': {e}"
            print(f"ERROR: {status_message}")
            return None, status_message # Return None for quote_id and the error message
        except Exception as e: # Other unexpected errors during creation
            status_message = f"Unexpected error creating quote '{app_quote_payload.title}': {e}"
            print(f"ERROR: {status_message}")
            return None, status_message

        # --- Send Quote ---
        if not quote_id: # Should not happen if creation succeeded, but as a safeguard
            final_status_message = f"{status_message} Skipping sending as quote ID was not obtained."
            print(f"WARNING: {final_status_message}")
            return None, final_status_message

        print(f"INFO: Attempting to send quote ID: {quote_id} (Title: '{app_quote_payload.title}')")
        # Assuming quoteSend(id: $quoteId) structure based on QuoteSendByIdVariablesGQL
        send_mutation = """
        mutation QuoteSend($quoteId: ID!) {
          quoteSend(id: $quoteId) { quote { id quoteStatus } userErrors { message path } }
        }"""
        variables_send: QuoteSendByIdVariablesGQL = {"quoteId": quote_id}
        try:
            raw_data_send: GraphQLData = self._post(send_mutation, variables_send)
            quote_send_payload_dict = raw_data_send.get("quoteSend")

            if not isinstance(quote_send_payload_dict, dict):
                warning_msg = f"Quote sending response for ID {quote_id} missing 'quoteSend' key or not a dict. Response: {raw_data_send}. Quote may not have been sent."
                print(f"WARNING: {warning_msg}")
                return quote_id, f"{status_message} Sending status uncertain: {warning_msg}"
            
            send_result: QuoteSendDataPayloadGQL = cast(QuoteSendDataPayloadGQL, quote_send_payload_dict)
            user_errors_send = send_result.get("userErrors")
            if user_errors_send:
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors_send]
                send_errors_details = '; '.join(error_messages)
                print(f"WARNING: Jobber userErrors sending quote ID {quote_id}: {send_errors_details}. Response: {send_result}")
                return quote_id, f"{status_message} Sending encountered user errors: {send_errors_details}"
            
            sent_quote_details = send_result.get("quote")
            final_quote_status = "Unknown after send"
            if sent_quote_details:
                final_quote_status = sent_quote_details.get("quoteStatus", "StatusNotProvidedInSendResponse") # quoteStatus is required
            
            success_send_message = f"Quote (ID: {quote_id}) sent. New status: {final_quote_status}."
            print(f"SUCCESS: {success_send_message} (Title: '{app_quote_payload.title}')")
            return quote_id, success_send_message

        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            send_fail_message = f"{status_message} Sending failed for quote ID {quote_id}: {e}"
            print(f"ERROR: {send_fail_message}")
            return quote_id, send_fail_message # Return created quote_id but with send error message
        except Exception as e:
            send_unexpected_fail_message = f"{status_message} Unexpected error sending quote ID {quote_id}: {e}"
            print(f"ERROR: {send_unexpected_fail_message}")
            return quote_id, send_unexpected_fail_message

# Example Usage (Illustrative)
if __name__ == "__main__":
    from datetime import datetime # Required for SaberisOrder in example

    # This example assumes jobber_auth_flow.py and token_storage.py are configured
    # and that a valid token can be obtained (e.g., after running the web auth flow).
    # For direct testing of this module without full auth, you might need to
    # temporarily mock get_valid_access_token() or ensure TOKEN_FILE_PATH has a valid token.

    print("INFO: Running jobber_client_module.py example usage...")
    print("Ensure Jobber tokens are authorized and available for this test to fully succeed.")

    client = JobberClient()
    
    # Sample data for testing
    sample_shipping_addr: ShippingAddress = {
        "address": "123 Example St", "city": "Exampleville", "state": "EX",
        "postalCode": "E1X 2M3", "country": "EXA"
    }
    sample_saberis_order = SaberisOrder(
        username="testuser_client_module", created_at=datetime.now(), # Changed username for clarity
        customer_name=f"Modular Test Client {datetime.now().strftime('%H%M%S')}", # Unique name for testing
        shipping_address=sample_shipping_addr,
        lines=[
            SaberisLineItem(type="Product", description="Modular Foundation Work", quantity=1, selling_price=1500.00, list_price=1600.00, cost=1000.00),
            SaberisLineItem(type="Product", description="Modular Framing Package", quantity=1, selling_price=3500.00, list_price=4000.00, cost=2500.00)
        ]
    )
    
    created_client_id: Optional[str] = None
    created_property_id: Optional[str] = None
    
    try:
        print("\n--- Testing Client and Property Creation ---")
        created_client_id, created_property_id = client.create_client_and_property(sample_saberis_order)
        print(f"INFO: Test Result - Created Client ID: {created_client_id}, Property ID: {created_property_id}")

        if created_client_id and created_property_id:
            sample_quote_app_payload = QuoteCreateInput(
                client_id=created_client_id, 
                property_id=created_property_id,
                title=f"Modular Project Estimate {datetime.now().strftime('%y%m%d-%H%M')}", 
                message="Estimate for the initial phase of the modular construction project.",
                line_items=[
                    QuoteLineInput(name="Site Preparation", quantity=1.0, unit_price=250.00, taxable=False),
                    QuoteLineInput(name="Module Delivery", quantity=1.0, unit_price=500.00, taxable=False)
                ]
            )
            try:
                print("\n--- Testing Quote Creation and Sending ---")
                final_quote_id, final_status_msg = client.create_and_send_quote(sample_quote_app_payload)
                print(f"INFO: Test Result - Quote ID: {final_quote_id}, Final Status: {final_status_msg}")
            except RuntimeError as e_quote: # Catch runtime specifically if needed
                print(f"ERROR: Test - Runtime error creating/sending quote: {e_quote}")
            except Exception as e_quote_general: # General catch
                print(f"ERROR: Test - General error creating/sending quote: {e_quote_general}")
                
    except ConnectionRefusedError as e_auth:
        print(f"ERROR: Test - Authentication error: {e_auth}. Please ensure the application is authorized with Jobber.")
    except RuntimeError as e_runtime: # Catch runtime specifically from client/property creation
        print(f"ERROR: Test - Runtime error during client/property creation: {e_runtime}")
    except Exception as e_general: # General catch for client/property
        print(f"ERROR: Test - General error during client/property creation: {e_general}")