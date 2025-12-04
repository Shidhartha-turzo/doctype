# Database Relationships Implementation Guide

## Overview

Implemented proper database relationships for Link fields in Doctype Engine. This enables true relational integrity between documents instead of just storing names in JSON.

## What Was Implemented

### 1. DocumentLink Model [YES]
**File**: `doctypes/models.py:293`

Handles **Many-to-One** and **One-to-One** relationships between documents.

**Key Features**:
- Source document → Target document relationship
- Field-level tracking (knows which field creates the link)
- CASCADE deletion for source (link removed when source deleted)
- PROTECT deletion for target (prevents deleting referenced documents)
- Automatic JSON sync (keeps document.data in sync with links)
- Validation (ensures field exists and is a link type)
- Unique constraint (one link per field per document)

**Example**: Order → Customer link
```python
# When you create an Order with a 'customer' link field
order = Document.objects.create(...)
customer = Document.objects.get(name="John Doe")

# A DocumentLink is automatically created
link = DocumentLink.objects.create(
    source_document=order,
    target_document=customer,
    field_name='customer'
)
```

### 2. DocumentLinkMultiple Model [YES]
**File**: `doctypes/models.py:375`

Handles **Many-to-Many** relationships (multiselect link fields).

**Key Features**:
- Multiple targets per field
- Order preservation
- Same PROTECT behavior for targets

**Example**: Project → Team Members (multiple)
```python
# Link project to multiple team members
for i, member in enumerate(team_members):
    DocumentLinkMultiple.objects.create(
        source_document=project,
        target_document=member,
        field_name='team_members',
        order=i
    )
```

### 3. Child Table Relationships (Already Existed) [YES]
**File**: `doctypes/models.py:198`

The `parent_document` field handles **One-to-Many** relationships for child tables.

**Example**: Sales Order → Sales Order Items
```python
# Create parent
order = Document.objects.create(
    doctype=sales_order_doctype,
    name="ORD-001",
    data={'customer': 'John'}
)

# Create children
item1 = Document.objects.create(
    doctype=order_item_doctype,
    parent_document=order,  # Links to parent
    data={'item_name': 'Widget', 'qty': 5}
)
```

## Relationship Types Supported

### 1. Many-to-One (Link Field)
**Use Case**: Multiple documents linking to the same document

```
[Order 1] ──┐
[Order 2] ──┼──> [Customer: John Doe]
[Order 3] ──┘
```

**Implementation**: DocumentLink model

**Example Fields**:
- Order → Customer
- Invoice → Customer
- Task → Project
- Employee → Department

### 2. One-to-Many (Child Table)
**Use Case**: Parent with multiple child records

```
[Sales Order] ──┬──> [Item 1]
                ├──> [Item 2]
                └──> [Item 3]
```

**Implementation**: parent_document ForeignKey

**Example Fields**:
- Sales Order → Order Items
- Invoice → Invoice Items
- Project → Tasks

### 3. Many-to-Many (Multiselect Link)
**Use Case**: Multiple documents linking to multiple documents

```
[Project 1] ──┬──> [User A] <──┬── [Project 2]
              ├──> [User B] <──┘
              └──> [User C]
```

**Implementation**: DocumentLinkMultiple model

**Example Fields**:
- Project → Team Members
- Task → Assigned To (multiple users)
- Document → Tags

## Database Schema

### DocumentLink Table
```sql
CREATE TABLE doctypes_documentlink (
    id BIGINT PRIMARY KEY,
    source_document_id BIGINT NOT NULL,  -- FK to doctypes_document
    target_document_id BIGINT NOT NULL,  -- FK to doctypes_document (PROTECT)
    field_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    created_by_id BIGINT NULL,           -- FK to auth_user

    UNIQUE (source_document_id, field_name),
    INDEX (source_document_id, field_name),
    INDEX (target_document_id)
);
```

### DocumentLinkMultiple Table
```sql
CREATE TABLE doctypes_documentlinkmultiple (
    id BIGINT PRIMARY KEY,
    source_document_id BIGINT NOT NULL,  -- FK to doctypes_document
    target_document_id BIGINT NOT NULL,  -- FK to doctypes_document (PROTECT)
    field_name VARCHAR(255) NOT NULL,
    order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL,

    INDEX (source_document_id, field_name),
    INDEX (target_document_id)
);
```

