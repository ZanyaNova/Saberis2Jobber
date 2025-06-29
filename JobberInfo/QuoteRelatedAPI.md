# Quote
A cost estimate of work which Service Providers send to their clients before any work is done

Implements
CustomFieldsInterface
Fields
amounts: QuoteAmounts!
All amounts related to the quote

client: Client
The client the quote was made for

clientHubUri: String
The URI of the quote in client hub

clientHubViewedAt: ISO8601DateTime
Time the quote was viewed at in Client Hub

contractDisclaimer: String
The contract disclaimer for the quote

createdAt: ISO8601DateTime!
The time the quote was created

customFields: [CustomFieldUnion!]!
The custom fields set for this object

depositAmountUnallocated: Float
Paid deposit amount that is not yet associated with an invoice

depositRecords(
after: String
before: String
first: Int
last: Int
filter: PaymentRecordFilterAttributes
): PaymentRecordConnection!
The deposit records applied to the quote

id: EncodedId!
The unique identifier

jobberWebUri: String!
The URI for the given record in Jobber Online

jobs(
after: String
before: String
first: Int
last: Int
sort: [QuoteJobsSortInput!]
): JobConnection
Job IDs converted from this quote

lastTransitioned: QuoteLastTransitioned!
The last transitioned dates of a quote

lineItems(
after: String
before: String
first: Int
last: Int
filter: QuoteLineItemFilterAttributes
): QuoteLineItemConnection!
The line items associated with the quote

message: String
The message to the client

noteAttachments(
sort: [NoteAttachmentSortAttributes!]
after: String
before: String
first: Int
last: Int
): QuoteNoteFileConnection!
The note files attached to the quote

notes(
sort: [NotesSortInput!]
after: String
before: String
first: Int
last: Int
): QuoteNoteUnionConnection!
The notes attached to the quote

property: Property
The property the quote was made for

quoteNumber: String!
A non-unique number assigned to the quote by a Service Provider

quoteStatus: QuoteStatusTypeEnum!
The current status the quote

request: Request
The request associated with the quote

salesperson: User
Salesperson for the quote

taxDetails: TaxDetails
The tax rate and amount details

title: String
The description of the quote

transitionedAt: ISO8601DateTime!
Time the quote transitioned to its current status

unallocatedDepositRecords(
after: String
before: String
first: Int
last: Int
): PaymentRecordConnection!
The deposit records that haven't been applied to an invoice and have not been refunded

updatedAt: ISO8601DateTime!
The last time the quote was changed in a way that is meaningful to the Service Provider

# QuoteConnection

The connection type for Quote.

Fields
edges: [QuoteEdge!]
A list of edges.

nodes: [Quote!]!
A list of nodes.

pageInfo: PageInfo!
Information to aid in pagination.

totalCount: Int!
The total count of possible records in this list. Supports filters.
Please use with caution. Using totalCount raises the likelyhood you will be throttled

# QuoteEdge
An edge in a connection.

Fields
cursor: String!
A cursor for use in pagination.

node: Quote!
The item at the end of the edge.

# QuoteFilterAttributes
Attributes for filtering quotes

Fields
clientId: EncodedId
The encoded id of the client to filter by

quoteNumber: IntRangeInput
The quote number to filter by

status: QuoteStatusTypeEnum
The quote status to filter by

cost: FloatRangeInput
The quote cost to filter by

sentAt: Iso8601DateTimeRangeInput
The quote sent at date to filter by

updatedAt: Iso8601DateTimeRangeInput
The quote updated at date to filter by

createdAt: Iso8601DateTimeRangeInput
The quote created at date to filter by

salespersonId: EncodedId
The encoded id of the salesperson to filter by

# QuoteStatusTypeEnum
Enum Values
draft
The default state of a quote

awaiting_response
The state when the quote is sent to a client

archived
The state when a quote is archived

approved
The state when a quote is approved by a client

converted
The state when a quote is converted to a job

changes_requested
The state when a client request changes to the quote

# QuoteLineItem
A quote line item

Implements
LineItemInterface
Fields
category: ProductsAndServicesCategory!
The category of the line item

createdAt: ISO8601DateTime!
The DateTime the line item was created

description: String!
The description of the line item

id: EncodedId!
The unique identifier

linkedProductOrService: ProductOrService
The product or service from the Service Providers saved Products and Services list that was used to create this line item

markup: Float
The markup of the line item

name: String!
The name of the line item

optional: Boolean!
Is the line item considered optional?

quantity: Float!
The quantity of the line item

recommended: Boolean
When the line item is optional, is it recommended or has it been selected to be included by the client?

sortOrder: Int
The sort order of the line item

taxable: Boolean!
If the line item is taxable

