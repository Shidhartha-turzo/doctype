# Doctype API - Complete Guide

The Doctype API is now live with all the endpoints from your Postman collection!

## Base URL
`http://localhost:8000`

## Swagger Documentation
**Interactive API Documentation:** http://localhost:8000/api/docs/
**ReDoc Documentation:** http://localhost:8000/api/redoc/
**OpenAPI Schema:** http://localhost:8000/api/schema/

---

## Authentication Endpoints

### 1. Request Magic Link
```bash
POST /auth/magic-link/
Content-Type: application/json

{
  "email": "user@example.com"
}
```

### 2. Login (Username & Password)
```bash
POST /auth/login/
Content-Type: application/json

{
  "username": "spoofman",
  "password": "admin123"
}

# Response:
{
  "access_token": "...",
  "refresh_token": "...",
  "session_key": "...",
  "user": {
    "id": 1,
    "username": "spoofman",
    "email": "admin@example.com"
  }
}
```

### 3. Refresh Token
```bash
POST /auth/token/refresh/
Content-Type: application/json

{
  "refresh_token": "YOUR_REFRESH_TOKEN"
}
```

### 4. List Active Sessions
```bash
GET /auth/sessions/
Authorization: Bearer YOUR_ACCESS_TOKEN
```

### 5. Logout
```bash
POST /auth/logout/
Authorization: Bearer YOUR_ACCESS_TOKEN

{
  "session_key": "YOUR_SESSION_KEY"
}
```

---

## Core Doctypes Endpoints

### 1. List Doctypes
```bash
GET /api/core/doctypes/
Authorization: Bearer YOUR_ACCESS_TOKEN

# Optional query parameters:
# ?status=published
# ?search=inventory
```

### 2. Create Doctype
```bash
POST /api/core/doctypes/
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "name": "Inventory Item",
  "description": "Track inventory items",
  "schema": {
    "fields": [
      {
        "name": "sku",
        "type": "string",
        "required": true,
        "max_length": 64,
        "unique": true
      },
      {
        "name": "title",
        "type": "string",
        "required": true
      },
      {
        "name": "unit_price",
        "type": "decimal",
        "max_digits": 10,
        "decimal_places": 2,
        "default": "0.00"
      }
    ],
    "options": {
      "class_name": "InventoryItem"
    }
  },
  "status": "published"
}
```

**Supported Field Types:**
- `string` - Text with max_length
- `text` - Long text
- `integer` - Whole numbers
- `decimal` - Decimal numbers (requires max_digits and decimal_places)
- `boolean` - True/False
- `date` - Date only
- `datetime` - Date and time
- `json` - JSON object

### 3. Get Doctype Detail
```bash
GET /api/core/doctypes/{id or slug}/
Authorization: Bearer YOUR_ACCESS_TOKEN

# Examples:
# GET /api/core/doctypes/1/
# GET /api/core/doctypes/inventory-item/
```

### 4. Create Dynamic Document
```bash
POST /api/core/doctypes/{id}/records/
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
  "sku": "SKU-12345",
  "title": "Demo Item",
  "unit_price": "19.99"
}
```

### 5. List Dynamic Documents
```bash
GET /api/core/doctypes/{id}/records/
Authorization: Bearer YOUR_ACCESS_TOKEN

# Optional query parameter:
# ?q=Demo  (search in JSON data)
```

---

## Metadata Endpoints

### 1. Get Doctype Schema
```bash
GET /api/core/schema/{slug}/
Authorization: Bearer YOUR_ACCESS_TOKEN

# Example:
GET /api/core/schema/inventory-item/
```

### 2. Search Documents
```bash
GET /api/core/search/{slug}/?q=Demo
Authorization: Bearer YOUR_ACCESS_TOKEN

# Example:
GET /api/core/search/inventory-item/?q=Demo
```

### 3. OpenAPI Schema
```bash
GET /api/core/schema/openapi/
Authorization: Bearer YOUR_ACCESS_TOKEN
```

---

## Complete Example Workflow

### Step 1: Login
```bash
curl -X POST http://localhost:8000/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"spoofman","password":"admin123"}'
```

Save the `access_token` from the response.

### Step 2: Create a Doctype
```bash
curl -X POST http://localhost:8000/api/core/doctypes/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Product",
    "description": "Product catalog",
    "schema": {
      "fields": [
        {"name": "name", "type": "string", "required": true},
        {"name": "price", "type": "decimal", "max_digits": 10, "decimal_places": 2},
        {"name": "in_stock", "type": "boolean"}
      ]
    },
    "status": "published"
  }'
```

Note the `id` from the response.

### Step 3: Create Documents
```bash
curl -X POST http://localhost:8000/api/core/doctypes/1/records/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Laptop","price":"999.99","in_stock":true}'
```

### Step 4: List Documents
```bash
curl http://localhost:8000/api/core/doctypes/1/records/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Using with Frontend

### JavaScript/Fetch Example
```javascript
// Login
const loginResponse = await fetch('http://localhost:8000/auth/login/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'spoofman',
    password: 'admin123'
  })
});

const { access_token } = await loginResponse.json();

// Create doctype
const doctypeResponse = await fetch('http://localhost:8000/api/core/doctypes/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'Blog Post',
    description: 'Blog posts',
    schema: {
      fields: [
        { name: 'title', type: 'string', required: true },
        { name: 'content', type: 'text', required: true },
        { name: 'published', type: 'boolean' }
      ]
    },
    status: 'published'
  })
});

const doctype = await doctypeResponse.json();

// Create document
const documentResponse = await fetch(`http://localhost:8000/api/core/doctypes/${doctype.id}/records/`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access_token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'My First Post',
    content: 'Hello world!',
    published: true
  })
});
```

---

## Admin Panel

Access the Django admin at: http://localhost:8000/admin/

Login with:
- Username: `spoofman`
- Password: `admin123`

You can manage:
- Doctypes
- Documents
- Magic Links
- User Sessions
- Users

---

## Next Steps

1. **Add More Doctypes** - Create schemas for your use case
2. **Build Frontend** - Use React, Vue, or Next.js to consume the API
3. **Deploy** - Use Docker Compose for production deployment
4. **Add Features**:
   - File uploads for documents
   - Relationships between doctypes
   - Webhooks for document changes
   - GraphQL API layer
   - Full-text search with Elasticsearch

## Notes

- All endpoints support CORS from `http://localhost:3000` (configured for frontend)
- JWT tokens expire after 1 hour (access) and 7 days (refresh)
- All data is validated against the doctype schema
- JSON storage allows flexible schema changes without migrations
- API is fully documented in Swagger at `/api/docs/`
