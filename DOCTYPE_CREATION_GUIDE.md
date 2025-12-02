# Doctype Creation Guide

## The Issue (Fixed)
Previously, creating a doctype would fail because the schema field wasn't being initialized properly with an empty `{"fields": []}` structure.

## What Was Fixed
1. **Admin Form**: Auto-initializes schema field when loading the add page
2. **JavaScript**: Ensures schema field is populated on page load
3. **Model**: Auto-initializes schema before validation if missing

## How to Create a Doctype Now

### Option 1: Minimal Doctype (Quickest)
1. Go to: http://127.0.0.1:8000/admin/doctypes/doctype/add/
2. Enter just the **Name** (e.g., "Item")
3. Click **Save**
4. Done! The schema will auto-initialize with empty fields

### Option 2: Using the Field Builder
1. Go to: http://127.0.0.1:8000/admin/doctypes/doctype/add/
2. Enter the **Name** (e.g., "Customer")
3. Scroll down to the **Field Builder** section
4. Click **"+ Add Field"**
5. Fill in:
   - Field Name: `customer_name` (lowercase, underscores only)
   - Label: `Customer Name`
   - Type: `string`
   - Check "Required" if needed
6. Click **Save Field**
7. Add more fields as needed
8. Click **Save** at the bottom

### Option 3: Manual JSON Schema
1. Go to: http://127.0.0.1:8000/admin/doctypes/doctype/add/
2. Enter the **Name**
3. Expand the **"Schema (JSON)"** fieldset
4. Edit the schema directly, e.g.:
```json
{
  "fields": [
    {
      "name": "title",
      "label": "Title",
      "type": "string",
      "required": true
    }
  ]
}
```
5. Click **Save**

## Testing

The server is running at: **http://127.0.0.1:8000**

Admin credentials (from done_so_fat.txt):
- Username: `spoofman`
- Password: `admin123!`

## Verification Commands

```bash
# Check if server is running
lsof -ti:8000

# Test creating doctype programmatically
python manage.py shell -c "
from django.contrib.auth import get_user_model
from doctypes.models import Doctype
user = get_user_model().objects.first()
doctype = Doctype.objects.create(name='Test', created_by=user)
print(f'Created: {doctype.name} with schema: {doctype.schema}')
"

# View all doctypes
python manage.py shell -c "
from doctypes.models import Doctype
for dt in Doctype.objects.all():
    print(f'{dt.name}: {len(dt.schema.get(\"fields\", []))} fields')
"
```

## Next Steps

Now you can:
1. Create doctypes with dynamic schemas
2. Add/edit/remove fields using the visual builder
3. Create documents based on your doctypes
4. Access the API at: http://127.0.0.1:8000/api/core/
