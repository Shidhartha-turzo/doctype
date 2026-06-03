# Email & Document Sharing

This guide covers email configuration (SMTP/IMAP) and the document sharing API.

## Email Configuration

### SystemSettings Fields

#### Outgoing Email (SMTP)
- `enable_email` - Master switch for email functionality
- `email_backend` - Email backend type (SMTP/Console/etc.)
- `email_host` - SMTP server hostname (e.g., smtp.gmail.com)
- `email_port` - SMTP port (587 for TLS, 465 for SSL)
- `email_use_tls` - Use TLS encryption
- `email_use_ssl` - Use SSL encryption
- `email_host_user` - SMTP username/email
- `email_host_password` - SMTP password (encrypted storage)
- `email_from_address` - Default "From" email
- `email_from_name` - Default "From" name

#### Incoming Email (IMAP)
- `enable_incoming_email` - Enable incoming email processing
- `imap_host` - IMAP server hostname
- `imap_port` - IMAP port (993 for SSL)
- `imap_use_ssl` - Use SSL for IMAP
- `imap_username` - IMAP username
- `imap_password` - IMAP password (encrypted)

#### Email Features
- `allow_document_sharing` - Allow sharing documents via email
- `email_rate_limit` - Max emails per user per hour (default: 50)

### Setup via Admin Interface

1. Go to: http://127.0.0.1:8000/admin/core/systemsettings/1/change/
2. Scroll to "Email Settings - Outgoing (SMTP)"
3. Check "Enable email"
4. Configure your provider settings (see below)

### Setup via .env File

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_FROM=Your App Name <your-email@gmail.com>
```

---

## Email Provider Configs

### Gmail
```
Host: smtp.gmail.com
Port: 587
TLS: Yes
Note: Requires App Password (not regular password)
```

**Getting a Gmail App Password:**
1. Go to Google Account → Security → 2-Step Verification
2. Scroll to "App passwords"
3. Create new app password
4. Use that password in your SMTP config

### Outlook/Office 365
```
Host: smtp.office365.com
Port: 587
TLS: Yes
```

### SendGrid
```
Host: smtp.sendgrid.net
Port: 587
TLS: Yes
Username: apikey
Password: <your-sendgrid-api-key>
```

### Amazon SES
```
Host: email-smtp.us-east-1.amazonaws.com
Port: 587
TLS: Yes
Username: <IAM-SMTP-username>
Password: <IAM-SMTP-password>
```

---

## Testing Email

### Test SMTP Connection

```python
python manage.py shell

from core.email_service import EmailService
result = EmailService.test_email_connection()
print(result)
```

### Send Test Email

```python
from django.core.mail import send_mail

send_mail(
    'Test Email',
    'This is a test email from Doctype Engine',
    'your-email@gmail.com',
    ['recipient@example.com'],
    fail_silently=False,
)
```

---

## Document Sharing API

### Overview

The Document Sharing API allows users to share documents via email with tracking, rate limiting, and HTML email templates.

**Features:**
- Share documents via email to single or multiple recipients
- HTML email templates with plain text fallback
- Share tracking with status monitoring (sent, delivered, opened, failed)
- Rate limiting based on SystemSettings
- Personal messages with each share
- IP address and user agent tracking
- Admin interface for viewing share history

### DocumentShare Model

Location: `doctypes/models.py`

Fields:
- `document` - ForeignKey to Document
- `shared_by` - User who shared the document
- `recipient_email` - Email address of recipient
- `recipient_name` - Optional recipient name
- `personal_message` - Optional message to include
- `share_url` - URL to view the document
- `status` - sent | delivered | opened | failed
- `sent_at` - Timestamp when email was sent
- `opened_at` - Timestamp when recipient opened
- `ip_address` - IP address of the sharing user
- `user_agent` - Browser/client information

### API Endpoint

**URL**: `POST /api/doctypes/documents/<document_id>/share/`

**Authentication**: Required (JWT or Session)

**Request Body**:
```json
{
  "recipient_emails": ["user1@example.com", "user2@example.com"],
  "personal_message": "Please review this document."
}
```

**Response**:
```json
{
  "message": "Document shared with 2 out of 2 recipients",
  "results": {
    "success_count": 2,
    "failed_count": 0,
    "total": 2,
    "shares": [
      {
        "id": 1,
        "recipient_email": "user1@example.com",
        "status": "sent"
      }
    ]
  }
}
```

**Response Codes**:
- `200 OK` - Document shared successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - Document sharing disabled
- `404 Not Found` - Document not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - All shares failed
- `503 Service Unavailable` - Email disabled

### Email Service

Location: `core/email_service.py`

- `send_document_share_email()` - Send to a single recipient
- `send_bulk_document_share()` - Send to multiple recipients
- `check_rate_limit()` - Verify user hasn't exceeded email limits
- `test_email_connection()` - Test SMTP configuration

### Email Templates

- **HTML**: `doctypes/templates/emails/document_share.html`
- **Text**: `doctypes/templates/emails/document_share.txt`

---

## Usage Examples

### Share via curl

```bash
# Get JWT token first
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"spoofman","password":"admin123!"}' \
  | python -m json.tool | grep access | cut -d'"' -f4)

