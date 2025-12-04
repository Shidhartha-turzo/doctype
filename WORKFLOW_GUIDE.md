# Workflow System Guide

Complete guide for implementing and using workflows in Doctype Engine.

## Table of Contents
1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Workflow Configuration](#workflow-configuration)
4. [State Transitions](#state-transitions)
5. [Permissions](#permissions)
6. [API Reference](#api-reference)
7. [UI Components](#ui-components)
8. [Email Notifications](#email-notifications)
9. [Python API](#python-api)
10. [Best Practices](#best-practices)

---

## Overview

The Workflow System provides state machine functionality for documents, enabling:

- **State Management** - Define states for your documents (Draft, Submitted, Approved, etc.)
- **Controlled Transitions** - Define allowed transitions between states
- **Permission Control** - Restrict who can perform transitions based on roles
- **Automation** - Execute actions on transitions (email, webhooks, field updates)
- **Audit Trail** - Complete history of all state changes
- **Email Notifications** - Automatic notifications on state changes

---

## Quick Start

### 1. Create a Workflow

In Django Admin:
1. Go to **Workflows**
2. Click **Add Workflow**
3. Fill in:
   - Name: "Sales Order Approval"
   - Doctype: Select your doctype (e.g., "Sales Order")
   - Description: "Approval workflow for sales orders"
   - Is Active: [YES]

### 2. Define States

For each state you want:
1. Click **Add State** under the workflow
2. Fill in:
   - Name: "Draft"
   - Is Initial: [YES] (for the first state)
   - Color: Choose a color (hex code)
   - Description: Optional

Example states for Sales Order:
- **Draft** (Initial, #gray)
- **Submitted** (#blue)
- **Approved** (Success, Final, #green)
- **Rejected** (Final, #red)

### 3. Define Transitions

For each allowed transition:
1. Click **Add Transition**
2. Fill in:
   - From State: "Draft"
   - To State: "Submitted"
   - Label: "Submit for Approval"
   - Require Comment: [YES] (optional)
   - Allowed Roles: Select roles (optional)

Example transitions:
- Draft → Submitted ("Submit for Approval")
- Submitted → Approved ("Approve")
- Submitted → Rejected ("Reject")
- Submitted → Draft ("Return to Draft")

### 4. Initialize Workflow on Document

**Via API:**
```bash
POST /api/doctypes/documents/{document_id}/workflow/init/
```

**Via Python:**
```python
from doctypes.workflow_engine import initialize_workflow

initialize_workflow(document, user)
```

### 5. Execute Transitions

**Via UI:**
- Open document in edit view
- Workflow widget appears with available transitions
- Click transition button
- Add comment if required
- Confirm

**Via API:**
```bash
POST /api/doctypes/documents/{document_id}/workflow/transition/
{
    "transition_id": 123,
    "comment": "Looks good, approved",
    "notify": true
}
```

---

## Workflow Configuration

### States

Each state represents a specific status of the document.

**Fields:**
- **Name** - Unique name for the state
- **Description** - Optional description
- **Is Initial** - Mark as starting state
- **Is Final** - Mark as ending state (no transitions out)
- **Is Success** - Mark successful final states (e.g., Approved vs Rejected)
- **Color** - Hex color for UI display (#FF0000)
- **Position X/Y** - For visual workflow designer (future)

**Examples:**
```python
# Draft state
name = "Draft"
is_initial = True
color = "#6c757d"

# Approved state
name = "Approved"
is_final = True
is_success = True
color = "#28a745"

# Rejected state
name = "Rejected"
is_final = True
is_success = False
color = "#dc3545"
```

### Transitions

Transitions define allowed state changes.

**Fields:**
- **From State** - Source state
- **To State** - Target state
- **Label** - Button text (e.g., "Submit", "Approve")
- **Condition** - Python expression for conditional logic
- **Allowed Roles** - User groups that can execute this transition
- **Require Comment** - Force user to add a comment
- **Actions** - JSON array of actions to execute

**Examples:**
```python
# Simple transition
from_state = Draft
to_state = Submitted
label = "Submit for Approval"

# With permissions
allowed_roles = ["Sales Manager", "Admin"]

# With required comment
require_comment = True

# With condition
condition = "document.data.get('amount', 0) < 10000"
```

### Conditional Transitions

Use Python expressions to control when transitions are available.

**Available Variables:**
- `document` - The document instance
- `user` - The current user
- `data` - document.data dictionary

**Examples:**
```python
# Amount-based condition
"data.get('amount', 0) > 5000"

# Date-based condition
"data.get('due_date') and data['due_date'] < '2025-12-31'"

# User-based condition
"user.email.endswith('@company.com')"

# Complex condition
"data.get('priority') == 'high' or data.get('amount', 0) > 10000"
```

### Transition Actions

Execute automated actions on transitions.

**Action Types:**
```json
[
    {
        "type": "set_field",
        "field": "approved_date",
        "value": "2025-12-03"
    },
    {
        "type": "send_email",
        "recipients": ["manager@company.com"],
        "template": "approval_notification"
    },
    {
        "type": "webhook",
        "url": "https://api.example.com/notify",
        "method": "POST"
    }
]
```

---

## State Transitions

### Transition Flow

1. **User clicks transition button**
2. **Permission check** - Verify user has required role
3. **Condition check** - Evaluate condition if present
4. **Comment validation** - Ensure comment if required
5. **Execute transition**
   - Update document state
   - Log transition in history
   - Execute actions
   - Send notifications
6. **UI update** - Refresh workflow widget

### Permission Checking

Before transition:
```python
from doctypes.workflow_engine import WorkflowEngine

engine = WorkflowEngine(document, user)
can_transition, reason = engine.can_transition(transition)

if can_transition:
    # Execute transition
else:
    # Show reason to user
```

### Transition History

All transitions are logged:
```python
{
    "from_state": "Draft",
    "to_state": "Submitted",
    "changed_by": "user@example.com",
    "changed_at": "2025-12-03T10:30:00",
    "comment": "Ready for review"
}
```

---

## Permissions

### Role-Based Access Control

Restrict transitions to specific roles:

```python
transition = WorkflowTransition.objects.create(
    from_state=submitted,
    to_state=approved,
    label="Approve",
    allowed_roles=[manager_group, admin_group]
)
```

### Superuser Override

Superusers can always execute any transition.

### Permission Checking

```python
# Check if user can execute transition
can_transition, reason = engine.can_transition(transition)

# Returns:
# (True, None) - Can execute
# (False, "User does not have required role(s): Manager") - Cannot execute
```

---

## API Reference

### Initialize Workflow

**Endpoint:** `POST /api/doctypes/documents/{document_id}/workflow/init/`

**Response:**
```json
{
    "success": true,
    "message": "Workflow initialized to state: Draft",
    "workflow": "Sales Order Approval",
    "current_state": "Draft"
}
```

### Get Workflow State

**Endpoint:** `GET /api/doctypes/documents/{document_id}/workflow/state/`

**Response:**
```json
{
    "has_workflow": true,
    "workflow": "Sales Order Approval",
    "current_state": {
        "id": 1,
        "name": "Draft",
        "color": "#6c757d",
        "is_final": false,
        "is_success": false
    },
    "available_transitions": [
        {
            "id": 10,
            "label": "Submit for Approval",
            "from_state": "Draft",
            "to_state": "Submitted",
            "require_comment": false,
            "can_execute": true,
            "reason": null
        }
    ],
    "history": [...]
}
```

### Execute Transition

**Endpoint:** `POST /api/doctypes/documents/{document_id}/workflow/transition/`

**Request:**
```json
{
    "transition_id": 10,
    "comment": "Ready for review",
    "notify": true
}
```

**Response:**
```json
{
    "success": true,
    "message": "Document transitioned to state: Submitted",
    "previous_state": "Draft",
    "current_state": "Submitted",
    "transitioned_by": "user@example.com"
}
```

### Get Workflow History

**Endpoint:** `GET /api/doctypes/documents/{document_id}/workflow/history/`

**Response:**
```json
{
    "document_id": 123,
    "history": [
        {
            "from_state": "Draft",
            "to_state": "Submitted",
            "changed_by": "user@example.com",
            "changed_at": "2025-12-03T10:30:00",
            "comment": "Ready for review"
        }
    ]
}
```

### Get Doctype Workflow

**Endpoint:** `GET /api/doctypes/{slug}/workflow/`

**Response:**
```json
{
    "has_workflow": true,
    "workflow": {
        "id": 1,
        "name": "Sales Order Approval",
        "description": "Approval workflow for sales orders"
    },
    "states": [...],
    "transitions": [...]
}
```

### Check Transition Permission

**Endpoint:** `POST /api/doctypes/documents/{document_id}/workflow/check/`

**Request:**
```json
{
    "transition_id": 10
}
```

**Response:**
```json
{
    "can_transition": true,
    "transition": {
        "id": 10,
        "label": "Approve",
        "from_state": "Submitted",
        "to_state": "Approved"
    },
    "reason": null
}
```

---

## UI Components

### Workflow Widget

The workflow widget is automatically displayed on document edit pages:

**Features:**
- Current state badge with color
- Available transition buttons
- Disabled buttons show reason on hover
- Transition modal for confirmation
- Comment field (required/optional)
- Workflow history viewer

**Location:** Appears after document fields, before Save button

### Transition Buttons

Buttons are styled based on action:
- **Approve** - Green
- **Reject** - Red
- **Other** - Blue

**States:**
- Enabled - User can execute
- Disabled - Shows reason on hover

### Transition Modal

Appears when user clicks transition:
- Shows transition details
- Optional comment field (required if configured)
- Cancel / Confirm buttons

### History Viewer

Collapsible history section shows:
- All past transitions
- User who made the change
- Timestamp
- Comments

---

## Email Notifications

### Automatic Notifications

Sent automatically on state transitions to:
- Document creator
- Assigned users (if `assigned_to` field exists)
- Watchers (if `watchers` field exists)

### Notification Content

**Subject:** `{Doctype Name} - State Changed to {New State}`

**Content:**
- State transition (From → To)
- Document details
- Changed by user
- Comment (if provided)
- Link to view document

### Email Templates

**HTML:** `doctypes/templates/doctypes/emails/workflow_notification.html`
**Text:** `doctypes/templates/doctypes/emails/workflow_notification.txt`

### Customization

Modify templates to:
- Add company branding
- Include additional document fields
- Change styling
- Add custom content

---

## Python API

### WorkflowEngine Class

```python
from doctypes.workflow_engine import WorkflowEngine
from doctypes.models import Document

document = Document.objects.get(id=123)
engine = WorkflowEngine(document, user)

# Get workflow
workflow = engine.get_workflow()

# Get current state
current_state = engine.get_current_state()

# Get available transitions
transitions = engine.get_available_transitions()

# Check if can transition
can_transition, reason = engine.can_transition(transition)

# Execute transition
doc_state = engine.execute_transition(transition, comment="Approved", notify=True)

# Get history
history = engine.get_workflow_history()

# Check if in final state
is_final = engine.is_in_final_state()
is_success = engine.is_in_success_state()
```

### Convenience Functions

```python
from doctypes.workflow_engine import (
    initialize_workflow,
    get_available_transitions,
    execute_transition,
    get_current_state
)

# Initialize workflow
doc_state = initialize_workflow(document, user)

# Get available transitions
transitions = get_available_transitions(document, user)

# Execute transition
doc_state = execute_transition(document, transition, user, comment="Approved")

# Get current state
state = get_current_state(document)
```

### In Django Signals

```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from doctypes.models import Document
from doctypes.workflow_engine import initialize_workflow

@receiver(post_save, sender=Document)
def auto_initialize_workflow(sender, instance, created, **kwargs):
    """Auto-initialize workflow for new documents"""
    if created:
        try:
            initialize_workflow(instance)
        except:
            pass  # No workflow configured
```

---

## Best Practices

### 1. Keep States Simple

Use clear, business-meaningful state names:
- **Good**: Draft, Submitted, Approved, Rejected
- **Bad**: state1, pending_review_stage_2, tmp_status

### 2. Use Descriptive Labels

Transition labels should be action-oriented:
- **Good**: "Submit for Approval", "Approve", "Return to Draft"
- **Bad**: "Next", "OK", "Change State"

### 3. Require Comments for Important Transitions

```python
# Approval/rejection should have comments
transition.require_comment = True  # For Approve/Reject

# Draft submissions may not need comments
transition.require_comment = False  # For Submit
```

### 4. Limit Allowed Roles

Don't make everyone an approver:
```python
# Good - specific roles
allowed_roles = ["Manager", "Director"]

# Bad - too permissive
allowed_roles = []  # Anyone can approve
```

### 5. Use Conditions for Business Logic

```python
# Require manager approval for high-value orders
condition = "data.get('amount', 0) > 10000"
allowed_roles = ["Manager"]

# Auto-approve small orders
condition = "data.get('amount', 0) <= 1000"
allowed_roles = ["Sales Rep"]
```

### 6. Design Clear Final States

Have distinct success/failure states:
- **Success**: Approved, Completed, Delivered
- **Failure**: Rejected, Cancelled, Failed

### 7. Test Workflow Thoroughly

Before going live:
1. Create test documents
2. Execute all possible transitions
3. Verify permissions
4. Check email notifications
5. Review history logging

### 8. Document Your Workflow

Add clear descriptions:
- Workflow description
- State descriptions
- Transition purposes
- Required fields for transitions

---

## Troubleshooting

### Workflow Not Appearing

**Problem:** Workflow widget doesn't show on document page

**Solutions:**
1. Ensure workflow is marked as "Active"
2. Check workflow is assigned to correct doctype
3. Verify document has been saved (widget only shows for existing documents)
4. Check browser console for JavaScript errors

### Transition Button Disabled

**Problem:** User can't click transition button

**Solutions:**
1. Check user has required role
2. Verify transition condition is met
3. Check document is in correct current state
4. Hover over button to see reason

### Notifications Not Sending

**Problem:** Email notifications not received

**Solutions:**
1. Verify SMTP settings configured
2. Check document has recipient fields (created_by, assigned_to, watchers)
3. Review email logs for errors
4. Test with simple transition first

### Permission Denied Errors

**Problem:** User gets "Permission Denied" when trying transition

**Solutions:**
1. Check user is in allowed_roles
2. Verify user is authenticated
3. Check condition evaluates to True
4. Review user's group memberships

---

## Examples

### Simple Approval Workflow

```python
# States
draft = WorkflowState.objects.create(
    workflow=workflow,
    name="Draft",
    is_initial=True,
    color="#6c757d"
)

approved = WorkflowState.objects.create(
    workflow=workflow,
    name="Approved",
    is_final=True,
    is_success=True,
    color="#28a745"
)

# Transition
WorkflowTransition.objects.create(
    workflow=workflow,
    from_state=draft,
    to_state=approved,
    label="Approve",
    require_comment=True,
    allowed_roles=[manager_group]
)
```

### Multi-Step Approval

```python
# States: Draft → Submitted → Reviewed → Approved

# Transitions:
# 1. Draft → Submitted (Anyone)
WorkflowTransition.objects.create(
    from_state=draft,
    to_state=submitted,
    label="Submit"
)

# 2. Submitted → Reviewed (Team Lead only)
WorkflowTransition.objects.create(
    from_state=submitted,
    to_state=reviewed,
    label="Review",
    allowed_roles=[team_lead_group],
    require_comment=True
)

# 3. Reviewed → Approved (Manager only, high value)
WorkflowTransition.objects.create(
    from_state=reviewed,
    to_state=approved,
    label="Approve",
    allowed_roles=[manager_group],
    condition="data.get('amount', 0) > 5000",
    require_comment=True
)
```

---

## Summary

**Key Features:**
- State machine for documents
- Role-based permissions
- Conditional transitions
- Automated actions
- Email notifications
- Complete audit trail
- Visual UI components

**Files Created:**
- `doctypes/workflow_engine.py` - Workflow execution engine
- `doctypes/workflow_views.py` - API endpoints
- `doctypes/templates/doctypes/workflow_widget.html` - UI component
- `doctypes/templates/doctypes/emails/workflow_notification.html` - Email template

**API Endpoints:**
- `/api/doctypes/documents/{id}/workflow/init/` - Initialize workflow
- `/api/doctypes/documents/{id}/workflow/state/` - Get state and transitions
- `/api/doctypes/documents/{id}/workflow/transition/` - Execute transition
- `/api/doctypes/documents/{id}/workflow/history/` - Get history
- `/api/doctypes/{slug}/workflow/` - Get workflow configuration

For more information, see the Django Admin interface or contact your system administrator.

---

**Last Updated:** 2025-12-03
**Version:** 1.0