textOnly: Boolean!
Is the line item text only (doesn't include quantity and price information)

totalCost: Float
The total cost of the line item

totalPrice: Float!
The total price of the line item

unitCost: Float
The unit cost of the quote line item

unitPrice: Float!
The unit price of the line item

updatedAt: ISO8601DateTime!
The last DateTime the line item was changed in a way that is meaningful to the Service Provider

# Client
Clients are the customers who pay for services on Jobber's platform - they belong to the Jobber account / service provider.

Implements
CustomFieldsInterface
Fields
balance: Float!
The client's current balance

billingAddress: ClientAddress
The billing address of the client

billingAddressPresent: Boolean!
Is a custom billing address present for this client?

clientProperties(
after: String
before: String
first: Int
last: Int
): PropertyConnection!
The properties belonging to the client which are serviced by the service provider

companyName: String
The name of the business

contacts(
sort: [ContactsSortInput!]
filter: ContactFilterInput
after: String
before: String
first: Int
last: Int
): ContactModelConnection!
The contacts associated with the client

createdAt: ISO8601DateTime!
The time the client was created

customFields: [CustomFieldUnion!]!
The custom fields set for this object

defaultEmails(emailType: EmailTypes): [String!]!
The email address stored from previous communications.

defaultPhones(messageType: WorkObjectSendMessageType): [String!]!
Default phone numbers to fetch for the given message type.

emails(filter: EmailFilterInput): [Email!]!
The email addresses belonging to the client

firstName: String!
The first name of the client

id: EncodedId!
The unique identifier

invoices(
after: String
before: String
first: Int
last: Int
): InvoiceConnection!
The invoices associated with the client

isArchivable: Boolean!
Is the client archivable

isArchived: Boolean!
Is the client archived

isCompany: Boolean!
Does the client represent a business

isLead: Boolean!
Is the client a prospective lead for the service provider

jobberWebUri: String!
The URI for the given record in Jobber Online

jobs(
after: String
before: String
first: Int
last: Int
filter: JobFilterAttributes
sort: [JobsSortInput!]
): JobConnection!
The jobs associated with the client

lastName: String!
The last name of the client

name: String!
The primary name of the client

noteAttachments(
sort: [NoteAttachmentSortAttributes!]
after: String
before: String
first: Int
last: Int
): ClientNoteFileConnection!
The note files attached to the client

notes(
sort: [NotesSortInput!]
after: String
before: String
first: Int
last: Int
): ClientNoteConnection!
The notes attached to the client

phones(filter: PhoneFilterInput): [ClientPhoneNumber!]!
The phone numbers belonging to the client

quotes(
after: String
before: String
first: Int
last: Int
): QuoteConnection!
The quotes associated with the client

receivesFollowUps: Boolean!
Does the client receive job follow ups

receivesInvoiceFollowUps: Boolean!
Does the client receive invoice follow ups

receivesQuoteFollowUps: Boolean!
Does the client receive quote follow ups

receivesReminders: Boolean!
Does the client receive assessment or visit reminders

receivesReviewRequests: Boolean!
Does the client receive review requests

requests(
after: String
before: String
first: Int
last: Int
): RequestConnection!
The requests associated with the client

sampleData: Boolean!
Is the client sample data

secondaryName: String
The secondary name of the client

sourceAttribution: SourceAttribution
The source of the client object

tags(
after: String
before: String
first: Int
last: Int
): TagConnection!
The custom tags added to the client

title: String
The title of the client

updatedAt: ISO8601DateTime!
The last time the client was updated

workObjects(
after: String
before: String
first: Int
last: Int
): WorkObjectUnionConnection
The client's requests, quotes, jobs, and invoices sorted descending by modified date

# Property
Properties are locations owned by Service Consumers where Service Providers provide service for

Implements
CustomFieldsInterface
Fields
address: PropertyAddress!
The address of the property

client: Client
The client associated with the property

contacts(
sort: [ContactsSortInput!]
after: String
before: String
first: Int
last: Int
): ContactModelConnection
The contacts associated with the property

customFields: [CustomFieldUnion!]!
The custom fields set for this object

id: EncodedId!
The unique identifier

isBillingAddress: Boolean
Whether the property is a billing address

jobberWebUri: String!
The URI for the given record in Jobber Online

jobs(
after: String
before: String
first: Int
last: Int
): JobConnection!
The jobs associated with the property

name: String
The name of the property

quotes(
after: String
before: String
first: Int
last: Int
): QuoteConnection!
The quotes associated with the property

requests(
after: String
before: String
first: Int
last: Int
): RequestConnection!
The requests associated with the property

routingOrder: Int
The routing order of the property

taxRate: TaxRate
The tax rate of the property