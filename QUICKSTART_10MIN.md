# 10-Minute Quick Start: Build Your First Application

This guide will help you build a complete Task Management application in just 10 minutes.

## What You'll Build

A simple task management system where users can:
- Create tasks with title, description, priority, and due date
- Assign tasks to team members
- Track task status (To Do, In Progress, Done)
- View task lists and statistics

## Prerequisites

- Server running (http://localhost:8000)
- Admin credentials (username: spoofman, password: admin123)

## Step 1: Get Access Token (1 minute)

```bash
# Login to get your access token
curl -X POST http://localhost:8000/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "spoofman",
    "password": "admin123"
  }' | python -m json.tool

# Save the access_token from the response
export TOKEN="your-access-token-here"
```

## Step 2: Create the Module (1 minute)

```bash
# Create a "Projects" module
curl -X POST http://localhost:8000/api/modules/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Projects",
    "icon": "check-square",
    "color": "#3498db",
    "description": "Project and Task Management"
  }' | python -m json.tool

# Note the "id" from the response - you'll need it for the next step
```

## Step 3: Create Task Doctype (2 minutes)

```bash
# Create the Task doctype
curl -X POST http://localhost:8000/api/core/doctypes/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Task",
    "module_id": 1,
    "naming_rule": "TASK-{YYYY}-{#####}",
    "description": "Task tracking",
    "track_changes": true,
    "schema": {
      "fields": [
        {
          "name": "title",
          "type": "string",
          "label": "Task Title",
          "required": true
        },
        {
          "name": "description",
          "type": "text",
          "label": "Description"
        },
        {
          "name": "status",
          "type": "select",
          "label": "Status",
          "options": ["To Do", "In Progress", "Done"],
          "default": "To Do"
        },
        {
          "name": "priority",
          "type": "select",
          "label": "Priority",
          "options": ["Low", "Medium", "High", "Urgent"],
          "default": "Medium"
        },
        {
          "name": "due_date",
          "type": "date",
          "label": "Due Date"
        },
        {
          "name": "estimated_hours",
          "type": "integer",
          "label": "Estimated Hours"
        },
        {
          "name": "tags",
          "type": "string",
          "label": "Tags"
        }
      ]
    }
  }' | python -m json.tool

# Note the doctype "id" from the response
```

## Step 4: Create Sample Tasks (2 minutes)

```bash
# Create task 1
curl -X POST http://localhost:8000/api/core/doctypes/1/records/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Setup development environment",
    "description": "Install Python, Docker, and configure VS Code",
    "status": "Done",
    "priority": "High",
    "estimated_hours": 2,
    "tags": "setup, development"
  }' | python -m json.tool

# Create task 2
curl -X POST http://localhost:8000/api/core/doctypes/1/records/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Design database schema",
    "description": "Create ERD and define all tables",
    "status": "In Progress",
    "priority": "High",
    "due_date": "2025-12-15",
    "estimated_hours": 4,
    "tags": "design, database"
  }' | python -m json.tool

# Create task 3
curl -X POST http://localhost:8000/api/core/doctypes/1/records/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Write unit tests",
    "description": "Create comprehensive test suite for all modules",
    "status": "To Do",
    "priority": "Medium",
    "due_date": "2025-12-20",
    "estimated_hours": 8,
    "tags": "testing, quality"
  }' | python -m json.tool
```

## Step 5: Query Your Data (1 minute)

```bash
# Get all tasks
curl http://localhost:8000/api/core/doctypes/1/records/ \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Filter by status
curl "http://localhost:8000/api/core/doctypes/1/records/?status=In%20Progress" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool

# Filter by priority
curl "http://localhost:8000/api/core/doctypes/1/records/?priority=High" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

## Step 6: Update a Task (1 minute)

```bash
# Update task status to Done
curl -X PATCH http://localhost:8000/api/core/doctypes/1/records/2/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "Done"
  }' | python -m json.tool
