"""
Jobber API Client for making GraphQL requests.
Integrates with jobber_auth_flow to use valid access tokens.
"""
import requests
from typing import Any, Optional, Tuple 

from jobber_config import JOBBER_GRAPHQL_URL
from jobber_auth_flow import get_valid_access_token
from jobber_models import SaberisOrder, QuoteCreateInput 

class JobberClient:
    def __init__(self, api_version: str = "2025-01-20"):
        """
        Initializes the JobberClient.
        Authentication is handled by get_valid_access_token().
        """
        self.api_version = api_version
        self.access_token: Optional[str] = None # Instance cache for the token

    def _get_headers(self) -> dict[str, str]:
        """
        Ensures a valid token is available (fetching or refreshing if needed)
        and returns the necessary headers for API calls.
        """
        # Attempt to get a valid token if not already cached in this instance
        # or if the instance cache might be stale (though get_valid_access_token handles actual refresh logic)
        self.access_token = get_valid_access_token()

        if not self.access_token:
            # This error means that even after attempting to load/refresh, no token is available.
            raise ConnectionRefusedError(
                "Jobber API: No valid access token available. Please authorize the application via the /authorize_jobber endpoint."
            )
        
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
            "X-JOBBER-GRAPHQL-VERSION": self.api_version,
        }

    def _post(self, query: str, variables: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Makes a POST request to the Jobber GraphQL endpoint with authentication.
        Handles token acquisition and potential refresh.
        """
        headers = self._get_headers() # This will ensure self.access_token is valid and set
        payload = {"query": query, "variables": variables or {}}
        
        try:
            resp = requests.post(JOBBER_GRAPHQL_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            data = resp.json()

            # Check for GraphQL-specific errors in the response body
            if "errors" in data and data["errors"]: 
                error_detail = f"GraphQL errors for query '{query[:100]}...': {data['errors']}"
                print(error_detail) 
                raise RuntimeError(error_detail) # Or a custom GraphQL error exception
            
            if "data" not in data: # Should always be present in a successful GraphQL response
                 raise RuntimeError(f"GraphQL response missing 'data' key. Response: {data}")
            return data["data"]
        except requests.exceptions.HTTPError as e:
            # Specific handling for 401 Unauthorized, which might mean the token became invalid
            # between the time it was fetched/refreshed by _get_headers and the actual API call.
            # This is less likely with the current structure but good for robustness.
            if e.response is not None and e.response.status_code == 401:
                print("Jobber API call returned 401 Unauthorized. Token might have been revoked or expired suddenly.")
                print("Attempting to clear local token cache to force re-auth or a fresh refresh on next attempt.")
                from token_storage import clear_tokens 
                clear_tokens()
                self.access_token = None # Clear instance token as well
                # Re-raise as a ConnectionRefusedError to signal auth failure to the worker
                raise ConnectionRefusedError(
                    "Jobber API: Token became unauthorized during use. Please re-authorize or wait for next refresh attempt."
                ) from e
            raise # Re-raise other HTTP errors
        except requests.exceptions.RequestException as e:
            # For other network issues, timeouts, etc.
            print(f"Network request to Jobber API failed: {e}")
            raise # Re-raise the original exception

    # ––––– Public API (Methods from your original main.py) –––––
    def create_client_and_property(self, order: SaberisOrder) -> Tuple[str, str]:
        """
        Creates a new client + property. Returns (client_id, property_id).
        NOTE: This is a placeholder. Implement with actual GraphQL calls.
        Consult Jobber's GraphQL documentation for the correct mutations and input types.
        """
        # Example structure for client creation:
        # client_name = order.customer_name
        # # Potentially map Saberis address fields to Jobber's expected address structure
        # # street = order.shipping_address.get('address')
        # # city = order.shipping_address.get('city')
        # # ... etc.
        # client_create_mutation = """
        # mutation ClientCreate($input: ClientCreateInput!) {
        #   clientCreate(input: $input) {
        #     client { id name }
        #     userErrors { message path }
        #   }
        # }
        # """
        # client_variables = {
        #     "input": {
        #         "name": client_name,
        #         # "firstName": "...", # If you parse it
        #         # "lastName": "...",  # If you parse it
        #         # "emails": [{"address": "email@example.com", "primary": True}], # If available
        #         # "phones": [{"number": "123-456-7890", "primary": True, "type": "MOBILE"}], # If available
        #         # ... other client fields
        #     }
        # }
        # try:
        #     client_data = self._post(client_create_mutation, client_variables)
        #     if client_data.get("clientCreate", {}).get("userErrors"):
        #         raise RuntimeError(f"Error creating client: {client_data['clientCreate']['userErrors']}")
        #     client_id = client_data["clientCreate"]["client"]["id"]
        # except Exception as e:
        #     print(f"Failed to create Jobber client for {client_name}: {e}")
        #     raise

        # # Example structure for property creation (associated with client_id):
        # property_create_mutation = """
        # mutation PropertyCreate($input: PropertyCreateInput!) {
        #   propertyCreate(input: $input) {
        #     property { id address { street city } }
        #     userErrors { message path }
        #   }
        # }
        # """
        # property_variables = {
        #     "input": {
        #         "clientId": client_id,
        #         "address": {
        #             "street": order.shipping_address.get('address'),
        #             "city": order.shipping_address.get('city'),
        #             "province": order.shipping_address.get('state'),
        #             "postalCode": order.shipping_address.get('postalCode'),
        #             "country": order.shipping_address.get('country')
        #         }
        #         # ... other property fields
        #     }
        # }
        # try:
        #     property_data = self._post(property_create_mutation, property_variables)
        #     if property_data.get("propertyCreate", {}).get("userErrors"):
        #         raise RuntimeError(f"Error creating property: {property_data['propertyCreate']['userErrors']}")
        #     property_id = property_data["propertyCreate"]["property"]["id"]
        # except Exception as e:
        #     print(f"Failed to create Jobber property for client {client_id}: {e}")
        #     raise
        
        print(f"Stub: Creating client for {order.customer_name} and property.")
        fake_id = lambda prefix: f"{prefix}_{hash(order.unique_key()) & 0xFFFF:04x}"
        client_id = fake_id("client") 
        property_id = fake_id("property")
        print(f"Stub: Generated client_id: {client_id}, property_id: {property_id}")
        return client_id, property_id


    def create_and_send_quote(self, payload: QuoteCreateInput) -> str:
        """Creates a quote and immediately sends it. Returns quote_id."""
        quote_lines_for_gql = [ # Renamed to avoid conflict with outer scope if any
            {
                "description": li.name,
                "quantity": li.quantity,
                "unitPrice": li.unit_price, # Ensure this is float/decimal as expected by Jobber
                # Conditionally add unitCost if it's not None
                **({"unitCost": li.unit_cost} if li.unit_cost is not None else {}),
                # "taxable": li.taxable # Include if you intend to set tax status per line
            }
            for li in payload.line_items
        ]
        
        variables_create = {
            "input": {
                "clientId": payload.client_id,
                "propertyId": payload.property_id, # Ensure this is the Jobber Property ID
                "title": payload.title,
                "message": payload.message,
                "lineItems": quote_lines_for_gql,
                # "creationOptions": { "draft": False } # To create as non-draft, if API supports
            }
        }
        # This mutation is based on common GraphQL patterns.
        # Verify the exact 'QuoteCreateInput' type and fields from Jobber's schema.
        create_mutation = """
        mutation QuoteCreate($input: QuoteCreateInput!) {
          quoteCreate(input: $input) {
            quote { id quoteNumber quoteStatus }
            userErrors { message path }
          }
        }
        """
        print(f"Creating quote with title: '{payload.title}' for client: {payload.client_id}")
        data_create = self._post(create_mutation, variables_create)
        
        # Robust error checking for quote creation
        quote_create_result = data_create.get("quoteCreate")
        if not quote_create_result or quote_create_result.get("userErrors"):
            errors = quote_create_result.get("userErrors") if quote_create_result else "Unknown error structure"
            raise RuntimeError(f"Quote creation failed. Errors: {errors}. Response: {data_create}")
        
        if not quote_create_result.get("quote") or not quote_create_result["quote"].get("id"):
             raise RuntimeError(f"Quote creation response missing quote ID. Response: {data_create}")

        quote_id = quote_create_result["quote"]["id"]
        print(f"Quote created with ID: {quote_id}. Status: {quote_create_result['quote']['quoteStatus']}. Now sending.")

        # Auto-send mutation.
        # The Jobber AppTemplate-RailsAPI used `quoteSend(id: $id)`.
        # The Jobber documentation for `appDisconnect` suggests mutations might take an input object.
        # Let's stick to the simpler `id` based one if that's what the template used,
        # but be prepared to change if Jobber's schema requires an input object like `QuoteSendByIdInput`.
        
        # Version 1: Based on Rails template (simpler)
        send_mutation_simple = """
        mutation QuoteSend($quoteId: ID!) {
          quoteSend(id: $quoteId) {
            quote { id quoteStatus }
            userErrors { message path }
          }
        }
        """
        variables_send_simple = {"quoteId": quote_id}
        
        # # Version 2: If it requires an input object (more complex, verify if needed)
        # send_mutation_input_obj = """
        # mutation QuoteSendById($input: QuoteSendByIdInput!) {
        #   quoteSendById(input: $input) {
        #     quote { id quoteStatus }
        #     userErrors { message path }
        #   }
        # }
        # """
        # variables_send_input_obj = {"input": {"id": quote_id}}

        # Using the simpler version based on the Rails template indication
        data_send = self._post(send_mutation_simple, variables_send_simple)

        send_result = data_send.get("quoteSend")
        if not send_result or send_result.get("userErrors"):
            errors = send_result.get("userErrors") if send_result else "Unknown error structure"
            # Note: Even if sending fails, the quote is already created.
            # You might want to log this error but not necessarily raise an exception
            # that stops further processing if partial success is acceptable.
            print(f"Warning: Quote sending for {quote_id} encountered errors: {errors}. Response: {data_send}")
        else:
            print(f"Quote {quote_id} sent successfully. New status: {send_result.get('quote', {}).get('quoteStatus')}")
            
        return quote_id