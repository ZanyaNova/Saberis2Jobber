# jobber_client_module.py
"""
Jobber API Client for making GraphQL requests.
Integrates with jobber_auth_flow to use valid access tokens.
"""
import requests
import re
from typing import Any, Optional, Tuple, List, TypedDict, Union, Dict, cast

from .jobber_auth_flow import get_valid_access_token
from .jobber_models import (
    SaberisOrder, QuoteCreateInput, ShippingAddress, QuoteLineItemGQL, 
    QuoteLineEditItemGQL, PageInfoGQL, JobNodeGQL, JobPageGQL, 
    GetJobsResponseGQL, JobCreateLineItemGQL, JobEditLineItemGQL # Add Job models here
)
JOBBER_GRAPHQL_URL = "https://api.getjobber.com/api/graphql"

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

class JobCreateLineItemsInputGQL(TypedDict):
    """The 'input' object for the jobCreateLineItems mutation."""
    lineItems: List[JobCreateLineItemGQL]

class JobCreateLineItemsPayloadGQL(TypedDict):
    """The 'jobCreateLineItems' payload in the response data."""
    userErrors: Optional[List[UserError]]
    # The payload also returns the job and createdLineItems, which we can add if needed for verification.

# --- Structures for Editing Line Items on a Job ---
# This should only contain the line items, as per the Jobber API Schema.
class JobEditLineItemsInputGQL(TypedDict):
    """The 'input' object for the jobEditLineItems mutation."""
    lineItems: List[JobEditLineItemGQL]

# This is the correct structure for the overall variables object.
class JobEditLineItemsVariablesGQL(TypedDict):
    """The complete variables for the jobEditLineItems mutation."""
    jobId: str
    input: JobEditLineItemsInputGQL

class JobEditLineItemsPayloadGQL(TypedDict):
    """The 'jobEditLineItems' payload in the response data."""
    userErrors: Optional[List[UserError]]

class JobLineItemNodeGQL(TypedDict, total=False):
    """Represents a single line item on a Job."""
    id: str
    name: str
    quantity: float
    unitPrice: float

class JobLineItemConnectionGQL(TypedDict):
    nodes: List[JobLineItemNodeGQL]

class FullJobNodeGQL(TypedDict, total=False):
    """Represents a single, detailed job fetched by its ID."""
    id: str
    lineItems: JobLineItemConnectionGQL

class GetJobDataGQL(TypedDict):
    job: FullJobNodeGQL

class GetJobResponseGQL(TypedDict):
    data: GetJobDataGQL

# --- Structures for Approved Quote Query ---

class AddressGQL(TypedDict, total=False):
    street1: Optional[str]
    city: Optional[str]
    province: Optional[str]
    postalCode: Optional[str]

class PropertyGQL(TypedDict, total=False):
    id: str
    address: AddressGQL

class ClientGQL(TypedDict):
    id: str
    name: str

class QuoteAmountsGQL(TypedDict, total=False):
    total: float

class QuoteNodeGQL(TypedDict):
    id: str
    quoteNumber: str
    title: Optional[str]
    transitionedAt: str # ISO 8601 string
    client: ClientGQL
    property: Optional[PropertyGQL] # Property can be null
    amounts: QuoteAmountsGQL

class QuoteEdgeGQL(TypedDict):
    cursor: str
    node: QuoteNodeGQL

class QuotesConnectionGQL(TypedDict):
    edges: List[QuoteEdgeGQL]
    pageInfo: PageInfoGQL
    totalCount: int

class QuotesDataGQL(TypedDict):
    quotes: QuotesConnectionGQL

class GetQuotesResponseGQL(TypedDict):
    data: QuotesDataGQL

class QuotePageGQL(TypedDict):
    """
    Represents a single 'page' of quotes returned from the API,
    along with the necessary information to fetch the next page.
    """
    quotes: List[QuoteNodeGQL]
    next_cursor: Optional[str]
    has_next_page: bool

# --- Client Creation GQL TypedDicts ---
class ClientEmailInputGQL(TypedDict, total=False):
    address: str # Assuming 'address' corresponds to the email string
    primary: Optional[bool]
    # label: Optional[str] # If EmailCreateAttributes has a label

class ClientPhoneInputGQL(TypedDict, total=False):
    number: str # Assuming 'number' corresponds to the phone string
    primary: Optional[bool]
    type: Optional[str] # e.g., "work", "mobile", from a PhoneType enum
    # label: Optional[str] # If PhoneNumberCreateAttributes has a label

