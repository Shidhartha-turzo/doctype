# Visual Field Builder Guide

## Overview

The Visual Field Builder is an interactive, drag-and-drop interface for creating and managing doctype schemas without writing raw JSON. It provides a user-friendly way to define fields, configure properties, and organize your doctype structure.

## Accessing the Field Builder

### Slug-Based URLs

Doctypes can now be accessed using readable slug-based URLs instead of numeric IDs:

**Old Format** (still works):
```
http://127.0.0.1:8000/admin/doctypes/doctype/1/change/
```

**New Format** (recommended):
```
http://127.0.0.1:8000/admin/doctypes/doctype/inventory-item/change/
```

The slug is automatically generated from the doctype name:
- "Inventory Item" → `inventory-item`
- "Sales Order" → `sales-order`
- "Employee" → `employee`

### Location in Admin

1. Navigate to Django Admin: `http://127.0.0.1:8000/admin/`
2. Go to **Doctypes** → **Doctypes**
3. Click on any doctype or create a new one
4. Scroll down past the basic fields to find the **Field Builder** section

## Features

### 1. Visual Field List

All fields are displayed as cards showing:
- **Field Name & Label**: The internal name and display label
- **Field Type Badge**: Color-coded by type (string, integer, link, etc.)
- **Property Badges**: Shows if field is Required, Unique, or Read Only
- **Field Details**: Description, default value, options, linked doctype, etc.
- **Actions**: Edit and Delete buttons

### 2. Drag-and-Drop Reordering

**How to Reorder Fields**:
1. Hover over any field card
2. Click and hold the **⋮⋮** (move handle) button
3. Drag the field to the desired position
4. Drop it between other fields
5. The schema updates automatically

This allows you to control the order fields appear in forms and API responses.

### 3. Adding New Fields

**Step-by-Step**:
1. Click the **"+ Add Field"** button in the toolbar
2. A modal dialog opens with the field editor
3. Fill in the required fields:
   - **Field Name**: Internal name (lowercase, underscores only) - e.g., `customer_name`
   - **Label**: Display name shown to users - e.g., "Customer Name"
   - **Field Type**: Select from 20+ available types
4. Configure optional properties:
   - **Default Value**: Pre-populate the field
   - **Required**: Make the field mandatory
   - **Unique**: Enforce unique values across documents
   - **Read Only**: Prevent editing after creation
   - **Description**: Help text for users
5. Configure type-specific options (see below)
6. Click **"Save Field"**

### 4. Editing Existing Fields

**Step-by-Step**:
1. Find the field you want to edit in the field list
2. Click the **"Edit"** button on the field card
3. The modal opens with the current field configuration
4. Make your changes
5. Click **"Save Field"**

### 5. Deleting Fields

**Step-by-Step**:
1. Find the field you want to delete
2. Click the **"Delete"** button on the field card
3. Confirm the deletion in the alert dialog
4. The field is removed and schema updates automatically

**Warning**: Deleting a field doesn't remove data from existing documents. Consider the implications before deleting fields in production.

## Field Types and Options

### Basic Text Types

**String**: Single-line text
```
Field Name: customer_name
Type: String
Max Length: 255
```

**Text**: Multi-line text area
```
Field Name: description
Type: Text
```

**Email**: Email validation
```
Field Name: email
Type: Email
Validates: user@example.com format
```

**Phone**: Phone number
```
Field Name: phone
Type: Phone
```

**URL**: Web address
```
Field Name: website
Type: URL
Validates: http:// or https://
```

### Numeric Types

**Integer**: Whole numbers
```
Field Name: quantity
Type: Integer
```

**Decimal**: Numbers with decimals
```
Field Name: price
Type: Decimal
Precision: 10,2
```

**Currency**: Money values
```
Field Name: total_amount
Type: Currency
Auto-formatting: $1,234.56
```

**Percent**: Percentage values
```
Field Name: discount_rate
Type: Percent
Display: 15%
```

### Selection Types