```

## Step 7: View in Admin Panel (1 minute)

1. Open browser: http://localhost:8000/admin/
2. Login with: spoofman / admin123
3. Navigate to: **Doctypes → Task → Documents**
4. You'll see all your tasks with full CRUD interface!

## Step 8: Add More Features (1 minute)

Let's add a "Team Member" doctype and link it to tasks:

```bash
# Create Team Member doctype
curl -X POST http://localhost:8000/api/core/doctypes/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Team Member",
    "module_id": 1,
    "naming_rule": "TM-{####}",
    "schema": {
      "fields": [
        {
          "name": "full_name",
          "type": "string",
          "required": true
        },
        {
          "name": "email",
          "type": "email",
          "required": true
        },
        {
          "name": "role",
          "type": "select",
          "options": ["Developer", "Designer", "Manager", "QA"]
        }
      ]
    }
  }' | python -m json.tool
```

Now update the Task doctype to add an "assigned_to" field:

```bash
# Add custom field to Task doctype
curl -X POST http://localhost:8000/api/core/custom-fields/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "doctype_id": 1,
    "fieldname": "assigned_to",
    "label": "Assigned To",
    "fieldtype": "link",
    "options": {
      "link_doctype": "Team Member"
    }
  }' | python -m json.tool
```

## Congratulations!

In just 10 minutes, you've:
- [YES] Created a module
- [YES] Defined a doctype with 7 fields
- [YES] Created sample data
- [YES] Queried and filtered data
- [YES] Updated records
- [YES] Extended the schema with custom fields
- [YES] Linked multiple doctypes together

## What's Next?

### Add Workflow (5 minutes)

Create an approval workflow for high-priority tasks:

```bash
curl -X POST http://localhost:8000/api/workflows/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Task Approval Flow",
    "doctype_id": 1,
    "is_active": true,
    "workflow_data": {
      "states": [
        {"name": "To Do", "is_initial": true, "color": "#gray"},
        {"name": "In Progress", "color": "#blue"},
        {"name": "Review", "color": "#orange"},
        {"name": "Done", "is_final": true, "color": "#green"}
      ],
      "transitions": [
        {
          "from_state": "To Do",
          "to_state": "In Progress",
          "label": "Start Work"
        },
        {
          "from_state": "In Progress",
          "to_state": "Review",
          "label": "Submit for Review"
        },
        {
          "from_state": "Review",
          "to_state": "Done",
          "label": "Approve"
        }
      ]
    }
  }'
```

### Add Automation (5 minutes)

Send email when high-priority task is created:

```bash
curl -X POST http://localhost:8000/api/hooks/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "doctype_id": 1,
    "hook_type": "after_insert",
    "action_type": "email",
    "condition": "doc.priority == '\''Urgent'\''",
    "email_template": "Urgent task created: {doc.title}",
    "email_recipients": ["manager@company.com"],
    "is_active": true
  }'
```

### Create a Report (5 minutes)

```bash
curl -X POST http://localhost:8000/api/reports/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Task Statistics",
    "doctype_id": 1,
    "report_type": "sql",
    "query": "SELECT status, priority, COUNT(*) as count FROM document WHERE doctype_id = 1 GROUP BY status, priority",
    "columns": [
      {"label": "Status", "field": "status"},
      {"label": "Priority", "field": "priority"},
      {"label": "Count", "field": "count"}
    ]
  }'
```

### Build a Frontend (10 minutes)

Create a simple HTML page:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Task Manager</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        .task { border: 1px solid #ddd; padding: 10px; margin: 10px 0; }
        .task.high { border-left: 4px solid red; }
        .task.medium { border-left: 4px solid orange; }
        .task.low { border-left: 4px solid green; }
    </style>
</head>
<body>
    <h1>My Tasks</h1>
    <div id="tasks"></div>

    <script>
        const API_URL = 'http://localhost:8000/api/core/doctypes/1/records/';
        const TOKEN = 'your-token-here';

        async function loadTasks() {
            const response = await fetch(API_URL, {
                headers: {
                    'Authorization': `Bearer ${TOKEN}`
                }
            });
            const data = await response.json();

            const tasksDiv = document.getElementById('tasks');
            data.results.forEach(task => {
                const taskEl = document.createElement('div');
                taskEl.className = `task ${task.data.priority.toLowerCase()}`;
                taskEl.innerHTML = `
                    <h3>${task.data.title}</h3>
                    <p>${task.data.description || 'No description'}</p>
                    <p><strong>Status:</strong> ${task.data.status}</p>
                    <p><strong>Priority:</strong> ${task.data.priority}</p>
                    <p><strong>Due:</strong> ${task.data.due_date || 'Not set'}</p>
                `;
                tasksDiv.appendChild(taskEl);
            });
        }

        loadTasks();
    </script>
</body>
</html>
```