class ClientMutationInputGQL(TypedDict, total=False):
    """
    Represents the input for creating a client in Jobber, aligning with ClientCreateInput.
    Fields are based on the provided Jobber API documentation.
    """
    # Naming and Identification
    title: Optional[str]       # e.g., "Mr.", "Ms." Corresponds to ClientTitle.
    firstName: Optional[str]
    lastName: Optional[str]    # Documentation implies this is not strictly required (String, not String!)
    companyName: Optional[str]
    isCompany: Optional[bool]  # True if companyName should be the primary name.

    # Communication Preferences
    receivesReminders: Optional[bool]
    receivesFollowUps: Optional[bool]
    receivesQuoteFollowUps: Optional[bool]
    receivesInvoiceFollowUps: Optional[bool]
    receivesReviewRequests: Optional[bool]

    # Contact Information
    phones: Optional[List[ClientPhoneInputGQL]] 
    emails: Optional[List[ClientEmailInputGQL]] 


class QuoteCreateLineItemsInputGQL(TypedDict):
    """The 'lineItems' object nested within the mutation variables."""
    lineItems: List[QuoteLineEditItemGQL]

class QuoteCreateLineItemsVariablesGQL(TypedDict):
    """
    The complete, flattened variables for the quoteCreateLineItems mutation.
    This structure now has unique keys compared to other variable types in the Union.
    """
    quoteId: str
    lineItems: List[QuoteLineEditItemGQL]

class AddedLineItemNodeGQL(TypedDict):
    """Represents a line item within the returned quote's lineItems connection."""
    id: str

class AddedLineItemsEdgeGQL(TypedDict):
    """Edge for the lineItems connection."""
    node: AddedLineItemNodeGQL

class LineItemsConnectionGQL(TypedDict):
    """The lineItems connection on the returned quote object."""
    edges: List[AddedLineItemsEdgeGQL]
    totalCount: int

class QuoteAfterAddingItemsGQL(TypedDict):
    """The 'quote' object returned by the mutation."""
    id: str
    lineItems: LineItemsConnectionGQL

class QuoteCreateLineItemsPayloadGQL(TypedDict):
    """The 'quoteCreateLineItems' payload in the response data."""
    quote: Optional[QuoteAfterAddingItemsGQL]
    userErrors: Optional[List[UserError]]

class QuoteCreateLineItemsDataGQL(TypedDict):
    """The 'data' field in the GraphQL response for this specific mutation."""
    quoteCreateLineItems: QuoteCreateLineItemsPayloadGQL


class ClientCreateVariablesGQL(TypedDict): 
    input: ClientMutationInputGQL
class ClientObjectGQL(TypedDict): id: str; name: str # Structure of 'client' object in response
class ClientCreateDataPayloadGQL(TypedDict): client: Optional[ClientObjectGQL]; userErrors: Optional[List[UserError]] # Structure of 'clientCreate' in response data

# --- TypedDicts for Fetching a Quote's Line Items ---

class QuoteLineItemConnectionGQL(TypedDict):
    nodes: List[QuoteLineItemGQL]

class FullQuoteNodeGQL(TypedDict, total=False):
    """Represents a single, detailed quote fetched by its ID."""
    id: str
    lineItems: QuoteLineItemConnectionGQL

class GetQuoteDataGQL(TypedDict):
    quote: FullQuoteNodeGQL

class GetQuoteResponseGQL(TypedDict):
    data: GetQuoteDataGQL


# --- TypedDicts for Editing Line Items ---
class JobCreateLineItemsVariablesGQL(TypedDict):
    """The complete variables for the jobCreateLineItems mutation."""
    jobId: str
    input: JobCreateLineItemsInputGQL

class QuoteEditLineItemInputGQL(TypedDict):
    """Input for updating a single line item."""
    lineItemId: str
    quantity: float

class QuoteEditLineItemsVariablesGQL(TypedDict):
    """Variables for the quoteEditLineItems mutation."""
    quoteId: str
    lineItems: List[QuoteEditLineItemInputGQL]

class QuoteEditLineItemsPayloadGQL(TypedDict):
    """The 'quoteEditLineItems' payload in the response data."""
    userErrors: Optional[List[UserError]]


# ClientCreateResponseDataGQL (Optional - for typing the whole 'data' field for this specific mutation)
# class ClientCreateResponseDataGQL(TypedDict): clientCreate: Optional[ClientCreateDataPayloadGQL]


