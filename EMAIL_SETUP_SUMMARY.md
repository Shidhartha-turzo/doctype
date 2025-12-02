# Email Configuration - Setup Complete ✅

## What Was Added

### 1. SystemSettings - Email Fields

Added comprehensive email configuration to **SystemSettings** model:

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

### 2. Admin Interface

Email settings organized in admin panel with three sections:
1. **Email Settings - Outgoing (SMTP)** - Configure sending emails
2. **Email Settings - Incoming (IMAP)** - Configure receiving emails (collapsed by default)
3. **Email Features** - Control email features and rate limits

Access at: http://127.0.0.1:8000/admin/core/systemsettings/1/change/

### 3. Helper Methods

- `configure_email_settings()` - Automatically updates Django settings when saved
- `get_email_config()` - Returns email configuration as dict

## How to Configure Email

### Option 1: Via Admin Interface

1. Go to: http://127.0.0.1:8000/admin/core/systemsettings/1/change/
2. Scroll to "Email Settings - Outgoing (SMTP)"
3. Check "Enable email"
4. Configure settings:

**Gmail Example:**
```
Enable email: ✓
Email backend: django.core.mail.backends.smtp.EmailBackend
Email host: smtp.gmail.com
Email port: 587
Email use TLS: ✓
Email host user: your-email@gmail.com
Email host password: your-app-password
Email from address: your-email@gmail.com
Email from name: Your App Name
```

**For Gmail, you need an App Password:**
1. Go to Google Account → Security → 2-Step Verification
2. Scroll to "App passwords"
3. Create new app password
4. Use that password (not your regular password)

### Option 2: Via .env File

Add to `.env`:
```bash
# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_FROM=Your App Name <your-email@gmail.com>
```

## Testing Email

### Test Sending Email

```python
python manage.py shell

from django.core.mail import send_mail
from core.security_models import SystemSettings

# Configure from settings
settings = SystemSettings.get_settings()
settings.enable_email = True
settings.email_host = 'smtp.gmail.com'
settings.email_port = 587
settings.email_use_tls = True
settings.email_host_user = 'your-email@gmail.com'
settings.email_host_password = 'your-app-password'
settings.email_from_address = 'your-email@gmail.com'
settings.email_from_name = 'Test App'
settings.save()

# Send test email
send_mail(
    'Test Email',
    'This is a test email from Doctype Engine',
    'your-email@gmail.com',
    ['recipient@example.com'],
    fail_silently=False,
)
```

## Email Providers Configuration

### Gmail
```
Host: smtp.gmail.com
Port: 587
TLS: Yes
Note: Requires App Password
```

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

## Next Steps

### Phase 2: Document Sharing (Upcoming)
- [ ] Create email service utilities
- [ ] Add "Share Document" API endpoint
- [ ] Create email templates
- [ ] Add email tracking
- [ ] Add bulk email functionality

### Phase 3: Incoming Email (Future)
- [ ] Process incoming emails
- [ ] Create documents from email
- [ ] Email-to-document mapping
- [ ] Attachment handling

## Current Status

✅ Email configuration fields added to SystemSettings
✅ Admin interface updated with email settings
✅ Helper methods for email configuration
✅ Database migrations applied
✅ Server running successfully

🔄 Document sharing API (in progress)
⏳ Email templates (pending)
⏳ Email utilities (pending)

## Database

Migrations applied:
- `core.0003_systemsettings_allow_document_sharing_and_more`
  - Added 18 new email-related fields

## Files Modified

1. `core/security_models.py` - Added email fields + methods
2. `core/admin.py` - Updated admin interface
3. `core/migrations/0003_...py` - Database migration
4. `doctype/settings.py` - Temporarily using SQLite

## Important Notes

📝 **Password Security**: Email passwords are stored in the database. In production, use environment variables or a secrets manager.

📝 **Rate Limiting**: Default limit is 50 emails per user per hour. Adjust via `email_rate_limit` field.

📝 **PostgreSQL**: To use PostgreSQL, run `./setup_database_macos.sh` and uncomment PostgreSQL config in settings.py.

---

Ready to configure email! Go to the admin panel to set up your SMTP settings.