**Select**: Single choice dropdown
```
Field Name: status
Type: Select
Options: Draft, Submitted, Approved, Rejected
```

**Type-Specific Configuration**:
- Enter options separated by commas: `Draft, Submitted, Approved`
- Options are stored as an array in JSON

**Multiselect**: Multiple choices
```
Field Name: tags
Type: Multiselect
Options: Urgent, Important, Review, Archive
```

### Boolean Type

**Boolean**: True/False checkbox
```
Field Name: is_active
Type: Boolean
Default: true
```

### Date/Time Types

**Date**: Date picker
```
Field Name: order_date
Type: Date
Format: YYYY-MM-DD
```

**Datetime**: Date and time picker
```
Field Name: created_at
Type: Datetime
Format: YYYY-MM-DD HH:MM:SS
```

**Duration**: Time duration
```
Field Name: estimated_time
Type: Duration
Format: HH:MM:SS
```

### Relational Types

**Link**: Reference to another doctype
```
Field Name: customer
Type: Link
Link to Doctype: Customer
```

**Type-Specific Configuration**:
- Enter the name of the doctype to link to
- Creates a foreign key relationship
- Enables cascading queries

**Table**: Child table (one-to-many)
```
Field Name: items
Type: Table
Child Doctype: Order Item
```

**Type-Specific Configuration**:
- Specify the child doctype name
- Child doctype must have `is_child = True`
- Creates a parent-child relationship

### Special Types

**Computed**: Calculated field
```
Field Name: total
Type: Computed
Formula: quantity * rate
```

**Type-Specific Configuration**:
- Enter a formula expression
- Supported operations: +, -, *, /, sum(), avg(), date_diff()
- Examples:
  - `quantity * rate`
  - `sum(items.amount)`
  - `date_diff(end_date, start_date)`

**File**: File upload
```
Field Name: attachment
Type: File
Allowed: PDF, DOCX, TXT
```

**Image**: Image upload
```
Field Name: photo
Type: Image
Allowed: PNG, JPG, GIF
```

**Color**: Color picker
```
Field Name: theme_color
Type: Color
Format: #RRGGBB
```

**Rating**: Star rating
```
Field Name: customer_rating
Type: Rating
Max: 5 stars
```

**JSON**: Structured data
```
Field Name: metadata
Type: JSON
Stores: Any valid JSON
```

## Field Properties

### Required Field
- Makes the field mandatory
- Users cannot save without providing a value
- API validates presence

### Unique Field
- Enforces unique values across all documents
- Prevents duplicates
- Useful for: email, phone, reference numbers

### Read Only Field
- Field can be set once but not edited
- Useful for: creation timestamps, system-generated IDs
- Can still be set via API initially

### Default Value
- Pre-populates the field when creating new documents
- Can be overridden by user
- Useful for: status fields, boolean flags

### Description / Help Text
- Shown to users as guidance
- Explains the field's purpose
- Best practices for data entry

## Import/Export Functionality

### Export JSON

**Use Case**: Backup your schema or share with others

**Steps**:
1. Click **"↑ Export JSON"** button in the toolbar
2. The schema is automatically copied to your clipboard
3. Paste it into a text editor or file

**Output Format**:
```json
{
  "fields": [
    {
      "name": "customer_name",
      "label": "Customer Name",
      "type": "string",
      "required": true
    },
    {
      "name": "status",
      "label": "Status",
      "type": "select",
      "options": ["Draft", "Submitted", "Approved"]
    }
  ]
}
```

### Import JSON

**Use Case**: Load a pre-defined schema or restore from backup

**Steps**:
1. Click **"↓ Import JSON"** button in the toolbar
2. A prompt appears asking for JSON input
3. Paste your JSON schema
4. Click OK
5. Fields are loaded into the builder

**Supported Formats**:

**Full Schema**:
```json
{
  "fields": [...]
}
```

**Fields Array Only**:
```json
[
  {"name": "field1", "type": "string"},
  {"name": "field2", "type": "integer"}
]
```

