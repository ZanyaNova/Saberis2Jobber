
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

# ProductsAndServicesEditInput
Attributes for updating a product or service

Fields
description: String
The description for the service or product

taxable: Boolean
Whether the product or service will be taxable

markup: Float
Whether the product or service will have a default markup

internalUnitCost: Float
The default unit cost for the product or service

durationMinutes: Int
Duration to complete the service in minutes

onlineBookingsEnabled: Boolean
The product or service is also available as a bookable service

quantityRange: QuantityRangeInput
Quantity range for the product or service when created through online booking

bookableType: SelfServeBooking
The type of the product or service when created through online booking

name: String
Name of the product or service item

defaultUnitCost: Float
The default price for the service or product

visible: Boolean
Whether the product or service will be visible

customFields: [CustomFieldEditInput!]
List of custom fields to modify or add

category: ProductsAndServicesCategory
Whether this item will be a product or a service

# ProductsAndServicesInput
Attributes for creating a product or service

Fields
description: String
The description for the service or product

taxable: Boolean
Whether the product or service will be taxable

markup: Float
Whether the product or service will have a default markup

internalUnitCost: Float
The default unit cost for the product or service

durationMinutes: Int
Duration to complete the service in minutes

onlineBookingsEnabled: Boolean
The product or service is also available as a bookable service

quantityRange: QuantityRangeInput
Quantity range for the product or service when created through online booking

bookableType: SelfServeBooking
The type of the product or service when created through online booking

name: String!
Name of the product or service item

defaultUnitCost: Float!
The default price for the service or product

category: ProductsAndServicesCategory
Whether this item will be a product or a service

customFields: [CustomFieldCreateInput!]
List of custom fields to add

# ProductsAndServicesSortInput
The attributes to sort on products and services detail data

Fields
key: ProductsAndServicesSortKey!
The key to sort on

direction: SortDirectionEnum!
The direction of the sort

# mutation.productsAndServicesCreate
Create a new product or service

Type
CreatePayload!
Arguments
input: ProductsAndServicesInput!
Attributes of the new product or service