## Helper Methods Added to Document Model

### get_link(field_name)
Get the linked document for a link field.

```python
order = Document.objects.get(id=1)
customer = order.get_link('customer')
print(customer.name)  # "John Doe"
```

### set_link(field_name, target_document, user=None)
Set or update a link.

```python
order.set_link('customer', customer_doc, user=request.user)
```

### get_linked_documents(field_name)
Get all documents for a multiselect link field.

```python
project = Document.objects.get(id=1)
team = project.get_linked_documents('team_members')
for member in team:
    print(member.name)
```

### get_child_documents()
Get all child documents (for table fields).

```python
order = Document.objects.get(id=1)
items = order.get_child_documents()
for item in items:
    print(item.data['item_name'])
```

### get_referencing_documents()
Get all documents that link to this document (reverse lookup).

```python
customer = Document.objects.get(id=1)
orders = customer.get_referencing_documents()
print(f"{customer.name} has {len(orders)} orders")
```

## Views Integration

### document_create View
**File**: `doctypes/views.py:325`

When creating a document:
1. Gets available documents for each link field
2. Validates selected document IDs
3. Creates DocumentLink entries after document creation
4. Stores document name in JSON for backward compatibility

```python
# In the view:
link_field_options = {}
for field in fields:
    if field['type'] == 'link':
        link_doctype = Doctype.objects.get(name=field['link_doctype'])
        link_field_options[field['name']] = Document.objects.filter(
            doctype=link_doctype,
            is_deleted=False
        ).order_by('name')
```

### document_edit View
**File**: `doctypes/views.py:434`

When editing a document:
1. Loads existing link field options
2. Removes old DocumentLink entries for updated fields
3. Creates new DocumentLink entries
4. Updates JSON data to match

## Template Integration

### document_form.html
**File**: `doctypes/templates/doctypes/document_form.html:238`

Link fields are now rendered as dropdowns:

```django
{% elif field.type == 'link' %}
    <select name="{{ field.name }}" class="form-control">
        <option value="">-- Select {{ field.link_doctype }} --</option>
        {% for link_doc in link_field_options|get_item:field.name %}
        <option value="{{ link_doc.id }}"
            {% if document.data|get_item:field.name == link_doc.name %}selected{% endif %}>
            {{ link_doc.name }}
        </option>
        {% endfor %}
    </select>
{% endif %}
```

## Admin Interface

### DocumentLinkAdmin
**File**: `doctypes/admin.py:307`

View and manage all document links:
- List display: source → field → target
- Filter by field name, doctype, date
- Search by document names
- Raw ID fields for performance
- View at: http://localhost:8000/admin/doctypes/documentlink/

### DocumentLinkMultipleAdmin
**File**: `doctypes/admin.py:327`

View and manage many-to-many links:
- List display with order
- Editable order in list view
- Filter and search capabilities
- View at: http://localhost:8000/admin/doctypes/documentlinkmultiple/

## Benefits of This Implementation

### 1. **Referential Integrity**
- Can't delete a document that's being referenced (PROTECT)
- Orphaned links are automatically cleaned up (CASCADE)
- Database enforces constraints

### 2. **Efficient Queries**
```python
# Old way (JSON search - slow)
orders = Document.objects.filter(data__contains={'customer': 'John'})

# New way (indexed foreign key - fast)
customer = Document.objects.get(name='John')
orders = [link.source_document for link in customer.incoming_links.all()]
```

### 3. **Reverse Lookups**
```python
# Find all orders for a customer
customer = Document.objects.get(name='John Doe')
orders = customer.get_referencing_documents()

# Find customer for an order
order = Document.objects.get(id=1)
customer = order.get_link('customer')
```

### 4. **Type Safety**
- Validates that target document is of correct doctype
- Validates that field exists and is a link type
- Prevents invalid links at database level

### 5. **Audit Trail**
- Tracks who created each link
- Tracks when links were created
- Can query link history

## Usage Example: Creating a Sales Order with Customer Link

### Step 1: Create Doctypes