## How Schema Updates Work

### Automatic Synchronization

The Visual Field Builder automatically syncs with the hidden JSON schema field:

1. **When you add/edit/delete a field**: The JSON is updated immediately
2. **When you drag-and-drop**: The field order in JSON changes
3. **When you save the doctype**: The complete schema is saved to the database

### Hidden Schema Field

The raw JSON schema field is still present but hidden by default:

- Located in the collapsed **"Schema (JSON)"** section
- Can be manually edited if needed (for advanced users)
- Click to expand and see the raw JSON
- Changes in the visual builder update this field

### Backward Compatibility

- Existing doctypes load their fields into the visual builder
- You can switch between visual and JSON editing
- Both methods update the same underlying schema

## Best Practices

### 1. Field Naming Convention

**Do**:
- Use lowercase letters
- Use underscores for spaces: `customer_name`
- Be descriptive: `billing_address` not `addr1`
- Keep it consistent: `created_at`, `updated_at`

**Don't**:
- Use spaces: `customer name` ❌
- Use special characters: `customer-name` ❌
- Start with numbers: `1st_name` ❌
- Use Python keywords: `class`, `def`, `import` ❌

### 2. Field Organization

**Group Related Fields**:
1. Drag-and-drop to organize logically
2. Put most important fields first
3. Group related fields together (address fields, date fields)

**Example Order**:
```
1. name (title_field)
2. customer (link)
3. order_date (date)
4. status (select)
5. items (table)
6. total_amount (currency)
7. notes (text)
```

### 3. Required vs Optional

**Make Required**:
- Fields essential for the document to be valid
- Fields used in workflows or automations
- Fields needed for reports

**Make Optional**:
- Additional information
- Fields filled in later
- Nice-to-have data

### 4. Default Values

**Good Uses**:
- Status fields: `default: "Draft"`
- Boolean flags: `default: true`
- Current date: `default: "Today"`

**Avoid**:
- User-specific data (name, email)
- Calculated values (use computed fields)
- Large text blocks

### 5. Unique Constraints

**Apply to**:
- Email addresses
- Phone numbers
- Reference numbers
- Serial numbers

**Don't Apply to**:
- Names (people can have same name)
- Dates
- Status fields
- Calculated fields

## Troubleshooting

### Fields Not Showing

**Issue**: Fields added in builder don't appear after saving

**Solutions**:
1. Check browser console for JavaScript errors
2. Clear browser cache and reload
3. Verify static files are collected: `python manage.py collectstatic`
4. Check that the schema field is not empty

### Drag-and-Drop Not Working

**Issue**: Cannot reorder fields by dragging

**Solutions**:
1. Check browser compatibility (requires modern browser)
2. Ensure JavaScript is enabled
3. Try refreshing the page
4. Check for JavaScript errors in console

### Type-Specific Options Not Showing

**Issue**: Link doctype or options field not appearing

**Solutions**:
1. Select the correct field type first
2. Options appear based on selected type:
   - Link → shows "Link to Doctype"
   - Select → shows "Options"
   - Table → shows "Child Doctype"
   - Computed → shows "Formula"

### Schema Not Saving

**Issue**: Changes lost after saving doctype

**Solutions**:
1. Check Django admin logs for errors
2. Verify the schema field is not marked readonly
3. Check browser console for JavaScript errors
4. Try manually expanding and saving the JSON schema

### Import JSON Fails

**Issue**: Error when importing JSON

**Solutions**:
1. Validate JSON syntax (use jsonlint.com)
2. Ensure format matches expected structure
3. Check for missing required fields (name, type)
4. Remove invalid field types

## Examples

### Example 1: Customer Doctype

```json
{
  "fields": [
    {
      "name": "customer_name",
      "label": "Customer Name",
      "type": "string",
      "required": true
    },
    {
      "name": "email",
      "label": "Email Address",
      "type": "email",
      "required": true,
      "unique": true
    },
    {
      "name": "phone",
      "label": "Phone Number",
      "type": "phone"
    },
    {
      "name": "status",
      "label": "Status",
      "type": "select",
      "options": ["Active", "Inactive", "Suspended"],
      "default": "Active"
    }
  ]
}
```

