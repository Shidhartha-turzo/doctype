# Child Table Guide

## Concept

Child tables allow you to have **nested data** within a document. Think of it like:
- **Parent**: Sales Order
  - **Child Table**: Order Items (multiple rows)
    - Item Name
    - Quantity
    - Price
    - Total

## How Child Tables Work

### 1. Create the Child Doctype First

The child doctype defines the structure of each row in the table.

**Example: Sales Order Item (Child)**
- Name: `Sales Order Item`
- **is_child**: ✓ Checked (Important!)
- Fields:
  - `item_name` (string) - Name of the product
  - `quantity` (integer) - How many
  - `rate` (decimal) - Price per unit
  - `amount` (decimal) - Total (quantity × rate)

### 2. Create the Parent Doctype

The parent doctype has a field of type "table" that references the child.

**Example: Sales Order (Parent)**
- Name: `Sales Order`
- **is_child**: ✗ Not checked
- Fields:
  - `customer_name` (string) - Who's ordering
  - `order_date` (date) - When
  - `items` (table) - **child_doctype: Sales Order Item**
  - `total_amount` (decimal) - Sum of all items

### 3. Document Structure (JSON)

When you create a Sales Order document, the data looks like this:

```json
{
  "customer_name": "John Doe",
  "order_date": "2025-12-03",
  "items": [
    {
      "item_name": "Laptop",
      "quantity": 2,
      "rate": 999.99,
      "amount": 1999.98
    },
    {
      "item_name": "Mouse",
      "quantity": 5,
      "rate": 25.00,
      "amount": 125.00
    }
  ],
  "total_amount": 2124.98
}
```

## Real-World Examples

### Example 1: Invoice with Line Items
- **Parent**: Invoice
- **Child**: Invoice Item
  - Product/Service
  - Quantity
  - Unit Price
  - Discount
  - Tax
  - Line Total

### Example 2: Employee with Qualifications
- **Parent**: Employee
- **Child**: Employee Qualification
  - Degree
  - University
  - Year
  - Grade

### Example 3: Project with Tasks
- **Parent**: Project
- **Child**: Project Task
  - Task Name
  - Assigned To
  - Start Date
  - End Date
  - Status

### Example 4: Recipe with Ingredients
- **Parent**: Recipe
- **Child**: Recipe Ingredient
  - Ingredient Name
  - Quantity
  - Unit (cups, grams, etc.)

## Step-by-Step Tutorial

Let's create a **Sales Order** system together.

### Step 1: Create Child Doctype
1. Go to Admin → Doctypes → Add Doctype
2. Fill in:
   - **Name**: `Sales Order Item`
   - **is_child**: ✓ Check this box
3. Add Fields:
   - Field 1:
     - Name: `item_name`
     - Label: `Item Name`
     - Type: `string`
     - Required: ✓
   - Field 2:
     - Name: `quantity`
     - Label: `Quantity`
     - Type: `integer`
     - Required: ✓
   - Field 3:
     - Name: `rate`
     - Label: `Rate`
     - Type: `decimal`
     - Required: ✓
   - Field 4:
     - Name: `amount`
     - Label: `Amount`
     - Type: `decimal`
     - Read Only: ✓
4. Save

### Step 2: Create Parent Doctype
1. Go to Admin → Doctypes → Add Doctype
2. Fill in:
   - **Name**: `Sales Order`
   - **is_child**: ✗ Leave unchecked
3. Add Fields:
   - Field 1:
     - Name: `customer_name`
     - Label: `Customer Name`
     - Type: `string`
     - Required: ✓
   - Field 2:
     - Name: `order_date`
     - Label: `Order Date`
     - Type: `date`
     - Required: ✓
   - Field 3:
     - Name: `items`
     - Label: `Items`
     - Type: `table`
     - **Child Doctype**: `Sales Order Item` (Important!)
   - Field 4:
     - Name: `total_amount`
     - Label: `Total Amount`
     - Type: `decimal`
4. Save

### Step 3: Create a Document

Now when you create a Sales Order document, the `items` field will contain an array of Sales Order Item objects.

**Via API:**
```bash
curl -X POST http://127.0.0.1:8000/api/core/sales-order/records/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "John Doe",
    "order_date": "2025-12-03",
    "items": [
      {
        "item_name": "Laptop",
        "quantity": 2,
        "rate": 999.99,
        "amount": 1999.98
      },
      {
        "item_name": "Mouse",
        "quantity": 5,
        "rate": 25.00,
        "amount": 125.00
      }
    ],
    "total_amount": 2124.98
  }'
```

## Current Limitations & Future Improvements

### What Works Now:
✓ Creating child doctypes with `is_child=True`
✓ Creating table fields that reference child doctypes
✓ Storing child table data as JSON arrays in documents
✓ Validating field types in child tables

### What Needs Improvement:
- [ ] Visual UI for adding/editing child table rows in admin
- [ ] Computed fields (auto-calculate totals)
- [ ] Drag-and-drop reordering of rows
- [ ] Inline editing of child rows
- [ ] Validation of child table data
- [ ] Better display of child tables in document list

## Next Steps

Would you like me to:
1. Create a working Sales Order example with child tables?
2. Build a better UI for editing child table rows?
3. Add computed field support (auto-calculate amounts)?
4. Add validation for child table data?

Let me know what you'd like to focus on!
