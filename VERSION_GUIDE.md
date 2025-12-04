# Document Versioning Guide

Complete guide for document version management and history tracking.

## Table of Contents
1. [Overview](#overview)
2. [Features](#features)
3. [Automatic Version Creation](#automatic-version-creation)
4. [Version API](#version-api)
5. [UI Components](#ui-components)
6. [Restore Functionality](#restore-functionality)
7. [Diff Comparison](#diff-comparison)
8. [Best Practices](#best-practices)
9. [Examples](#examples)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The Document Versioning System automatically tracks all changes to documents, allowing you to:

- **View version history** - See all past versions of a document
- **Compare versions** - Identify what changed between versions
- **Restore versions** - Revert to previous document states
- **Track changes** - Know who changed what and when
- **Audit trail** - Complete history of document evolution

**Key Features:**
- Automatic version creation on every save
- Snapshot-based versioning (complete document copy)
- Diff calculation between versions
- Change annotation (added/modified/removed fields)
- Restore to any previous version
- User attribution and comments
- RESTful API for integration
- Interactive UI widget

---

## Features

### 1. Automatic Versioning

Every document save automatically creates a new version:
- New version number assigned sequentially
- Complete snapshot of document data
- Diff from previous version calculated
- User and timestamp recorded
- Optional comment support

### 2. Version History

View complete history:
- Version number
- Who made changes
- When changes occurred
- What changed (summary)
- Comments explaining changes
- Current version indicator

### 3. Version Comparison

Compare any two versions:
- Side-by-side comparison
- Added fields highlighted
- Modified fields with old/new values
- Removed fields shown
- Unified diff format available

### 4. Version Restoration

Restore to any previous version:
- Creates new version with restored data
- Doesn't delete history
- Comment required for audit trail
- User attribution maintained

### 5. Change Tracking

Track specific changes:
- Field additions
- Field modifications (old → new)
- Field removals
- Nested object changes
- Array changes

---

## Automatic Version Creation

### How It Works

Versions are created automatically via Django signals:

```python
# In signals.py
@receiver(post_save, sender=Document)
def document_post_save(sender, instance, created, **kwargs):
    # After document is saved, create version
    create_version(
        instance,
        user=getattr(instance, '_current_user', None),
        comment=getattr(instance, '_version_comment', '')
    )
```

### Attaching User Context

To attribute versions to users:

```python
from doctypes.signals import set_document_user

# In your view
document = Document.objects.get(pk=document_id)
set_document_user(document, request.user)
document.data = {'field': 'new_value'}
document.save()  # Version will be attributed to request.user
```

### Adding Version Comments

To add comments to versions:

```python
# Set comment before saving
document._version_comment = "Updated pricing structure"
document.save()
```

### Skipping Version Creation

To skip automatic version creation:

```python
# Temporarily disable versioning
document._skip_version_creation = True
document.save()  # No version created
```

---

## Version API

### 1. List Versions

Get all versions of a document:

**Endpoint:** `GET /api/doctypes/documents/{document_id}/versions/`

**Query Parameters:**
- `limit` (optional) - Maximum number of versions to return

**Response:**
```json
{
    "success": true,
    "versions": [
        {
            "version_number": 3,
            "changed_by": "user@example.com",
            "changed_at": "2025-12-03T10:30:00Z",
            "comment": "Updated pricing",
            "changes_summary": "2 fields modified",
            "is_current": true
        },
        {
            "version_number": 2,
            "changed_by": "user@example.com",
            "changed_at": "2025-12-03T10:00:00Z",
            "comment": "Added customer info",
            "changes_summary": "3 fields added",
            "is_current": false
        },
        {
            "version_number": 1,
            "changed_by": "System",
            "changed_at": "2025-12-03T09:00:00Z",
            "comment": "",
            "changes_summary": "5 fields added",
            "is_current": false
        }
    ],
    "current_version": 3,
    "total_versions": 3
}
```

**Usage:**
```javascript
fetch('/api/doctypes/documents/123/versions/')
    .then(response => response.json())
    .then(data => {
        console.log('Versions:', data.versions);
    });
```

### 2. Get Specific Version

Get details of a specific version:

**Endpoint:** `GET /api/doctypes/documents/{document_id}/versions/{version_number}/`

**Response:**
```json
{
    "success": true,
    "version": {
        "version_number": 2,
        "data_snapshot": {
            "customer": "ACME Corp",
            "amount": 5000,
            "status": "draft"
        },
        "changes": {
            "added": {
                "customer": "ACME Corp"
            },
            "modified": {},
            "removed": {}
        },
        "changed_by": "user@example.com",
        "changed_at": "2025-12-03T10:00:00Z",
        "comment": "Added customer info"
    }
}
```

### 3. Compare Versions

Compare two versions:

**Endpoint:** `GET /api/doctypes/documents/{document_id}/versions/compare/`

**Query Parameters:**
- `v1` (required) - First version number
- `v2` (required) - Second version number
- `field` (optional) - Compare specific field only
- `format` (optional) - `json` (default) or `text` for unified diff

**Response (format=json):**
```json
{
    "success": true,
    "comparison": {
        "version1": {
            "number": 1,
            "changed_by": "System",
            "changed_at": "2025-12-03T09:00:00Z",
            "comment": ""
        },
        "version2": {
            "number": 2,
            "changed_by": "user@example.com",
            "changed_at": "2025-12-03T10:00:00Z",
            "comment": "Added customer info"
        },
        "diff": {
            "added": {
                "customer": "ACME Corp"
            },
            "modified": {
                "amount": {
                    "old": 1000,
                    "new": 5000
                }
            },
            "removed": {}
        },
        "has_changes": true
    }
}
```

**Response (format=text):**
```json
{
    "success": true,
    "diff_text": "--- Version 1\n+++ Version 2\n@@ -1,5 +1,6 @@\n {\n   \"amount\": 5000,\n+  \"customer\": \"ACME Corp\",\n   \"status\": \"draft\"\n }"
}
```

### 4. Restore Version

Restore document to a previous version:

**Endpoint:** `POST /api/doctypes/documents/{document_id}/versions/{version_number}/restore/`

**Request Body:**
```json
{
    "comment": "Restored to working version"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Document restored to version 2",
    "new_version": {
        "version_number": 4,
        "comment": "Restored to working version",
        "changed_by": "user@example.com",
        "changed_at": "2025-12-03T11:00:00Z"
    },
    "document": {
        "id": 123,
        "current_version": 4,
        "data": {
            "customer": "ACME Corp",
            "amount": 5000,
            "status": "draft"
        }
    }
}
```

### 5. Get Version History

Get formatted version history:

**Endpoint:** `GET /api/doctypes/documents/{document_id}/versions/history/`

**Response:**
```json
{
    "success": true,
    "history": [
        {
            "version_number": 3,
            "changed_by": "user@example.com",
            "changed_at": "2025-12-03T10:30:00Z",
            "comment": "Updated pricing",
            "changes_summary": "2 fields modified",
            "is_current": true
        },
        ...
    ],
    "document": {
        "id": 123,
        "doctype": "Sales Order",
        "current_version": 3
    }
}
```

---

## UI Components

### Version History Widget

The version history widget is automatically displayed on document edit pages.

**Features:**
- Version history table
- Current version badge
- Change summary badges (+2 ~3 -1)
- View version button
- Restore version button
- Compare versions tool

**Location:**
Document edit page → Below form → "Version History" card

### Using the Widget

**1. View Version History**
- Opens automatically when editing a document
- Shows all versions in reverse chronological order
- Current version highlighted

**2. View Specific Version**
- Click the eye icon () next to any version
- Modal shows:
  - Version metadata (who, when, comment)
  - Complete document snapshot
  - Changes made in that version

**3. Compare Versions**
- Click "Compare Versions" button
- Select two versions from dropdowns
- View:
  - Added fields (green)
  - Modified fields (yellow, old → new)
  - Removed fields (red)
  - Unified diff (optional)

**4. Restore Version**
- Click restore icon (↶) next to any version
- Add optional comment
- Confirm restoration
- Page reloads with restored data

---

## Restore Functionality

### How Restoration Works

Restoration creates a **new version** with the old data:

1. User clicks restore on version 2
2. System copies data from version 2
3. Document is updated with old data
4. New version (4) is created
5. Version history preserved

**Example Timeline:**
```
v1 → v2 → v3 (current)
           ↓ (restore v2)
v1 → v2 → v3 → v4 (current, data from v2)
```

### Why Not Delete History?

Versions are **never deleted** because:
- Complete audit trail maintained
- Can track why restoration occurred
- Can restore to pre-restoration state
- Compliance and regulatory requirements

### Restoration API

```javascript
// Restore to version 2
fetch('/api/doctypes/documents/123/versions/2/restore/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        comment: 'Reverted to stable version before bug'
    })
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        console.log('Restored to version', data.new_version.version_number);
        // Reload page or update UI
    }
});
```

### Python API

```python
from doctypes.version_engine import restore_version

# Restore document to version 2
new_version = restore_version(
    document=document,
    version_number=2,
    user=request.user,
    comment='Reverted to stable version'
)

print(f"Created version {new_version.version_number}")
```

---

## Diff Comparison

### Change Types

**Added Fields:**
Fields that exist in version 2 but not version 1:
```json
"added": {
    "customer": "ACME Corp",
    "email": "contact@acme.com"
}
```

**Modified Fields:**
Fields that changed between versions:
```json
"modified": {
    "amount": {
        "old": 1000,
        "new": 5000
    },
    "status": {
        "old": "draft",
        "new": "submitted"
    }
}
```

**Removed Fields:**
Fields that existed in version 1 but not version 2:
```json
"removed": {
    "temp_field": "temporary value"
}
```

### Unified Diff Format

For text-based comparison:

```diff
--- Version 1
+++ Version 2
@@ -1,5 +1,6 @@
 {
-  "amount": 1000,
+  "amount": 5000,
+  "customer": "ACME Corp",
   "status": "draft"
 }
```

### Comparing Specific Fields

```javascript
// Compare only 'items' field between versions
fetch('/api/doctypes/documents/123/versions/compare/?v1=1&v2=2&field=items')
    .then(response => response.json())
    .then(data => {
        console.log('Field diff:', data.diff_text);
    });
```

---

## Best Practices

### 1. Add Meaningful Comments

**Good:**
```python
document._version_comment = "Updated pricing based on Q4 2025 rates"
document.save()
```

**Bad:**
```python
document._version_comment = "Updated"
document.save()
```

### 2. Attribute Changes to Users

Always set user context:
```python
from doctypes.signals import set_document_user

set_document_user(document, request.user)
document.save()  # Version attributed to user
```

### 3. Review Before Restoring

Always:
1. View the version you're restoring to
2. Compare with current version
3. Understand what will change
4. Add comment explaining restoration

### 4. Don't Skip Versioning Unnecessarily

Only skip versioning for:
- Automated background updates
- System maintenance operations
- Bulk operations where individual versions not needed

**Don't skip for:**
- User-initiated changes
- Important data updates
- Any change requiring audit trail

### 5. Regular Version Cleanup

Consider cleanup policy:
- Keep all versions from last 90 days
- Keep monthly snapshots for historical data
- Document cleanup policy clearly

### 6. Monitor Version Storage

Versions consume database space:
- Monitor `DocumentVersion` table size
- Plan for growth (snapshots = full document copies)
- Consider archiving old versions

### 7. Use Version History for Debugging

When investigating issues:
1. Check version history
2. Identify when problem started
3. Compare versions around that time
4. Restore to working version if needed

### 8. Document Important Changes

For significant changes, add detailed comments:
```python
document._version_comment = """
Major update:
- Migrated from old pricing model
- Updated all item rates
- Recalculated totals
- Verified with finance team
"""
document.save()
```

---

## Examples

### Example 1: Manual Version with Comment

```python
from doctypes.signals import set_document_user

def update_order_pricing(request, document_id):
    document = Document.objects.get(pk=document_id)

    # Set user context
    set_document_user(document, request.user)

    # Update data
    document.data['amount'] = 5000
    document.data['discount'] = 10

    # Add comment
    document._version_comment = "Updated pricing for bulk order discount"

    # Save (version automatically created)
    document.save()
```

### Example 2: Compare Last Two Versions

```python
from doctypes.version_engine import VersionEngine

engine = VersionEngine(document)
versions = engine.get_versions(limit=2)

if len(versions) >= 2:
    comparison = engine.compare_versions(
        versions[1].version_number,  # Older
        versions[0].version_number   # Newer
    )

    print("Changes:")
    print(f"Added: {comparison['diff']['added']}")
    print(f"Modified: {comparison['diff']['modified']}")
    print(f"Removed: {comparison['diff']['removed']}")
```

### Example 3: Restore to Last Known Good Version

```python
from doctypes.version_engine import restore_version

# Find last version with status='approved'
approved_version = DocumentVersion.objects.filter(
    document=document,
    data_snapshot__status='approved'
).order_by('-version_number').first()

if approved_version:
    new_version = restore_version(
        document=document,
        version_number=approved_version.version_number,
        user=request.user,
        comment="Restored to last approved version"
    )
    print(f"Restored to v{approved_version.version_number}, created v{new_version.version_number}")
```

### Example 4: View Version History

```python
from doctypes.version_engine import VersionEngine

engine = VersionEngine(document)
history = engine.get_version_history()

for version in history:
    current_marker = " (CURRENT)" if version['is_current'] else ""
    print(f"v{version['version_number']}{current_marker}")
    print(f"  By: {version['changed_by']}")
    print(f"  At: {version['changed_at']}")
    print(f"  Changes: {version['changes_summary']}")
    print(f"  Comment: {version['comment']}")
    print()
```

### Example 5: Batch Update Without Versions

```python
# For bulk operations, skip versioning
from doctypes.models import Document

documents = Document.objects.filter(doctype__slug='invoice')

for doc in documents:
    doc._skip_version_creation = True
    doc.data['updated_by_migration'] = True
    doc.save()

# Then create single version for audit
last_doc = documents.last()
last_doc._skip_version_creation = False
last_doc._version_comment = "Bulk migration applied to all invoices"
last_doc.save()
```

### Example 6: Get Diff as Text

```python
from doctypes.version_engine import VersionEngine

engine = VersionEngine(document)

# Get unified diff between versions
diff_text = engine.get_diff_text(
    version1_number=1,
    version2_number=3
)

print("Unified Diff:")
print(diff_text)

# Compare specific field only
items_diff = engine.get_diff_text(
    version1_number=1,
    version2_number=3,
    field_name='items'
)

print("Items Diff:")
print(items_diff)
```

---

## Troubleshooting

### Versions Not Being Created

**Check:**
1. Signals are imported in `apps.py`:
   ```python
   def ready(self):
       import doctypes.signals  # noqa
   ```

2. Document is being saved correctly:
   ```python
   document.save()  # Not document.save(update_fields=['data'])
   ```

3. Version creation not skipped:
   ```python
   # Check if _skip_version_creation is set
   if hasattr(document, '_skip_version_creation'):
       print("Version creation is skipped!")
   ```

### User Attribution Missing

**Fix:**
Always set user before save:
```python
from doctypes.signals import set_document_user

set_document_user(document, request.user)
document.save()
```

### Version History Not Loading in UI

**Check:**
1. Document has versions:
   ```python
   from doctypes.engine_models import DocumentVersion
   versions = DocumentVersion.objects.filter(document=document)
   print(f"Found {versions.count()} versions")
   ```

2. API endpoints are accessible:
   ```bash
   curl http://localhost:8000/api/doctypes/documents/123/versions/
   ```

3. JavaScript console for errors:
   - Open browser DevTools
   - Check Console tab for errors
   - Check Network tab for failed requests

### Restore Not Working

**Check:**
1. Version exists:
   ```python
   version = engine.get_version(2)
   if not version:
       print("Version 2 not found!")
   ```

2. API response:
   ```javascript
   fetch('/api/doctypes/documents/123/versions/2/restore/', {
       method: 'POST',
       body: JSON.stringify({})
   })
   .then(r => r.json())
   .then(d => console.log(d))
   ```

3. Check for errors in logs:
   ```bash
   tail -f logs/django.log | grep version
   ```

### Database Space Issues

**Monitor:**
```python
from doctypes.engine_models import DocumentVersion
from django.db.models import Count, Sum
import json

# Count versions per document
stats = DocumentVersion.objects.values('document').annotate(
    version_count=Count('id')
).order_by('-version_count')

print("Documents with most versions:")
for stat in stats[:10]:
    print(f"Document {stat['document']}: {stat['version_count']} versions")

# Estimate storage size (rough)
versions = DocumentVersion.objects.all()
total_size = sum(len(json.dumps(v.data_snapshot)) for v in versions)
print(f"Estimated storage: {total_size / 1024 / 1024:.2f} MB")
```

**Cleanup Old Versions:**
```python
from datetime import datetime, timedelta
from doctypes.engine_models import DocumentVersion

# Delete versions older than 1 year (except first and last)
cutoff_date = datetime.now() - timedelta(days=365)

for document in Document.objects.all():
    old_versions = DocumentVersion.objects.filter(
        document=document,
        changed_at__lt=cutoff_date
    ).exclude(
        version_number=1  # Keep first version
    ).exclude(
        version_number=document.version_number  # Keep current
    )

    count = old_versions.count()
    old_versions.delete()
    print(f"Deleted {count} old versions for document {document.id}")
```

---

## Summary

**Document Versioning Features:**
- [YES] Automatic version creation on save
- [YES] Complete document snapshots
- [YES] Diff calculation (added/modified/removed)
- [YES] Version comparison (JSON and unified diff)
- [YES] Restore to any version
- [YES] User attribution and comments
- [YES] RESTful API
- [YES] Interactive UI widget
- [YES] Change tracking
- [YES] Audit trail

**API Endpoints:**
- GET /api/doctypes/documents/{id}/versions/
- GET /api/doctypes/documents/{id}/versions/{version}/
- GET /api/doctypes/documents/{id}/versions/compare/
- POST /api/doctypes/documents/{id}/versions/{version}/restore/
- GET /api/doctypes/documents/{id}/versions/history/

**UI Features:**
- Version history table
- View version modal
- Compare versions modal
- Restore version modal
- Change badges (+/~/-)
- Unified diff viewer
- Current version indicator

**Use Cases:**
- Track document changes
- Compare versions
- Restore previous states
- Audit trail
- Change debugging
- Compliance requirements
- Collaborative editing

For more information, see the Django Admin or contact your system administrator.

---

**Last Updated:** 2025-12-04
**Version:** 1.0