### Example 2: Sales Order Doctype

```json
{
  "fields": [
    {
      "name": "order_number",
      "label": "Order #",
      "type": "string",
      "readonly": true,
      "unique": true
    },
    {
      "name": "customer",
      "label": "Customer",
      "type": "link",
      "link_doctype": "Customer",
      "required": true
    },
    {
      "name": "order_date",
      "label": "Order Date",
      "type": "date",
      "default": "Today",
      "required": true
    },
    {
      "name": "items",
      "label": "Order Items",
      "type": "table",
      "child_doctype": "Sales Order Item"
    },
    {
      "name": "total_amount",
      "label": "Total Amount",
      "type": "computed",
      "formula": "sum(items.amount)"
    },
    {
      "name": "status",
      "label": "Status",
      "type": "select",
      "options": ["Draft", "Submitted", "Delivered", "Cancelled"],
      "default": "Draft"
    }
  ]
}
```

### Example 3: Employee Doctype

```json
{
  "fields": [
    {
      "name": "employee_id",
      "label": "Employee ID",
      "type": "string",
      "required": true,
      "unique": true
    },
    {
      "name": "full_name",
      "label": "Full Name",
      "type": "string",
      "required": true
    },
    {
      "name": "email",
      "label": "Work Email",
      "type": "email",
      "required": true,
      "unique": true
    },
    {
      "name": "department",
      "label": "Department",
      "type": "link",
      "link_doctype": "Department"
    },
    {
      "name": "hire_date",
      "label": "Date of Joining",
      "type": "date",
      "required": true
    },
    {
      "name": "is_active",
      "label": "Active",
      "type": "boolean",
      "default": true
    },
    {
      "name": "photo",
      "label": "Profile Photo",
      "type": "image"
    }
  ]
}
```

## Advanced Usage

### Combining with Custom Fields

You can still add custom fields at runtime via the API:

```bash
curl -X POST http://localhost:8000/api/core/custom-fields/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "doctype_id": 1,
    "fieldname": "priority",
    "fieldtype": "select",
    "options": ["High", "Medium", "Low"]
  }'
```

Custom fields appear alongside regular fields in the visual builder.

### Programmatic Schema Updates

You can still update schemas via the API:

```python
import requests

schema = {
    "fields": [
        {"name": "title", "type": "string", "required": True}
    ]
}

response = requests.patch(
    f"http://localhost:8000/api/core/doctypes/1/",
    json={"schema": schema},
    headers={"Authorization": f"Bearer {token}"}
)
```

### Bulk Import/Export

Export all doctypes' schemas:

```bash
python manage.py dumpdata doctypes.Doctype --indent 2 > doctypes_backup.json
```

Import schemas:

```bash
python manage.py loaddata doctypes_backup.json
```

## Future Enhancements

Planned features for the Visual Field Builder:

1. **Field Templates**: Pre-defined field sets (address, contact info)
2. **Validation Rules**: Visual builder for field validators
3. **Permission Designer**: Visual permission rule builder
4. **Workflow Designer**: Visual workflow state machine builder
5. **Field Dependencies**: Show/hide fields based on other fields
6. **Bulk Operations**: Select multiple fields to edit/delete
7. **Field Search**: Search and filter fields in large schemas
8. **Schema Versioning**: Track and rollback schema changes
9. **Field Statistics**: Show usage statistics for each field
10. **AI Suggestions**: Suggest fields based on doctype name

## Support

If you encounter issues with the Visual Field Builder:

1. Check browser console for errors (F12)
2. Verify static files are collected
3. Check Django logs for backend errors
4. Test with raw JSON editing as fallback
5. Report issues on GitHub

---

**Visual Field Builder** - Build powerful doctypes without writing JSON!