## Real-World Extensions

### Multi-Project Support

Add a Project doctype and link tasks to projects:

```bash
# Create Project doctype
curl -X POST http://localhost:8000/api/core/doctypes/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Project",
    "module_id": 1,
    "schema": {
      "fields": [
        {"name": "project_name", "type": "string", "required": true},
        {"name": "client", "type": "string"},
        {"name": "start_date", "type": "date"},
        {"name": "end_date", "type": "date"},
        {"name": "budget", "type": "currency"}
      ]
    }
  }'

# Add project field to Task
curl -X POST http://localhost:8000/api/core/custom-fields/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "doctype_id": 1,
    "fieldname": "project",
    "label": "Project",
    "fieldtype": "link",
    "options": {"link_doctype": "Project"}
  }'
```

### Time Tracking

Add a Time Log doctype:

```bash
curl -X POST http://localhost:8000/api/core/doctypes/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Time Log",
    "module_id": 1,
    "naming_rule": "TL-{YYYY}-{#####}",
    "schema": {
      "fields": [
        {"name": "task", "type": "link", "link_doctype": "Task", "required": true},
        {"name": "hours", "type": "decimal", "required": true},
        {"name": "date", "type": "date", "default": "today"},
        {"name": "description", "type": "text"}
      ]
    }
  }'
```

### Comments/Activity Feed

Add a Comment doctype:

```bash
curl -X POST http://localhost:8000/api/core/doctypes/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Task Comment",
    "module_id": 1,
    "schema": {
      "fields": [
        {"name": "task", "type": "link", "link_doctype": "Task", "required": true},
        {"name": "comment", "type": "text", "required": true}
      ]
    }
  }'
```

## Tips for Success

1. **Start Small**: Begin with core fields, add more later
2. **Use Admin Panel**: Visual interface for managing data
3. **Test with Real Data**: Create realistic sample records
4. **Iterate**: The beauty of this system is you can modify schema anytime
5. **Security**: Configure permissions before going to production
6. **Documentation**: Document your doctypes and workflows

## Common Commands Cheatsheet

```bash
# List all modules
curl http://localhost:8000/api/modules/ \
  -H "Authorization: Bearer $TOKEN"

# List all doctypes
curl http://localhost:8000/api/core/doctypes/ \
  -H "Authorization: Bearer $TOKEN"

# Get specific record
curl http://localhost:8000/api/core/doctypes/1/records/2/ \
  -H "Authorization: Bearer $TOKEN"

# Delete record
curl -X DELETE http://localhost:8000/api/core/doctypes/1/records/2/ \
  -H "Authorization: Bearer $TOKEN"

# Search records
curl "http://localhost:8000/api/core/doctypes/1/records/?search=keyword" \
  -H "Authorization: Bearer $TOKEN"

# Pagination
curl "http://localhost:8000/api/core/doctypes/1/records/?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

**Issue**: 401 Unauthorized
**Solution**: Token expired, login again to get new token

**Issue**: 404 Not Found
**Solution**: Check doctype ID in URL

**Issue**: 400 Bad Request
**Solution**: Check JSON syntax and required fields

**Issue**: 500 Internal Server Error
**Solution**: Check server logs: `docker-compose logs web`

## Next Steps

- Read [REAL_WORLD_APPLICATIONS.md](REAL_WORLD_APPLICATIONS.md) for more complex examples
- Check [ENGINE_GUIDE.md](ENGINE_GUIDE.md) for complete feature documentation
- Review [README.md](README.md) for security and deployment guides

## Support

- Documentation: http://localhost:8000/api/docs/
- Admin Panel: http://localhost:8000/admin/
- OpenAPI Schema: http://localhost:8000/api/schema/

Happy building! 