# Share document
curl -X POST http://localhost:8000/api/doctypes/documents/1/share/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_emails": ["recipient@example.com"],
    "personal_message": "Please review this sales order."
  }' | python -m json.tool
```

### Share via Python

```python
import requests

# Login
response = requests.post('http://localhost:8000/api/auth/login/', json={
    'username': 'spoofman',
    'password': 'admin123!'
})
token = response.json()['access']

# Share document
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}
data = {
    'recipient_emails': ['user@example.com', 'team@example.com'],
    'personal_message': 'Hi team, please review this.'
}
response = requests.post(
    'http://localhost:8000/api/doctypes/documents/1/share/',
    headers=headers,
    json=data
)
print(response.json())
```

### Share via Django Shell

```python
python manage.py shell

from django.contrib.auth.models import User
from doctypes.models import Document
from core.email_service import EmailService

user = User.objects.get(username='spoofman')
document = Document.objects.get(id=1)

success = EmailService.send_document_share_email(
    document=document,
    recipient_email='recipient@example.com',
    sender=user,
    message='Please review this document.',
    share_url='http://localhost:8000/doctypes/sales-order/1/'
)
print(f"Email sent: {success}")
```

---

## Rate Limiting

Rate limiting is enforced per user based on `SystemSettings.email_rate_limit`:

- Default: 50 emails per hour
- Configurable in admin
- Returns HTTP 429 when exceeded

---

## Admin Interface

### View Document Shares

Go to: http://localhost:8000/admin/doctypes/documentshare/

Features:
- View all document shares
- Filter by status, sender, date
- Search by recipient email
- View share timestamps
- Track delivery status

---

## Security Features

1. **Authentication Required** - All share endpoints require authentication
2. **Rate Limiting** - Prevents email spam
3. **IP Tracking** - Logs IP address of sharing user
4. **User Agent Tracking** - Logs browser/client information
5. **Enable/Disable Toggle** - Admins can disable sharing globally

---

## Troubleshooting

### Emails Not Sending

1. **Check SystemSettings** - Ensure "Enable email" is checked and SMTP credentials are correct
2. **Test connection**: `EmailService.test_email_connection()`
3. **Check logs**: `grep -i "email" /tmp/django_server.log`

### Gmail "Less Secure App" Error

Gmail has removed "Less secure app access". You must use App Passwords (see Gmail section above).

### Test SMTP Manually

```python
from django.core.mail import get_connection
connection = get_connection()
connection.open()  # Should not raise an error
connection.close()
```

---

## File Locations

```
doctype/
├── core/
│   ├── email_service.py          # Email service utilities
│   └── security_models.py        # SystemSettings with email config
├── doctypes/
│   ├── models.py                 # DocumentShare model
│   ├── views.py                  # share_document API endpoint
│   ├── serializers.py            # DocumentShareSerializer, BulkShareSerializer
│   ├── urls.py                   # URL routing
│   ├── admin.py                  # Admin interface
│   └── templates/
│       └── emails/
│           ├── document_share.html
│           └── document_share.txt
```

## Important Notes

- **Password Security**: Email passwords are stored in the database. In production, use environment variables or a secrets manager.
- **Rate Limiting**: Default limit is 50 emails per user per hour. Adjust via `email_rate_limit` field.
