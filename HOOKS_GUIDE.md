# Hook System Guide

Complete guide for using hooks to extend document lifecycle behavior.

## Table of Contents
1. [Overview](#overview)
2. [Hook Types](#hook-types)
3. [Action Types](#action-types)
4. [Creating Hooks](#creating-hooks)
5. [Python Hooks](#python-hooks)
6. [Webhook Hooks](#webhook-hooks)
7. [Email Hooks](#email-hooks)
8. [Conditional Hooks](#conditional-hooks)
9. [Error Handling](#error-handling)
10. [Best Practices](#best-practices)
11. [Examples](#examples)

---

## Overview

The Hook System allows you to execute custom logic at various points in the document lifecycle. Hooks can:

- **Execute Python code** - Run custom business logic
- **Call webhooks** - Integrate with external systems
- **Send emails** - Notify users of events
- **Validate data** - Prevent invalid operations
- **Transform data** - Modify document fields automatically

**Key Features:**
- Automatic execution via Django signals
- Support for multiple hook types (before/after operations)
- Conditional execution
- Error handling and logging
- Audit trail of hook failures

---

## Hook Types

Hooks are triggered at specific points in the document lifecycle:

### Document Creation

**before_insert**
- Runs before new document is saved to database
- Can modify document data
- Can prevent insert by raising exception
- Use for: Validation, auto-numbering, defaults

**after_insert**
- Runs after new document is saved
- Cannot prevent insert
- Use for: Notifications, creating related documents, webhooks

### Document Updates

**before_save**
- Runs before existing document is saved
- Can modify document data
- Can prevent save by raising exception
- Use for: Validation, data transformation, permission checks

**after_save**
- Runs after existing document is saved
- Cannot prevent save
- Use for: Notifications, audit logging, webhooks

**on_change**
- Runs after save if document data changed
- Has access to old and new data
- Use for: Change notifications, cascading updates

### Document Deletion

**before_delete**
- Runs before document is deleted
- Can prevent deletion by raising exception
- Use for: Permission checks, dependency validation

**after_delete**
- Runs after document is deleted
- Cannot prevent deletion
- Use for: Cleanup, notifications, archiving

### Special Events

**before_submit** (planned)
- Before document status changes to Submitted

**after_submit** (planned)
- After document status changes to Submitted

---

## Action Types

Hooks can perform different types of actions:

### 1. Python Code
Execute custom Python code with access to document data.

### 2. Webhook
Send HTTP POST request to external URL.

### 3. Email
Send email to specified recipients.

### 4. Notification
Create in-app notification (placeholder).

---

## Creating Hooks

### Via Django Admin

1. Go to **Doctypes** → **Doctype Hooks**
2. Click **Add Doctype Hook**
3. Fill in:
   - **Doctype**: Select the doctype
   - **Hook Type**: When to trigger (before_save, after_insert, etc.)
   - **Action Type**: What to do (python, webhook, email)
   - **Order**: Execution order (lower runs first)
   - **Is Active**: Enable/disable hook
   - **Condition**: Optional Python expression

4. Configure action-specific fields:
   - **Python Code**: For python actions
   - **Webhook URL/Headers**: For webhook actions
   - **Email Template/Recipients**: For email actions

5. Save

---

## Python Hooks

### Available Context

Python code has access to:

```python
# Document instance
document  # The document being saved/deleted

# Document data
data  # Dictionary of document fields (modifiable)

# Current user
user  # User performing the action (may be None)

# Logger
logger  # Python logger for debugging

# Safe built-in functions
len, str, int, float, bool, list, dict, set
sum, min, max, abs, round
```

### Examples

**Set default value:**
```python
# Set created_date if not provided
if 'created_date' not in data or not data['created_date']:
    from django.utils import timezone
    data['created_date'] = timezone.now().isoformat()
```

**Validate data:**
```python
# Ensure amount is positive
if data.get('amount', 0) <= 0:
    raise ValueError("Amount must be greater than zero")
```

**Calculate fields:**
```python
# Calculate total from items
items = data.get('items', [])
total = sum(item.get('amount', 0) for item in items)
data['total'] = total
```

**Auto-numbering:**
```python
# Generate unique order number
if not data.get('order_number'):
    from datetime import datetime
    prefix = "ORD"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    data['order_number'] = f"{prefix}-{timestamp}"
```

**Prevent operation:**
```python
# Prevent save if status is invalid
if data.get('status') not in ['draft', 'approved', 'rejected']:
    raise ValueError(f"Invalid status: {data.get('status')}")
```

### Security

Python hooks run in a restricted environment:
- No access to `__builtins__`
- No `import` statement
- No file system access
- Limited to safe operations

---

## Webhook Hooks

### Configuration

**Webhook URL**: Full URL to send POST request to
**Webhook Headers**: JSON object of custom headers

**Example Headers:**
```json
{
    "Authorization": "Bearer YOUR_TOKEN",
    "X-Custom-Header": "value"
}
```

### Payload Format

Webhooks receive POST request with JSON payload:

```json
{
    "event": "after_save",
    "doctype": "Sales Order",
    "document": {
        "id": 123,
        "data": {
            "customer": "ACME Corp",
            "amount": 5000
        },
        "created_at": "2025-12-03T10:00:00Z",
        "updated_at": "2025-12-03T10:30:00Z"
    },
    "user": "user@example.com",
    "timestamp": "2025-12-03T10:30:00Z"
}
```

### Headers Sent

```
Content-Type: application/json
User-Agent: Doctype-Engine-Webhook/1.0
[Custom headers from configuration]
```

### Timeout

Webhook requests timeout after 30 seconds.

### Response Handling

- Status 200-299: Success
- Other status codes: Logged as error
- Network errors: Logged with traceback

---

## Email Hooks

### Configuration

**Email Template**: Django template syntax
**Email Recipients**: JSON array of email addresses

**Example Recipients:**
```json
["manager@company.com", "admin@company.com"]
```

### Template Context

Email templates have access to:

```django
{{ document }}       # Document instance
{{ data }}          # Document data dictionary
{{ doctype }}       # Doctype instance
{{ user }}          # Current user
```

### Example Template

```django
Document Update Notification

Doctype: {{ doctype.name }}
Document ID: {{ document.id }}

{% if data.customer %}
Customer: {{ data.customer }}
{% endif %}

{% if data.amount %}
Amount: ${{ data.amount }}
{% endif %}

This document was updated by {{ user.email }}.

View document: https://yoursite.com/doctypes/{{ doctype.slug }}/{{ document.id }}/
```

### Subject Line

Email subject is auto-generated:
```
[Doctype Name] Document Update
```

---

## Conditional Hooks

Use conditions to control when hooks execute.

### Condition Syntax

Python expression that evaluates to True/False:

```python
# Run only for high-value orders
data.get('amount', 0) > 10000

# Run only for specific status
data.get('status') == 'approved'

# Run only for specific user
user and user.email == 'manager@company.com'

# Complex condition
data.get('priority') == 'high' or data.get('amount', 0) > 50000
```

### Available Variables

- `document` - Document instance
- `data` - Document data dictionary
- `user` - Current user instance

### Examples

**Send email only for urgent items:**
```python
data.get('priority') == 'urgent'
```

**Webhook only for large amounts:**
```python
data.get('total_amount', 0) >= 100000
```

**Python validation only for submitted status:**
```python
data.get('status') == 'submitted'
```

---

## Error Handling

### Before Hooks (before_insert, before_save, before_delete)

If a before hook fails:
- Operation is **prevented**
- Exception is raised
- Error is logged
- User sees error message

**Use for:**
- Validation
- Permission checks
- Data integrity

### After Hooks (after_insert, after_save, after_delete)

If an after hook fails:
- Operation **completes** (document is saved/deleted)
- Error is logged
- Other hooks continue to execute

**Use for:**
- Notifications
- Webhooks
- Non-critical operations

### Error Logging

Hook failures are logged in:
1. Application logs (via logger)
2. Document data (`hook_failures` field)

**Example failure log:**
```json
{
    "hook_failures": [
        {
            "hook_id": 123,
            "hook_type": "after_save",
            "action_type": "webhook",
            "error": "Webhook request failed: Connection timeout",
            "timestamp": "2025-12-03T10:30:00Z"
        }
    ]
}
```

Last 10 failures are kept per document.

---

## Best Practices

### 1. Use Appropriate Hook Types

**before_insert/before_save:**
- Data validation
- Setting defaults
- Auto-numbering
- Permission checks

**after_insert/after_save:**
- Sending notifications
- Calling webhooks
- Creating audit logs
- Updating related documents

### 2. Keep Hooks Fast

Slow hooks delay document operations:
- Avoid complex calculations
- Don't make slow API calls in before_* hooks
- Use after_* hooks for non-critical operations

### 3. Handle Errors Gracefully

```python
# Good - specific error message
if data.get('amount', 0) <= 0:
    raise ValueError("Amount must be positive")

# Bad - generic error
if data.get('amount', 0) <= 0:
    raise Exception("Error")
```

### 4. Use Conditions Wisely

```python
# Good - specific condition
data.get('status') == 'approved' and data.get('amount', 0) > 1000

# Bad - complex logic in condition
# (Put complex logic in Python hook instead)
```

### 5. Test Hooks Thoroughly

1. Create test documents
2. Trigger hook events
3. Verify expected behavior
4. Check error handling
5. Review logs

### 6. Document Your Hooks

In hook description, document:
- Purpose of hook
- When it triggers
- What it does
- Any dependencies

### 7. Order Hooks Properly

Use `order` field to control execution sequence:
- Lower numbers run first
- Critical hooks should run before optional ones
- Validation before transformation

### 8. Monitor Hook Performance

Check logs for:
- Failed hooks
- Slow execution times
- Repeated failures
- Unexpected behavior

---

## Examples

### Auto-Generate Invoice Number

**Hook Type:** before_insert
**Action Type:** python

```python
# Generate invoice number: INV-2025-001
if not data.get('invoice_number'):
    from datetime import datetime
    year = datetime.now().year

    # Get last invoice number for this year
    # (Simplified - use atomic counter in production)
    counter = 1
    data['invoice_number'] = f"INV-{year}-{counter:03d}"
```

### Calculate Order Total

**Hook Type:** before_save
**Action Type:** python

```python
# Calculate total from line items
items = data.get('items', [])
subtotal = sum(item.get('amount', 0) for item in items)
tax = subtotal * 0.1  # 10% tax
data['subtotal'] = subtotal
data['tax'] = tax
data['total'] = subtotal + tax
```

### Validate Customer Credit Limit

**Hook Type:** before_save
**Action Type:** python
**Condition:** `data.get('status') == 'submitted'`

```python
# Prevent save if order exceeds credit limit
customer_credit_limit = 50000  # Get from customer record
order_total = data.get('total', 0)

if order_total > customer_credit_limit:
    raise ValueError(
        f"Order total ${order_total} exceeds "
        f"credit limit ${customer_credit_limit}"
    )
```

### Send Order Confirmation Email

**Hook Type:** after_insert
**Action Type:** email
**Recipients:** `["customer@example.com"]`

**Template:**
```django
Your order has been received!

Order Number: {{ data.order_number }}
Order Date: {{ data.order_date }}
Total: ${{ data.total }}

Items:
{% for item in data.items %}
- {{ item.product }}: ${{ item.amount }}
{% endfor %}

Thank you for your business!
```

### Notify External System via Webhook

**Hook Type:** after_save
**Action Type:** webhook
**Webhook URL:** `https://api.external-system.com/orders/update`
**Webhook Headers:**
```json
{
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}
```

### Archive Deleted Documents

**Hook Type:** after_delete
**Action Type:** python

```python
# Save deleted document data to archive
import json
from datetime import datetime

# Create archive entry
archive_data = {
    'original_id': document.id,
    'doctype': document.doctype.name,
    'data': data,
    'deleted_at': datetime.now().isoformat(),
    'deleted_by': user.email if user else None
}

# Save to archive (simplified)
logger.info(f"Archived document: {json.dumps(archive_data)}")
```

### Prevent Deletion of Submitted Documents

**Hook Type:** before_delete
**Action Type:** python

```python
# Prevent deletion if document is submitted
if data.get('status') == 'submitted':
    raise ValueError(
        "Cannot delete submitted documents. "
        "Please cancel the document first."
    )
```

### Send Slack Notification

**Hook Type:** after_save
**Action Type:** webhook
**Condition:** `data.get('status') == 'approved'`
**Webhook URL:** `https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK`

Payload will be sent automatically.

---

## Troubleshooting

### Hook Not Executing

**Check:**
1. Hook is marked as "Active"
2. Hook type matches the operation (insert vs save)
3. Condition evaluates to True
4. Hook order is correct
5. No errors in Python code/webhook URL

### Python Hook Errors

**Common issues:**
```python
# Error: NameError: name 'datetime' is not defined
# Fix: Import at usage, not at module level
from datetime import datetime

# Error: SyntaxError
# Fix: Check Python syntax carefully

# Error: KeyError: 'field_name'
# Fix: Use .get() instead of direct access
data.get('field_name')  # Returns None if missing
```

### Webhook Not Receiving Data

**Check:**
1. Webhook URL is correct and accessible
2. Server accepts POST requests
3. Headers are correct (especially Authorization)
4. Server timeout is >= 30 seconds
5. Check application logs for errors

### Emails Not Sending

**Check:**
1. SMTP settings configured in Django settings
2. Recipients array is valid JSON
3. Email addresses are correct
4. Template syntax is valid
5. Check email logs for errors

---

## Summary

**Hook System Features:**
- [YES] Python code execution
- [YES] Webhook HTTP calls
- [YES] Email triggers
- [YES] Conditional execution
- [YES] Error handling
- [YES] Automatic integration via signals
- [YES] Audit trail

**Hook Types:**
- before_insert, after_insert
- before_save, after_save
- before_delete, after_delete
- on_change

**Action Types:**
- Python code
- Webhook
- Email
- Notification

**Use Cases:**
- Data validation
- Auto-numbering
- Email notifications
- External system integration
- Business logic
- Audit logging

For more information, see Django Admin or contact your system administrator.

---

**Last Updated:** 2025-12-03
**Version:** 1.0