```python
# Create Customer doctype
customer_doctype = Doctype.objects.create(
    name='Customer',
    schema={'fields': [
        {'name': 'customer_name', 'type': 'string', 'required': True},
        {'name': 'email', 'type': 'email'},
    ]}
)

# Create Sales Order doctype with link to Customer
order_doctype = Doctype.objects.create(
    name='Sales Order',
    schema={'fields': [
        {'name': 'order_number', 'type': 'string', 'required': True},
        {'name': 'customer', 'type': 'link', 'link_doctype': 'Customer', 'required': True},
        {'name': 'total', 'type': 'decimal'},
    ]}
)
```

### Step 2: Create Documents

```python
# Create customer
customer = Document.objects.create(
    doctype=customer_doctype,
    name='CUST-001',
    data={'customer_name': 'John Doe', 'email': 'john@example.com'},
    created_by=user
)

# Create order linked to customer
order = Document.objects.create(
    doctype=order_doctype,
    name='ORD-001',
    data={'order_number': 'ORD-001', 'customer': 'CUST-001', 'total': '1500.00'},
    created_by=user
)

# Create the link relationship
DocumentLink.objects.create(
    source_document=order,
    target_document=customer,
    field_name='customer',
    created_by=user
)
```

### Step 3: Query Relationships

```python
# Get customer for an order
order = Document.objects.get(name='ORD-001')
customer = order.get_link('customer')
print(f"Customer: {customer.data['customer_name']}")  # "John Doe"

# Get all orders for a customer
customer = Document.objects.get(name='CUST-001')
orders = customer.get_referencing_documents()
print(f"Orders: {len(orders)}")  # Shows count of orders

# Try to delete customer (will fail if orders exist)
try:
    customer.delete()  # Raises ProtectedError
except ProtectedError:
    print("Cannot delete customer with existing orders")
```

## Testing

### Test Link Field Creation
1. Go to admin: http://localhost:8000/admin/doctypes/doctype/
2. Create "Customer" doctype with basic fields
3. Create "Order" doctype with link field to Customer
4. Create some customer documents
5. Create order document - link field should show customers dropdown
6. Save order
7. Check DocumentLink admin - should see the link created

### Test Referential Integrity
1. Create customer with orders
2. Try to delete customer from admin
3. Should see error: "Cannot delete customer with existing orders"
4. Delete orders first
5. Then customer can be deleted

### Test Reverse Lookup
```python
python manage.py shell

from doctypes.models import Document
customer = Document.objects.get(name='CUST-001')
orders = customer.get_referencing_documents()
print([o.name for o in orders])
```

## Migrations Applied

**File**: `doctypes/migrations/0004_documentlink_documentlinkmultiple.py`

Creates:
- DocumentLink table
- DocumentLinkMultiple table
- Indexes for fast lookups
- Foreign key constraints

## API Integration (Future)

The serializers can be extended to include link data:

```python
class DocumentSerializer(serializers.ModelSerializer):
    links = serializers.SerializerMethodField()

    def get_links(self, obj):
        return {
            link.field_name: {
                'id': link.target_document.id,
                'name': link.target_document.name,
                'doctype': link.target_document.doctype.name
            }
            for link in obj.outgoing_links.all()
        }
```

## Performance Considerations

### Indexes Created
- `(source_document, field_name)` - Fast lookup of links from a document
- `(target_document)` - Fast reverse lookup (find all documents linking here)

### Query Optimization
```python
# Prefetch related links to avoid N+1 queries
documents = Document.objects.prefetch_related('outgoing_links__target_document')

for doc in documents:
    customer = doc.get_link('customer')  # No additional query
```

## Summary

[YES] **Proper database relationships implemented for Link fields**

**Relationship Types**:
- Many-to-One: DocumentLink model
- One-to-Many: parent_document field (existing)
- Many-to-Many: DocumentLinkMultiple model

**Features**:
- Referential integrity with PROTECT/CASCADE
- Automatic JSON sync
- Helper methods on Document model
- Admin interface for managing links
- Form integration with dropdowns
- Validation and type safety

**Status**: Ready for testing
**Next**: Create example doctypes with links and test end-to-end

---

Generated: 2025-12-03
Status: Complete [YES]
