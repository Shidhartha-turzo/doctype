# Field Management API Guide

## Overview

You can manage doctype fields both via the **Visual Field Builder** (UI) and **REST API** (programmatic). This guide shows you how to use the API to add, update, and remove fields.

## Current Approach: Update Entire Schema

Currently, you update fields by patching the entire schema:

### Get Current Schema

```bash
# Get auth token
TOKEN=$(curl -X POST http://localhost:8000/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "spoofman", "password": "admin123"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Get current doctype schema
curl http://localhost:8000/api/core/doctypes/1/ \
  -H "Authorization: Bearer $TOKEN" \
  | python -m json.tool
```

### Add a Field via API

```bash
# Update schema with new field
curl -X PATCH http://localhost:8000/api/core/doctypes/1/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "schema": {
      "fields": [
        {
          "name": "sku",
          "label": "SKU",
          "type": "string",
          "required": true,
          "unique": true
        },
        {
          "name": "title",
          "label": "Title",
          "type": "string",
          "required": true
        },
        {
          "name": "unit_price",
          "label": "Unit Price",
          "type": "decimal",
          "default": "0.00"
        },
        {
          "name": "description",
          "label": "Description",
          "type": "text"
        }
      ]
    }
  }'
```

## Better Approach: Helper Script

Here's a Python script to make field management easier:

### field_manager.py

```python
import requests
import json

BASE_URL = "http://localhost:8000"

class DoctypeFieldManager:
    def __init__(self, username, password):
        self.base_url = BASE_URL
        self.token = self.login(username, password)

    def login(self, username, password):
        """Get authentication token"""
        response = requests.post(
            f"{self.base_url}/auth/login/",
            json={"username": username, "password": password}
        )
        return response.json()['access_token']

    def get_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_doctype(self, doctype_id):
        """Get doctype details"""
        response = requests.get(
            f"{self.base_url}/api/core/doctypes/{doctype_id}/",
            headers=self.get_headers()
        )
        return response.json()

    def get_fields(self, doctype_id):
        """Get current fields"""
        doctype = self.get_doctype(doctype_id)
        return doctype.get('schema', {}).get('fields', [])

    def add_field(self, doctype_id, field_data):
        """Add a new field"""
        fields = self.get_fields(doctype_id)
        fields.append(field_data)
        return self.update_fields(doctype_id, fields)

    def update_field(self, doctype_id, field_name, field_data):
        """Update existing field"""
        fields = self.get_fields(doctype_id)
        for i, field in enumerate(fields):
            if field['name'] == field_name:
                fields[i] = field_data
                break
        return self.update_fields(doctype_id, fields)

    def remove_field(self, doctype_id, field_name):
        """Remove a field"""
        fields = self.get_fields(doctype_id)
        fields = [f for f in fields if f['name'] != field_name]
        return self.update_fields(doctype_id, fields)

    def update_fields(self, doctype_id, fields):
        """Update all fields"""
        response = requests.patch(
            f"{self.base_url}/api/core/doctypes/{doctype_id}/",
            headers=self.get_headers(),
            json={"schema": {"fields": fields}}
        )
        return response.json()

    def list_fields(self, doctype_id):
        """List all fields"""
        fields = self.get_fields(doctype_id)
        for field in fields:
            print(f"- {field['name']} ({field['type']}) - {field.get('label', '')}")
        return fields


# Usage Examples
if __name__ == "__main__":
    manager = DoctypeFieldManager("spoofman", "admin123")

    # Get doctype ID (or use 1 for inventory-item)
    doctype_id = 1

    # List current fields
    print("Current fields:")
    manager.list_fields(doctype_id)

    # Add a new field
    print("\nAdding 'description' field...")
    manager.add_field(doctype_id, {
        "name": "description",
        "label": "Description",
        "type": "text"
    })

    # Add another field with more options
    print("\nAdding 'category' field...")
    manager.add_field(doctype_id, {
        "name": "category",
        "label": "Category",
        "type": "select",
        "options": ["Electronics", "Clothing", "Food", "Books"],
        "required": True
    })

    # Update a field
    print("\nUpdating 'category' field...")
    manager.update_field(doctype_id, "category", {
        "name": "category",
        "label": "Product Category",
        "type": "select",
        "options": ["Electronics", "Clothing", "Food", "Books", "Other"],
        "required": True,
        "default": "Other"
    })

    # List updated fields
    print("\nUpdated fields:")
    manager.list_fields(doctype_id)

    # Remove a field
    # print("\nRemoving 'description' field...")
    # manager.remove_field(doctype_id, "description")
```

