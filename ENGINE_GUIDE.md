# Doctype Engine - Complete Guide

**A Modern, Innovative Doctype Engine inspired by Frappe but with Next-Generation Features**

## 🚀 Overview

The Doctype Engine is a comprehensive framework for building dynamic data-driven applications. Like Frappe's doctype system but modernized with:
- Module-based organization
- Enhanced field types
- Visual workflow designer
- Real-time webhooks
- Computed fields
- Dynamic permissions
- Audit trail & versioning
- Custom fields at runtime

---

## 📁 Architecture

### **Modules → Doctypes → Documents**

```
Module (e.g., CRM)
  ├── Doctype (e.g., Customer)
  │   ├── Fields (name, email, phone, rating)
  │   ├── Permissions (who can read/write)
  │   ├── Workflows (Draft → Approved → Active)
  │   ├── Hooks (before_save, after_insert)
  │   └── Naming Rules (CUST-####)
  └── Documents (actual customer records)
      ├── CUST-0001 (John Doe)
      ├── CUST-0002 (Jane Smith)
      └── ...
```

---

## 🏗️ Core Components

### 1. **Modules**
Organize doctypes into logical groups.

**Features:**
- Hierarchical (modules can have submodules)
- Custom icons & colors
- Drag-and-drop ordering
- System vs Custom modules

**Example:**
```python
{
  "name": "CRM",
  "icon": "👥",
  "color": "#3498db",
  "submodules": ["Sales", "Marketing"]
}
```

### 2. **Doctypes**
Define document schemas with rich metadata.

**Core Features:**
- 20+ field types
- Link to other doctypes
- Child tables (one-to-many)
- Tree/hierarchical structures
- Single doctypes (one record only)
- Submittable (approval workflow)

**Field Types:**
```
Basic: string, text, integer, decimal, boolean, date, datetime, json
Advanced: link, select, multiselect, table, file, image
Special: email, phone, url, color, rating, currency, percent, duration
Computed: Dynamic formulas
```

**Example Doctype:**
```json
{
  "name": "Sales Order",
  "module": "Sales",
  "is_submittable": true,
  "naming_rule": "SO-{####}",
  "schema": {
    "fields": [
      {
        "name": "customer",
        "type": "link",
        "link_doctype": "Customer",
        "required": true
      },
      {
        "name": "order_date",
        "type": "date",
        "default": "today"
      },
      {
        "name": "items",
        "type": "table",
        "child_doctype": "Sales Order Item"
      },
      {
        "name": "total_amount",
        "type": "computed",
        "formula": "sum(items.amount)"
      },
      {
        "name": "status",
        "type": "select",
        "options": ["Draft", "Pending", "Completed"]
      }
    ]
  }
}
```

### 3. **Documents**
Instances of doctypes.

**Features:**
- Auto-naming with series
- Draft/Submitted/Cancelled states
- Version history
- Soft delete
- Tree structure support
- Workflow states

**Document Lifecycle:**
```
Create → Draft → Submit → Approved → Cancelled
                          ↓
                      [Versions tracked]
```

---

## 🔐 Permissions System

Role-based access control at doctype level.

**Permission Types:**
- Create, Read, Write, Delete
- Submit, Cancel, Amend
- Export, Import, Share

**Conditional Permissions:**
```python
# Python expression for dynamic access
"user.department == doc.department"
"doc.status == 'Draft' and doc.created_by == user"
```

**Field-Level Security:**
- Read-only fields per role
- Hidden fields per role

**Example:**
```python
{
  "doctype": "Employee",
  "role": "HR Manager",
  "can_read": true,
  "can_write": true,
  "can_delete": false,
  "read_only_fields": ["employee_id"],
  "hidden_fields": ["salary"],
  "permission_condition": "doc.department == user.department"
}
```

---

## 🔄 Workflow Engine

Visual state machine for document approval flows.

**Components:**
- **States**: Draft, Pending Approval, Approved, Rejected
- **Transitions**: Rules for moving between states
- **Actions**: What happens on transition
- **Conditions**: When transitions are allowed