# --- Property Creation GQL TypedDicts ---
class PropertyAddressInputGQL(TypedDict, total=False):
    street1: Optional[str]; 
    street2: Optional[str]; 
    city: Optional[str]
    province: Optional[str]; 
    postalCode: Optional[str]; 
    country: Optional[str]

# Represents PropertyAttributes from Jobber documentation
class PropertyAttributesGQL(TypedDict, total=False):
    address: PropertyAddressInputGQL
    name: Optional[str]

# Represents PropertyCreateInput from Jobber documentation
class ActualPropertyCreateInputGQL(TypedDict): properties: List[PropertyAttributesGQL] # Must be a list

class PropertyCreateVariablesGQL(TypedDict):
    clientId: str  # Direct argument to propertyCreate
    input: ActualPropertyCreateInputGQL # The 'input' argument for propertyCreate

class PropertyObjectGQL(TypedDict): id: str; address: Optional[PropertyAddressInputGQL] # Structure of 'property' object
class PropertyCreateDataPayloadGQL(TypedDict): properties: Optional[List[PropertyObjectGQL]]; userErrors: Optional[List[UserError]] # Structure of 'propertyCreate' in response data
# PropertyCreateResponseDataGQL (Optional)
# class PropertyCreateResponseDataGQL(TypedDict): propertyCreate: Optional[PropertyCreateDataPayloadGQL]

# --- Quote Line Item for GQL Mutation ---



class CustomFieldCreateInputGQL(TypedDict, total=False):
    customFieldConfigurationId: str # EncodedId!
    valueText: Optional[str]
    # Add other value types (valueLink, valueArea, valueTrueFalse, valueNumeric, valueDropdown) if needed

class QuoteCreateAttributesGQL(TypedDict, total=False):
    clientId: str
    propertyId: str
    title: str
    message: Optional[str]
    lineItems: List[QuoteLineItemGQL]
    quoteNumber: Optional[int]
    contractDisclaimer: Optional[str]
    customFields: Optional[List[CustomFieldCreateInputGQL]]
    # clientViewOptions: Optional[QuoteClientViewOptionsInput]
        # Note: clientViewOptions can be used to control what the client sees,
        # e.g., show/hide line items, unit prices, quantities, totals, etc.

class QuoteCreateVariablesGQL(TypedDict): attributes: QuoteCreateAttributesGQL
class QuoteObjectGQL(TypedDict): id: str; quoteNumber: Optional[str]; quoteStatus: str # Structure of 'quote' object
class QuoteCreateDataPayloadGQL(TypedDict): quote: Optional[QuoteObjectGQL]; userErrors: Optional[List[UserError]] # Structure of 'quoteCreate' in response data



