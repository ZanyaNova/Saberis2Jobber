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

# JobCreateLineItemsInput
Inputs for creating a new line item on a job

Fields
lineItems: [JobCreateLineItemAttributes!]!
The attributes of the created line items

# JobCreateLineItemAttributes
Attributes for creating a new line item on a job

Fields
name: String!
The name of the line item

description: String
The description of the line item

category: ProductsAndServicesCategory
The category of the line item

taxable: Boolean
Is the line item taxable

saveToProductsAndServices: Boolean!
Save a copy of the new line item to products and services for future use

quoteLineItemId: EncodedId
The quote line item id related to this line item

unitCost: Float
The unit cost of the line item

quantity: Float!
The quantity of the line item

unitPrice: Float!
The unit price of the line item

# JobCreateLineItemsPayload
Autogenerated return type of JobCreateLineItems.

Fields
createdLineItems: [JobLineItem!]!
The line items which have been created successfully

job: Job!
The job modified when creating line items

userErrors: [MutationErrors!]!
Errors encountered when modifying the job

# JobEditLineItemsInput
Input for editing line items on a job

Fields
lineItems: [JobEditLineItemAttributes!]!
The attributes of the edited line items

# JobEditLineItemAttributes
Attributes for editing a line item on a job

Fields
lineItemId: EncodedId!
The unique identifier of the line item

name: String
The name of the line item

description: String
The description of the line item

unitPrice: Float
The unit price of the line item

quantity: Float
The quantity of the line item

taxable: Boolean
Is the line item taxable

category: ProductsAndServicesCategory
The category of the line item

unitCost: Float
The internal unit cost of the line item.

# JobStatusTypeEnum
requires_invoicing
Jobs that are in requires invoicing status have an overdue invoice reminder. This is a prompt to create an invoice for this job.

archived
These are closed jobs that no longer need to be invoiced. These are the jobs that you are done with.

late
Active jobs with a visit pass but was not marked complete.

today
Active jobs with a visit today.

upcoming
Active jobs with a visit in the future (after today).

action_required
These are jobs that are still active, but they have no more upcoming visits. You can think of action required like being 'on hold'. Action required is a prompt to either schedule more visits or close the job.

on_hold
These are jobs that are still active, but they have no more upcoming visits. You can think of action required like being 'action required'. On hold is a prompt to either schedule more visits or close the job. (alias for action_required)

unscheduled
These are jobs that have visits created, but the visits have been set up to be scheduled later.

active
Active jobs are the jobs in progress (the job is not closed). This includes other statuses (late, today, upcoming, ...).

expiring_within_30_days