**Example Workflow:**
```python
{
  "name": "Leave Approval",
  "doctype": "Leave Application",
  "states": [
    {"name": "Draft", "is_initial": true, "color": "#gray"},
    {"name": "Pending", "color": "#orange"},
    {"name": "Approved", "is_final": true, "color": "#green"},
    {"name": "Rejected", "is_final": true, "color": "#red"}
  ],
  "transitions": [
    {
      "from": "Draft",
      "to": "Pending",
      "label": "Submit",
      "allowed_roles": ["Employee"]
    },
    {
      "from": "Pending",
      "to": "Approved",
      "label": "Approve",
      "allowed_roles": ["Manager"],
      "condition": "doc.days <= 5 or user.is_hr_manager",
      "actions": [
        {"type": "email", "to": "doc.employee_email"},
        {"type": "webhook", "url": "https://api.example.com/notify"}
      ]
    }
  ]
}
```

---

## 🎯 Hooks & Events

Extensibility through event-driven hooks.

**Hook Types:**
- `before_insert` - Before creating document
- `after_insert` - After creating document
- `before_save` - Before any save
- `after_save` - After any save
- `before_submit` - Before submission
- `after_submit` - After submission
- `before_delete` - Before deletion
- `after_delete` - After deletion
- `on_change` - When specific field changes

**Action Types:**
1. **Python Code**: Execute custom logic
2. **Webhook**: HTTP POST to external API
3. **Email**: Send notification
4. **System Notification**: In-app alert

**Example:**
```python
{
  "doctype": "Sales Order",
  "hook_type": "after_submit",
  "action_type": "webhook",
  "webhook_url": "https://api.inventory.com/reserve",
  "webhook_headers": {
    "Authorization": "Bearer token123"
  },
  "condition": "doc.total_amount > 10000"
}
```

---

## 🔢 Naming Series

Automatic document naming with patterns.

**Formats:**
- `{prefix}-{####}` → CUST-0001
- `{module}-{YYYY}-{####}` → CRM-2025-0001
- `{field}-{###}` → Based on field value
- `{uuid}` → Random UUID
- `prompt` → Ask user

**Example:**
```python
{
  "doctype": "Invoice",
  "series_name": "Standard Invoice",
  "prefix": "INV",
  "padding": 5,
  "current_value": 1250
}
# Generates: INV-01251, INV-01252, ...
```

---

## 📊 Document Versioning

Complete audit trail of all changes.

**Tracked Information:**
- What changed
- Who changed it
- When it changed
- Previous value vs new value

**Version History:**
```json
{
  "document": "CUST-0001",
  "version_number": 3,
  "changes": {
    "email": {
      "old": "john@old.com",
      "new": "john@new.com"
    },
    "phone": {
      "old": "+1234567890",
      "new": "+0987654321"
    }
  },
  "changed_by": "admin",
  "changed_at": "2025-12-01T14:30:00Z",
  "comment": "Updated contact information"
}
```

---

## 🎨 Custom Fields

Add fields to existing doctypes without schema migration.

**Features:**
- Runtime field addition
- No database migration needed
- Preserved across updates
- Position control (insert_after)

**Example:**
```python
{
  "doctype": "Customer",
  "fieldname": "loyalty_points",
  "label": "Loyalty Points",
  "fieldtype": "integer",
  "default_value": "0",
  "insert_after": "customer_type",
  "is_required": false
}
```

---

## 📈 Reports

Custom reports with multiple formats.

**Report Types:**
1. **Query Builder**: Visual query construction
2. **SQL Query**: Direct SQL for complex reports
3. **Python Script**: Full programmatic control

