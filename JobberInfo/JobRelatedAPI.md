# Job
A detailed contract of work which Service Providers use to schedule work for a Service Consumer

Implements
CustomFieldsInterface
Fields
allowReviewRequest: Boolean!
Allow SMS to be sent to client for Google Reviews feature

arrivalWindow: ArrivalWindow
The time window during which the SP can arrive at the job

billingType: BillingStrategy!
Invoicing strategy selected for the job

bookingConfirmationSentAt: ISO8601DateTime
The time when booking confirmation for the job was sent

client: Client!
The client on the job

completedAt: ISO8601DateTime
The completion date of the job

createdAt: ISO8601DateTime!
The time the job was created

customFields: [CustomFieldUnion!]!
The custom fields set for this object

defaultVisitTitle: String!
The default title for new visits

endAt: ISO8601DateTime
End date of the job

expenses(
after: String
before: String
first: Int
last: Int
): ExpenseConnection!
Expenses associated with the job

id: EncodedId!
The unique identifier

instructions: String
The instructions on a job

invoiceSchedule: InvoiceSchedule!
Schedule of invoices

invoicedTotal: Float!
The total invoiced amount of the job

invoices(
after: String
before: String
first: Int
last: Int
sort: [InvoiceSortInput!]
): InvoiceConnection!
The invoices associated with the job

jobBalanceTotals: JobBalanceTotals
The total and outstanding balance of the job based on invoice and quote deposits

jobCosting: JobCosting
The job costing fields representing the profitability of the job

jobNumber: Int!
The number of the job

jobStatus: JobStatusTypeEnum!
The status of the job

jobType: JobTypeTypeEnum!
The type of job

jobberWebUri: String!
The URI for the given record in Jobber Online

lineItems(
after: String
before: String
first: Int
last: Int
): JobLineItemConnection!
The line items associated with the job

nextDateToSendReviewSms: ISO8601DateTime
The next available date to send an SMS review request

noteAttachments(
sort: [NoteAttachmentSortAttributes!]
after: String
before: String
first: Int
last: Int
): JobNoteFileConnection!
The note files attached to the job

notes(
sort: [NotesSortInput!]
after: String
before: String
first: Int
last: Int
): JobNoteUnionConnection!
The notes attached to the job

paymentRecords(
after: String
before: String
first: Int
last: Int
): PaymentRecordConnection!
The payment records applied to this job's invoices

property: Property!
The property associated with the job

quote: Quote
When applicable, the quote associated with the job

request: Request
When applicable, the request associated with the job

salesperson: User
Salesperson for the job

source: Source!
The originating source of the job

startAt: ISO8601DateTime
Start date of the job

timeSheetEntries(
after: String
before: String
first: Int
last: Int
): TimeSheetEntryConnection!
A list of all timesheet entries for this job

title: String
The scheduling information of the job

total: Float!
The total chargeable amount of the job

uninvoicedTotal: Float!
The total uninvoiced amount of the job

updatedAt: ISO8601DateTime!
The last time the job was changed in a way that is meaningful to the Service Provider

visitSchedule: VisitSchedule!
Schedule of visits

visits(
after: String
before: String
first: Int
last: Int
filter: VisitFilterAttributes
sort: [VisitsSortInput!]
timezone: Timezone
): VisitConnection!
The scheduled or unscheduled visits to the customer's property to complete the work associated with this job

visitsInfo: VisitsInfo!
Information about jobs visits

willClientBeAutomaticallyCharged: Boolean
The setting for automatic invoice charges


# JobLineItem
A job line item

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

name: String!
The name of the line item

quantity: Float!
The quantity of the line item

taxable: Boolean!
If the line item is taxable

totalCost: Float
The total (internal) cost of the line item

totalPrice: Float!
The total price of the line item

unitCost: Float
The unit cost of the line item

unitPrice: Float!
The unit price of the line item

updatedAt: ISO8601DateTime!
The last DateTime the line item was changed in a way that is meaningful to the Service Provider

Show Deprecated Fields

# JobLineItemEdge
An edge in a connection.

Fields
cursor: String!
A cursor for use in pagination.

node: JobLineItem!
The item at the end of the edge.

# JobLineItemConnection
The connection type for JobLineItem.

Fields
edges: [JobLineItemEdge!]
A list of edges.

nodes: [JobLineItem!]!
A list of nodes.

pageInfo: PageInfo!
Information to aid in pagination.

totalCount: Int!
The total count of possible records in this list. Supports filters.
Please use with caution. Using totalCount raises the likelyhood you will be throttled

# ProductOrService
The collection of attributes that represent a product or service

Implements
CustomFieldsInterface
Fields
bookableType: SelfServeBooking
The type of booking to be created in online booking for the product or service

category: ProductsAndServicesCategory!
The item's category

customFields: [CustomFieldUnion!]!
The custom fields set for this object

defaultUnitCost: Float!
A product or service has a default price

description: String
The description of product or service

durationMinutes: Minutes
The duration of the service in minutes

id: EncodedId!
The unique identifier

internalUnitCost: Float
A product or service has a default internal unit cost

lastJobLineItem(propertyId: EncodedId): JobLineItem
The last line item created for this product or service

markup: Float
A product or service has a default markup

name: String!
The name of the product or service

onlineBookingSortOrder: Int
Sort order of the service on the booking page

onlineBookingsEnabled: Boolean
Whether the service is enabled on the booking page

quantityRange: QuantityRange
Quantity range for the product or service when created through online booking

taxable: Boolean
A product or service can be taxable or non-taxable

visible: Boolean
A 'visible' product or service will show up as an autocomplete suggestion on quotes/jobs/invoice line items