# General type for variables passed to _post; can be expanded with more specific variable types
GraphQLMutationVariables = Union[
    ClientCreateVariablesGQL,
    PropertyCreateVariablesGQL,
    QuoteCreateVariablesGQL,
    QuoteCreateLineItemsVariablesGQL, # For adding items to a quote
    QuoteEditLineItemsVariablesGQL,   # For editing items on a quote
    JobCreateLineItemsVariablesGQL,   # For adding items to a job
    JobEditLineItemsVariablesGQL,     # For editing items on a job
    Dict[str, Any]                    # Fallback for any other structure
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
    
    def get_all_products_and_services(self) -> List[Dict[str, str]]:
        """
        Fetches all products and services from Jobber, handling pagination.
        Returns a list of dictionaries, each with 'id' and 'name'.
        """
        print("INFO: Fetching all products and services from Jobber...")
        all_products: List[Dict[str, str]] = []
        cursor: Optional[str] = None
        
        # CORRECTED: Changed 'productsAndServices' to 'productOrServices'
        query = """
        query GetAllProducts($cursor: String) {
          productOrServices(first: 250, after: $cursor) {
            edges {
              cursor
              node {
                id
                name
              }
            }
            pageInfo {
              hasNextPage
            }
          }
        }
        """

        while True:
            try:
                variables = {"cursor": cursor} if cursor else {}
                raw_data = self._post(query, variables)
                
                # CORRECTED: Changed key to 'productOrServices'
                connection = raw_data.get("productOrServices", {})
                edges = connection.get("edges", [])
                
                for edge in edges:
                    node = edge.get("node")
                    if node and node.get("id") and node.get("name"):
                        all_products.append({
                            "id": node["id"],
                            "name": node["name"]
                        })

                page_info = connection.get("pageInfo", {})
                if page_info.get("hasNextPage") and edges:
                    cursor = edges[-1].get("cursor")
                else:
                    break # Exit the loop if there are no more pages

            except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
                print(f"ERROR: Failed to fetch products and services from Jobber: {e}")
                # Return what we have so far, or an empty list if it fails on the first go.
                break 
        
        print(f"SUCCESS: Retrieved {len(all_products)} products and services.")
        return all_products

    def get_jobs(self, cursor: Optional[str] = None) -> JobPageGQL:
        """
        Fetches a single page of active jobs from Jobber.

        Args:
            cursor: The cursor for the page to retrieve. If None, retrieves the first page.

        Returns:
            A JobPageGQL dictionary containing the list of jobs for the page
            and pagination info (next_cursor, has_next_page).

        Raises:
            RuntimeError: If the API call fails or returns an unexpected structure.
        """
        log_message = f"Fetching a page of active jobs starting from cursor: {cursor}" if cursor else "Fetching first page of active jobs."
        print(f"INFO: {log_message}")

        # CORRECTED arugment in filter from jobStatus to status
        query = """
        query GetActiveJobs($cursor: String) {
        jobs(first: 50, after: $cursor, filter: { status: active }) {
            edges {
            cursor
            node {
                id
                jobNumber
                title
                jobStatus
                client { id name }
                property { id address { street1 city province postalCode } }
                total
            }
            }
            pageInfo {
            hasNextPage
            }
        }
        }
        """
        variables = {"cursor": cursor} if cursor else {}

        try:
            raw_response: GraphQLData = self._post(query, variables)
            gql_response = cast(GetJobsResponseGQL, {"data": raw_response})

            jobs_connection = gql_response.get("data", {}).get("jobs")
            if not jobs_connection:
                raise RuntimeError("API response missing 'jobs' connection.")

            jobs_on_page: List[JobNodeGQL] = [
                edge["node"] for edge in jobs_connection.get("edges", []) if edge and "node" in edge
            ]

            page_info = jobs_connection.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)

            next_cursor: Optional[str] = None
            edges = jobs_connection.get("edges", [])
            if has_next_page and edges:
                next_cursor = edges[-1].get("cursor")

            print(f"SUCCESS: Retrieved {len(jobs_on_page)} active jobs. has_next_page: {has_next_page}")

            return {
                "jobs": jobs_on_page,
                "next_cursor": next_cursor,
                "has_next_page": has_next_page,
            }

        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            print(f"ERROR: Failed to fetch active jobs from Jobber: {e}")
            raise

    def get_quote_with_line_items(self, quote_id: str) -> Optional[FullQuoteNodeGQL]:
        """Fetches a single quote and its line items by ID."""
        print(f"INFO: Fetching full details for Jobber Quote ID: {quote_id}")
        query = """
        query GetQuoteDetails($quoteId: EncodedId!) {
          quote(id: $quoteId) {
            id
            lineItems {
              nodes {
                id
                name
                quantity
                unitPrice
              }
            }
          }
        }
        """
        variables = {"quoteId": quote_id}
        try:
            raw_data = self._post(query, variables)
            response = cast(GetQuoteResponseGQL, {"data": raw_data})
            return response["data"]["quote"]
        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            print(f"ERROR: Failed to fetch details for quote {quote_id}: {e}")
            return None

    def add_line_items_to_job(self, job_id: str, line_items: List[JobCreateLineItemGQL]) -> Tuple[bool, str]:
        """Adds NEW line items to an existing Jobber job."""
        if not line_items:
            return True, "No new line items to add."

        print(f"INFO: Adding {len(line_items)} new line item(s) to Jobber Job ID: {job_id}")

        # This mutation signature is now correct, accepting both $jobId and $input
        mutation = """
        mutation JobCreateLineItems($jobId: EncodedId!, $input: JobCreateLineItemsInput!) {
        jobCreateLineItems(jobId: $jobId, input: $input) {
            userErrors { message path }
            createdLineItems { id }
        }
        }
        """

        # This variables object now perfectly matches the required JSON structure and our TypedDicts
        variables: JobCreateLineItemsVariablesGQL = {
            "jobId": job_id,
            "input": {
                "lineItems": line_items
            }
        }

        try:
            # The variables are now correctly typed and structured.
            raw_data = self._post(mutation, variables) # type: ignore

            result = raw_data.get("jobCreateLineItems", {})

            user_errors = result.get("userErrors")
            if user_errors:
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors]
                return False, f"Failed to add line items to job due to user errors: {'; '.join(error_messages)}"

            created_items = result.get("createdLineItems")
            if created_items is None:
                return False, "Failed to add line items: API response did not confirm creation."

            return True, f"Successfully added {len(created_items)} new line item(s) to job {job_id}."

        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            return False, f"An error occurred while adding line items to job: {e}"    
    
    def update_line_items_on_job(self, job_id: str, line_items: List[JobEditLineItemGQL]) -> Tuple[bool, str]:
        """Updates existing line items on a job."""
        if not line_items:
            return True, "No line items needed updating."

        print(f"INFO: Updating {len(line_items)} line item(s) on Jobber Job ID: {job_id}")
        
        # Corrected Mutation: Now accepts jobId as a top-level argument.
        mutation = """
        mutation JobEditLineItems($jobId: EncodedId!, $input: JobEditLineItemsInput!) {
        jobEditLineItems(jobId: $jobId, input: $input) {
            userErrors { message path }
        }
        }
        """
        
        # Corrected Variables: Structure now matches the API's expectation.
        variables: JobEditLineItemsVariablesGQL = {
            "jobId": job_id,
            "input": {
                "lineItems": line_items
            }
        }
        
        try:
            raw_data = self._post(mutation, variables)
            response_data = cast(Dict[str, JobEditLineItemsPayloadGQL], raw_data)
            result = response_data.get("jobEditLineItems", {}) # Use .get() for safety
            
            user_errors = result.get("userErrors")
            if user_errors:
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors]
                return False, f"Failed to update line items on job due to user errors: {'; '.join(error_messages)}"
            
            return True, f"Successfully updated {len(line_items)} line item(s) on job {job_id}."
            
        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            return False, f"An error occurred while updating line items on job: {e}"
    
    def update_line_items_on_quote(self, quote_id: str, line_items: List[QuoteEditLineItemInputGQL]) -> Tuple[bool, str]:
        """Updates existing line items on a quote."""
        if not line_items:
            return True, "No line items needed updating."

        print(f"INFO: Updating {len(line_items)} line item(s) on Jobber Quote ID: {quote_id}")
        mutation = """
        mutation QuoteEditLineItems($quoteId: EncodedId!, $lineItems: [QuoteEditLineItemAttributes!]!) {
          quoteEditLineItems(quoteId: $quoteId, lineItems: $lineItems) {
            userErrors { message path }
          }
        }
        """
        variables: QuoteEditLineItemsVariablesGQL = {
            "quoteId": quote_id,
            "lineItems": line_items,
        }
        try:
            raw_data = self._post(mutation, variables) # type: ignore
            response_data = cast(Dict[str, QuoteEditLineItemsPayloadGQL], raw_data)
            result = response_data["quoteEditLineItems"]
            user_errors = result.get("userErrors")
            if user_errors:
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors]
                return False, f"Failed to update line items due to user errors: {'; '.join(error_messages)}"
            return True, f"Successfully updated {len(line_items)} line item(s)."
        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            return False, f"An error occurred while updating line items: {e}"

    def add_line_items_to_quote(self, quote_id: str, line_items: List[QuoteLineEditItemGQL]) -> Tuple[bool, str]:
        """
        Adds NEW line items to an existing Jobber quote.
        Now checks the 'createdLineItems' field in the response.
        """
        if not line_items:
            return True, "No new line items to add."
        mutation = """
        mutation QuoteCreateLineItems($quoteId: EncodedId!, $lineItems: [QuoteCreateLineItemAttributes!]!) {
          quoteCreateLineItems(quoteId: $quoteId, lineItems: $lineItems) {
            createdLineItems {
              id
            }
            userErrors {
              message
              path
            }
          }
        }
        """
        variables: QuoteCreateLineItemsVariablesGQL = {
            "quoteId": quote_id,
            "lineItems": line_items,
        }

        try:
            raw_data: GraphQLData = self._post(mutation, variables) #type:ignore
            # The top-level key is 'quoteCreateLineItems'
            result: Dict[str, Any] = raw_data["quoteCreateLineItems"]

            user_errors = result.get("userErrors")
            if user_errors:
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors]
                return False, f"Failed to add line items due to user errors: {'; '.join(error_messages)}"

            # Check the 'createdLineItems' field as per new documentation.
            created_items = result.get("createdLineItems")
            if created_items is None: # It can be an empty list, but not None if the call was successful
                return False, "Failed to add line items: API response did not include the 'createdLineItems' field."

            success_message = f"Successfully added {len(created_items)} new line item(s) to quote {quote_id}."
            return True, success_message

        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            return False, f"An error occurred while adding line items: {e}"
        except (KeyError, TypeError) as e:
            return False, f"An error occurred while parsing the API response: {e}. The response structure may have changed."

   
    def create_client_and_property(self, order: SaberisOrder) -> Tuple[str, str]:
        """Creates a client and then a property for that client in Jobber."""
        client_name_str = order.customer_name.strip() # Get customer name from SaberisOrder
        print(f"INFO: Attempting to create Jobber client for: '{client_name_str}'")

        client_create_mutation = """
        mutation ClientCreate($input: ClientCreateInput!) {
          clientCreate(input: $input) {
            client { id name }
            userErrors { message path }
          }
        }"""

        client_mutation_input_gql: ClientMutationInputGQL = {}

        # Heuristic to determine if the name is a company or an individual
        # This can be customized based on common patterns in your Saberis data
        company_keywords = [" INC", " LLC", " CORP", " LTD", "COMPANY", "GROUP", "SERVICE", "SOLUTION"] # Add common suffixes/keywords
        # Check if any part of the name (uppercase) contains these keywords.
        # A more sophisticated check might look at word endings or specific structures.
        is_likely_company = any(keyword in client_name_str.upper() for keyword in company_keywords)

        if is_likely_company:
            client_mutation_input_gql["companyName"] = client_name_str
            client_mutation_input_gql["isCompany"] = True
            # Optional: Jobber might still prefer a lastName for a primary contact at the company.
            # If API errors about missing lastName, you could set a default:
            # client_mutation_input_gql["lastName"] = "Contact"
        else:
            name_parts = client_name_str.split(None) # Split by any whitespace
            if len(name_parts) >= 2: # e.g., "John Doe" or "Mary Anne Smith"
                client_mutation_input_gql["firstName"] = name_parts[0]
                client_mutation_input_gql["lastName"] = " ".join(name_parts[1:])
            elif len(name_parts) == 1 and name_parts[0]: # e.g., "Cher" or a single-word company name missed by keywords
                # If it's a single word and not flagged as a company, assume it's a person's last name.
                client_mutation_input_gql["lastName"] = name_parts[0]
            else:
                # Fallback if client_name_str is empty after stripping.
                # This should ideally be caught by validation earlier.
                print(f"Warning: Client name '{order.customer_name}' is empty or invalid. Using fallback.")
                client_mutation_input_gql["lastName"] = "Unknown" # Jobber usually appreciates a lastName
                client_mutation_input_gql["firstName"] = "Client" # Placeholder
            client_mutation_input_gql["isCompany"] = False

        client_variables: ClientCreateVariablesGQL = {"input": client_mutation_input_gql}
        client_id: str
        try:
            raw_client_response_data: GraphQLData = self._post(client_create_mutation, client_variables)
            
            client_create_payload_dict = raw_client_response_data.get("clientCreate")
            if not isinstance(client_create_payload_dict, dict):
                print(f"ERROR: Unexpected response structure for clientCreate for '{client_name_str}'. Expected dict, got {type(client_create_payload_dict)}. Response: {raw_client_response_data}")
                raise RuntimeError(f"Unexpected response structure for clientCreate: {raw_client_response_data}")
            
            client_create_data: ClientCreateDataPayloadGQL = cast(ClientCreateDataPayloadGQL, client_create_payload_dict)
            
            user_errors = client_create_data.get("userErrors")
            if user_errors:
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors]
                print(f"ERROR: Jobber userErrors creating client '{client_name_str}': {'; '.join(error_messages)}")
                raise RuntimeError(f"Error creating Jobber client '{client_name_str}': {'; '.join(error_messages)}")

            client_object = client_create_data.get("client")
            if not client_object or not client_object.get("id"):
                print(f"ERROR: Client creation response missing client ID or client object for '{client_name_str}'. Response: {client_create_data}")
                raise RuntimeError(f"Client creation response missing client ID or client object for '{client_name_str}': {client_create_data}")

            client_id = client_object["id"]
            created_client_jobber_name = client_object.get('name', client_name_str)
            print(f"SUCCESS: Created Jobber client '{created_client_jobber_name}' with ID: {client_id}")

        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            print(f"ERROR: Failed to create Jobber client for '{client_name_str}': {e}")
            raise
        except Exception as e:
            print(f"ERROR: Unexpected error creating Jobber client for '{client_name_str}': {e}")
            raise

        # --- Property Creation ---
        print(f"INFO: Attempting to create Jobber property for client ID: {client_id}")
        property_create_mutation = """
        mutation PropertyCreate($clientId: EncodedId!, $input: PropertyCreateInput!) {
        propertyCreate(clientId: $clientId, input: $input) {
            properties { # <-- Changed from 'property' to 'properties'
                id
                address { street city province postalCode }
            }
            userErrors { message path }
        }
        }"""
        saberis_addr: ShippingAddress = order.shipping_address
        # Filter None values from Saberis address to build PropertyAddressInputGQL
        temp_property_address: Dict[str, Any] = {
            "street1": saberis_addr.get("street1"), 
            "street2": saberis_addr.get("street2"), 
            "city": saberis_addr.get("city"),
            "province": saberis_addr.get("province"), 
            "postalCode": saberis_addr.get("postalCode"),
            "country": saberis_addr.get("country")
        }

        filtered_address_dict = {k: v for k, v in temp_property_address.items() if v is not None and v != ""}
        property_address_gql: PropertyAddressInputGQL = cast(PropertyAddressInputGQL, filtered_address_dict)
        property_attributes_item: PropertyAttributesGQL = {"address": property_address_gql}
        actual_input_for_mutation: ActualPropertyCreateInputGQL = {
            "properties": [property_attributes_item]
        }

        property_variables: PropertyCreateVariablesGQL = {
            "clientId": client_id,
            "input": actual_input_for_mutation
        }
        property_id: str

        try:
            raw_property_response_data: GraphQLData = self._post(property_create_mutation, property_variables)
            
            property_create_payload_dict = raw_property_response_data.get("propertyCreate")
            if not isinstance(property_create_payload_dict, dict):
                print(f"ERROR: Unexpected response structure for propertyCreate for client ID '{client_id}'. Expected dict, got {type(property_create_payload_dict)}. Response: {raw_property_response_data}")
                raise RuntimeError(f"Unexpected response structure for propertyCreate: {raw_property_response_data}")
            property_create_data: PropertyCreateDataPayloadGQL = cast(PropertyCreateDataPayloadGQL, property_create_payload_dict)
            
            user_errors = property_create_data.get("userErrors") # This is fine
            if user_errors:                                      # This is fine
                error_messages = [f"Path: {e.get('path', 'N/A')}, Message: {e.get('message', 'Unknown error')}" for e in user_errors]
                print(f"ERROR: Jobber userErrors creating property for client ID '{client_id}': {'; '.join(error_messages)}")
                raise RuntimeError(f"Error creating Jobber property for client ID '{client_id}': {'; '.join(error_messages)}")

            # Corrected logic for extracting property from 'properties' list:
            returned_properties_list = property_create_data.get("properties")

            if not returned_properties_list or len(returned_properties_list) == 0:
                print(f"ERROR: Property creation response missing 'properties' list or list is empty for client ID '{client_id}'. Response: {property_create_data}")
                raise RuntimeError(f"Property creation response missing 'properties' list or list is empty for client ID '{client_id}'")

            property_object = returned_properties_list[0] # Get the first property from the list

            if not property_object or not property_object.get("id"): # property_object is now an item from the list
                print(f"ERROR: Property object in list missing ID for client ID '{client_id}'. Response: {property_object}")
                raise RuntimeError(f"Property object in list missing ID for client ID '{client_id}'")

            property_id = property_object["id"]
            print(f"SUCCESS: Created Jobber property with ID: {property_id} for client ID: {client_id}")
        
        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            print(f"ERROR: Failed to create Jobber property for client ID '{client_id}': {e}")
            raise
        except Exception as e:
            print(f"ERROR: Unexpected error creating Jobber property for client ID '{client_id}': {e}")
            raise
            
        return client_id, property_id
    
    def get_job_with_line_items(self, job_id: str) -> Optional[FullJobNodeGQL]:
        """Fetches a single job and its line items by ID."""
        print(f"INFO: Fetching full details for Jobber Job ID: {job_id}")
        query = """
        query GetJobDetails($jobId: EncodedId!) {
        job(id: $jobId) {
            id
            lineItems {
            nodes {
                id
                name
                quantity
                unitPrice
            }
            }
        }
        }
        """
        variables = {"jobId": job_id}
        try:
            raw_data = self._post(query, variables)
            response = cast(GetJobResponseGQL, {"data": raw_data})
            return response["data"]["job"]
        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            print(f"ERROR: Failed to fetch details for job {job_id}: {e}")
            return None

    def get_approved_quotes(self, cursor: Optional[str] = None) -> QuotePageGQL:
        """
        Fetches a single page of approved quotes from Jobber.

        Args:
            cursor: The cursor for the page to retrieve. If None, retrieves the first page.

        Returns:
            A QuotePageGQL dictionary containing the list of quotes for the page
            and pagination info (next_cursor, has_next_page).
        
        Raises:
            RuntimeError: If the API call fails or returns an unexpected structure.
        """
        log_message = f"Fetching a page of approved quotes starting from cursor: {cursor}" if cursor else "Fetching first page of approved quotes."
        print(f"INFO: {log_message}")

        query = """
        query GetApprovedQuotes($cursor: String) {
          quotes(first: 50, after: $cursor, filter: { status: approved }) {
            edges {
              cursor
              node {
                id
                quoteNumber
                title
                transitionedAt
                client { id name }
                property { id address { street1 city province postalCode } }
                amounts { total }
              }
            }
            pageInfo {
              hasNextPage
            }
          }
        }
        """
        variables = {"cursor": cursor} if cursor else {}

        try:
            raw_response: GraphQLData = self._post(query, variables)
            gql_response = cast(GetQuotesResponseGQL, {"data": raw_response})
            
            quotes_connection = gql_response.get("data", {}).get("quotes")
            if not quotes_connection:
                raise RuntimeError("API response missing 'quotes' connection.")

            # Extract the list of quotes from the edges
            quotes_on_page: List[QuoteNodeGQL] = [
                edge["node"] for edge in quotes_connection.get("edges", []) if edge and "node" in edge
            ]

            # Determine pagination status
            page_info = quotes_connection.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            
            next_cursor: Optional[str] = None
            edges = quotes_connection.get("edges", [])
            if has_next_page and edges:
                # The cursor for the *next* page is the cursor of the *last* item on this page
                next_cursor = edges[-1].get("cursor")

            print(f"SUCCESS: Retrieved {len(quotes_on_page)} approved quotes. has_next_page: {has_next_page}")

            return {
                "quotes": quotes_on_page,
                "next_cursor": next_cursor,
                "has_next_page": has_next_page,
            }

        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            print(f"ERROR: Failed to fetch approved quotes from Jobber: {e}")
            raise
    
    # UNUSED, but helpful if we ever decide to automate quote creation
    def create_quote(self, app_quote_payload: QuoteCreateInput) -> Tuple[Optional[str], str]:
        """Creates quote in Jobber. Returns (quote_id, status_message)."""
        quote_id: Optional[str] = None
        status_message: str = "Quote processing initiated."

        print(f"INFO: Preparing to create quote with title: '{app_quote_payload.title}' for client: {app_quote_payload.client_id}")
        
        quote_lines_for_gql: List[QuoteLineItemGQL] = []
        for li_model in app_quote_payload.line_items:
            # Transformation from application model (QuoteLineInput) to GQL model (QuoteLineItemGQL)
            item_gql: QuoteLineItemGQL = {
                "id": "test_id",
                "name": li_model.name,
                "quantity": li_model.quantity,
                "unitPrice": li_model.unit_price,
                "taxable": li_model.taxable,
                "saveToProductsAndServices": True,
                "productOrServiceId": None,
                "description": li_model.description,
                "unitCost": -1,
            }
            if li_model.unit_cost is not None:
                item_gql["unitCost"] = li_model.unit_cost
            quote_lines_for_gql.append(item_gql)

        quote_attributes_gql: QuoteCreateAttributesGQL = {
            "clientId": app_quote_payload.client_id,
            "propertyId": app_quote_payload.property_id,
            "title": app_quote_payload.title, 
            "message": app_quote_payload.message,
            "lineItems": quote_lines_for_gql
        }

        variables_create: QuoteCreateVariablesGQL = {"attributes": quote_attributes_gql}

        create_mutation = """
        mutation QuoteCreate($attributes: QuoteCreateAttributes!) {
        quoteCreate(attributes: $attributes) { 
            quote { id quoteNumber quoteStatus } 
            userErrors { message path } 
        }
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
            print(f"SUCCESS: {status_message} For title: '{app_quote_payload.title}'.")
            success_message = f"Quote (ID: {quote_id}) sent. New status: {status_message}."
            return quote_id, success_message
        
        except (ConnectionRefusedError, requests.exceptions.RequestException, RuntimeError) as e:
            # These are errors from _post or local logic during creation
            status_message = f"Quote creation failed for '{app_quote_payload.title}': {e}"
            print(f"ERROR: {status_message}")
            return None, status_message # Return None for quote_id and the error message
        
        except Exception as e: # Other unexpected errors during creation
            status_message = f"Unexpected error creating quote '{app_quote_payload.title}': {e}"
            print(f"ERROR: {status_message}")
            return None, status_message