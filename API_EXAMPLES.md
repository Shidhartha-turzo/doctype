# API Examples

This document contains examples of how to use the Doctype API.

## Base URL

Development: `http://localhost:8000`

## Authentication

### 1. Obtain JWT Token

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "spoofman",
    "password": "admin123"
  }'
```

Response:
```json
{
  "refresh": "eyJ0eXAiOiJKV1...",
  "access": "eyJ0eXAiOiJKV1..."
}
```

### 2. Refresh Access Token

```bash
curl -X POST http://localhost:8000/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "YOUR_REFRESH_TOKEN"
  }'
```

### 3. Verify Token

```bash
curl -X POST http://localhost:8000/api/token/verify/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "YOUR_ACCESS_TOKEN"
  }'
```

## Core API Endpoints

### Health Check (Public)

```bash
curl http://localhost:8000/api/health/
```

Response:
```json
{
  "status": "healthy",
  "message": "API is running"
}
```

### List Users (Authenticated)

```bash
curl http://localhost:8000/api/users/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response:
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "username": "spoofman",
      "email": "admin@example.com",
      "first_name": "",
      "last_name": "",
      "date_joined": "2025-12-01T12:00:00Z"
    }
  ]
}
```

### Get User Detail (Authenticated)

```bash
curl http://localhost:8000/api/users/1/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Response:
```json
{
  "id": 1,
  "username": "spoofman",
  "email": "admin@example.com",
  "first_name": "",
  "last_name": "",
  "date_joined": "2025-12-01T12:00:00Z"
}
```

## Using the Browsable API

You can also interact with the API through your web browser:

1. Go to http://localhost:8000/api/
2. Login at http://localhost:8000/api-auth/login/
3. Browse the API endpoints interactively

## Testing with Python

```python
import requests

# Base URL
BASE_URL = "http://localhost:8000"

# Obtain token
response = requests.post(f"{BASE_URL}/api/token/", json={
    "username": "spoofman",
    "password": "admin123"
})
tokens = response.json()
access_token = tokens['access']

# Make authenticated request
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(f"{BASE_URL}/api/users/", headers=headers)
print(response.json())
```

## Testing with JavaScript/Fetch

```javascript
// Obtain token
const response = await fetch('http://localhost:8000/api/token/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    username: 'spoofman',
    password: 'admin123'
  })
});

const { access } = await response.json();

// Make authenticated request
const usersResponse = await fetch('http://localhost:8000/api/users/', {
  headers: {
    'Authorization': `Bearer ${access}`
  }
});

const users = await usersResponse.json();
console.log(users);
```

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

## Next Steps

1. Create your own models in `core/models.py`
2. Create serializers in `core/serializers.py`
3. Create views in `core/views.py`
4. Add URL patterns in `core/urls.py`
5. Write tests in `core/test_*.py`