### Usage:

```bash
# Save the script
cat > field_manager.py << 'EOF'
[paste the script above]
EOF

# Run it
python field_manager.py
```

## Examples

### Add a String Field

```python
manager.add_field(1, {
    "name": "product_code",
    "label": "Product Code",
    "type": "string",
    "required": True,
    "unique": True
})
```

### Add a Decimal Field

```python
manager.add_field(1, {
    "name": "price",
    "label": "Price",
    "type": "decimal",
    "required": True,
    "default": "0.00"
})
```

### Add a Select Field

```python
manager.add_field(1, {
    "name": "status",
    "label": "Status",
    "type": "select",
    "options": ["Active", "Inactive", "Discontinued"],
    "default": "Active"
})
```

### Add a Link Field

```python
manager.add_field(1, {
    "name": "supplier",
    "label": "Supplier",
    "type": "link",
    "link_doctype": "Supplier"
})
```

### Add a Boolean Field

```python
manager.add_field(1, {
    "name": "is_active",
    "label": "Active",
    "type": "boolean",
    "default": True
})
```

### Add a Date Field

```python
manager.add_field(1, {
    "name": "expiry_date",
    "label": "Expiry Date",
    "type": "date"
})
```

### Add a Computed Field

```python
manager.add_field(1, {
    "name": "total_value",
    "label": "Total Value",
    "type": "computed",
    "formula": "quantity * unit_price"
})
```

## Direct cURL Examples

### Add Description Field

```bash
# Get current fields first
FIELDS=$(curl -s http://localhost:8000/api/core/doctypes/1/ \
  -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys, json; d=json.load(sys.stdin); print(json.dumps(d['schema']['fields']))")

# Add new field to the array
# (You'll need to manually edit the JSON)

curl -X PATCH http://localhost:8000/api/core/doctypes/1/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "schema": {
      "fields": [
        {"name": "sku", "label": "SKU", "type": "string", "required": true, "unique": true},
        {"name": "title", "label": "Title", "type": "string", "required": true},
        {"name": "unit_price", "label": "Unit Price", "type": "decimal", "default": "0.00"},
        {"name": "description", "label": "Description", "type": "text"}
      ]
    }
  }'
```

## Best Practices

### 1. Always Get Current Fields First

```python
# Good
current_fields = manager.get_fields(doctype_id)
current_fields.append(new_field)
manager.update_fields(doctype_id, current_fields)

# Bad - overwrites existing fields!
manager.update_fields(doctype_id, [new_field])
```

### 2. Validate Field Names

```python
def validate_field_name(name):
    import re
    if not re.match(r'^[a-z_]+$', name):
        raise ValueError("Field name must be lowercase with underscores only")
    return name

field_data = {
    "name": validate_field_name("product_name"),
    ...
}
```

### 3. Handle Errors

```python
try:
    manager.add_field(1, field_data)
    print("Field added successfully!")
except Exception as e:
    print(f"Error: {e}")
```

### 4. Backup Before Changes

```python
# Backup current schema
import json
fields_backup = manager.get_fields(doctype_id)
with open('schema_backup.json', 'w') as f:
    json.dump(fields_backup, f, indent=2)

# Make changes
try:
    manager.add_field(doctype_id, new_field)
except:
    # Restore on error
    manager.update_fields(doctype_id, fields_backup)
```

## Two Ways to Manage Fields

### Visual Field Builder (UI):
- **Pros**: Easy, visual, drag-and-drop, no coding
- **Cons**: Manual, one at a time
- **Use when**: Building/testing schemas, quick changes

### API (Programmatic):
- **Pros**: Automated, scriptable, bulk operations
- **Cons**: Requires coding
- **Use when**: Deploying to production, bulk changes, automation

## Summary

You have two options:

1. **Visual Field Builder**: Use the admin UI at `/admin/doctypes/doctype/inventory-item/change/`
2. **REST API**: Use the API with `PATCH /api/core/doctypes/{id}/` endpoint

Both update the same schema - choose based on your needs!
