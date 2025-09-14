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
A 'visible' product or service will show up as an autocomple

ProductsAndServicesEditInput
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

ProductsAndServicesInput
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

Docs
ProductsAndServicesSortInput
The attributes to sort on products and services detail data

Fields
key: ProductsAndServicesSortKey!
The key to sort on

direction: SortDirectionEnum!
The direction of the sort

ProductsAndServicesSortKey
The fields, on a collection of ProductsAndServices which support sorting functionality

Enum Values
NAME
The product or service name

CATEGORY
The product or service category

ProductsFilterInput
Attributes for filtering products

Fields
category: [WorkItemCategoryTypeEnum!]
The item's category

sort: ProductsAndServicesSortInput
The sorting options

ids: [EncodedId!]
The ids of the products and services to filter by