**Example:**
```python
{
  "name": "Sales by Customer",
  "doctype": "Sales Order",
  "report_type": "sql",
  "query": """
    SELECT
      customer,
      COUNT(*) as order_count,
      SUM(total_amount) as total_sales
    FROM sales_order
    WHERE status = 'Completed'
    GROUP BY customer
    ORDER BY total_sales DESC
  """,
  "columns": [
    {"label": "Customer", "field": "customer"},
    {"label": "Orders", "field": "order_count"},
    {"label": "Total Sales", "field": "total_sales", "format": "currency"}
  ],
  "filters": [
    {"label": "From Date", "fieldtype": "date"},
    {"label": "To Date", "fieldtype": "date"}
  ]
}
```

---

## 🔗 Relationships & Links

Connect doctypes together.

**Link Field:**
```json
{
  "name": "customer",
  "type": "link",
  "link_doctype": "Customer",
  "required": true
}
```

**Child Tables (One-to-Many):**
```json
{
  "name": "items",
  "type": "table",
  "child_doctype": "Sales Order Item"
}
```

**Tree Structure (Self-Referencing):**
```json
{
  "doctype": "Department",
  "is_tree": true,
  // Creates parent_document field automatically
}
```

---

## 💡 Computed Fields

Dynamic calculations using formulas.

**Examples:**
```javascript
// Simple arithmetic
"quantity * rate"

// Functions
"sum(items.amount)"
"max(items.discount)"
"count(items)"

// Conditionals
"status == 'Approved' ? total * 0.9 : total"

// Date functions
"date_diff(end_date, start_date)"
```

---

## 🌐 API Integration

Full REST API for all operations.

### Create Module
```bash
POST /api/modules/
{
  "name": "HR",
  "icon": "👤",
  "color": "#2ecc71"
}
```

### Create Doctype
```bash
POST /api/core/doctypes/
{
  "name": "Employee",
  "module_id": 1,
  "is_submittable": false,
  "schema": { ... }
}
```

### Create Document
```bash
POST /api/core/doctypes/{id}/records/
{
  "employee_name": "John Doe",
  "department": "Engineering",
  "joining_date": "2025-01-01"
}
```

### Submit Document
```bash
POST /api/core/documents/{id}/submit/
```

### Get Workflow States
```bash
GET /api/workflows/{doctype_id}/states/
```

---

## 🎓 Example Use Cases

### 1. **CRM System**
```
Modules: Sales, Marketing, Support
Doctypes: Customer, Lead, Opportunity, Quote, Sales Order
Workflows: Lead → Qualified → Opportunity → Won/Lost
```

### 2. **HR Management**
```
Modules: HR, Payroll, Recruitment
Doctypes: Employee, Leave Application, Salary Slip, Job Opening
Workflows: Leave (Draft → Pending → Approved)
Naming: EMP-####, LEAVE-YYYY-####
```

### 3. **Inventory System**
```
Modules: Stock, Purchase, Sales
Doctypes: Item, Warehouse, Stock Entry, Purchase Order
Links: Purchase Order → Supplier, Item
Child Tables: Purchase Order Items
Computed: total_amount = sum(items.amount)
```

---

## 🚀 Innovations vs Frappe

| Feature | Frappe | Our Engine |
|---------|--------|------------|
| Storage | Dynamic Tables | JSON (easier) |
| Workflows | Basic | Visual Designer |
| Hooks | Python only | Python + Webhooks + Email |
| Permissions | Role-based | Role + Conditional |
| Versioning | Basic | Complete audit trail |
| Custom Fields | Yes | Yes + Runtime |
| Computed Fields | Server-side | Server + Client formulas |
| API | REST | REST + GraphQL ready |
| Real-time | Polling | WebSocket ready |
| Module Hierarchy | Flat | Tree structure |

---

## 📚 Next Steps

1. **Create Your First Module** in admin panel
2. **Design a Doctype** with fields
3. **Set up Permissions** for roles
4. **Create a Workflow** if needed
5. **Add Hooks** for automation
6. **Build Reports** for insights
7. **Integrate via API** with frontend

The engine is running at **http://localhost:8000/admin/**

Login: `spoofman` / `admin123`

Happy Building! 🎉
