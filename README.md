# Doctype Engine

A production-ready Django REST framework for building dynamic, data-driven applications with comprehensive security features, advanced authentication, and a flexible doctype system inspired by Frappe.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Security](#security)
- [Installation](#installation)
- [API Documentation](#api-documentation)
- [Security Configuration](#security-configuration)
- [Development](#development)
- [Production Deployment](#production-deployment)
- [Testing](#testing)

## Overview

The Doctype Engine is an enterprise-grade framework that combines the flexibility of a dynamic schema system with robust security measures. It provides a complete solution for building secure, scalable applications with minimal boilerplate code.

### Core Capabilities

**Dynamic Schema Management**: Create and modify data structures at runtime without database migrations, using a JSON-based schema system that supports 20+ field types, relationships, hierarchies, and computed fields.

**Enterprise Security**: Built-in protection against common attack vectors including brute force attacks, DDoS, SQL injection, XSS, CSRF, and more. All security features are configurable through a centralized System Settings interface.

**Flexible Authentication**: Multiple authentication methods including JWT tokens, API keys, magic links (passwordless), and session-based auth. Support for two-factor authentication and SSO integration.

**Audit & Compliance**: Comprehensive logging of all security events, login attempts, data modifications, and permission changes. Complete audit trail for compliance requirements.

## Key Features

### Application Framework
- Django 5.2.8 with Django REST Framework 3.15.2
- Dynamic doctype system with module organization
- **Visual Field Builder** - Drag-and-drop interface for schema design (NEW!)
- Slug-based admin URLs for readable doctype access (NEW!)
- JSON-based schema storage (no dynamic table creation)
- 20+ field types including computed fields
- Support for hierarchical data (tree structures)
- Child table relationships (one-to-many)
- Document versioning and change tracking
- Workflow engine with visual designer support
- Event-driven hooks system (Python, webhooks, email)
- Custom fields at runtime without migrations
- Advanced reporting system (Query Builder, SQL, Python)

### Security Features
- **Multi-layered Security Architecture**
  - Rate limiting (global and per-endpoint)
  - Brute force protection with account lockout
  - IP blacklisting and whitelisting
  - Session management with concurrent session limits
  - API key authentication for service-to-service
  - Comprehensive audit logging
  - Security headers (HSTS, CSP, X-Frame-Options, etc.)
  - JSON payload validation
  - Input sanitization

- **Password Security**
  - Configurable password policies
  - Password strength requirements
  - Password expiration
  - Prevention of password reuse
  - Secure password storage (Django's PBKDF2)

- **Access Control**
  - Role-based permissions
  - Conditional permissions (Python expressions)
  - Field-level security
  - Document-level security
  - IP-based access control

### Developer Experience
- OpenAPI/Swagger documentation with drf-spectacular
- Environment-based configuration with python-decouple
- Docker and Docker Compose support
- PostgreSQL ready (SQLite for development)
- Pre-commit hooks for code quality
- Comprehensive test suite with pytest
- CORS support for frontend integration
- WhiteNoise for efficient static file serving

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                          │
│  (Web App, Mobile App, Third-party Services)                │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                   Security Middleware                        │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │IP Black- │Brute     │Rate      │API Key   │Security  │  │
│  │list      │Force     │Limiting  │Auth      │Headers   │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                    API Layer (DRF)                           │
│  ┌────────────────┬────────────────┬──────────────────────┐ │
│  │ Authentication │ Doctypes API   │ Module Management    │ │
│  └────────────────┴────────────────┴──────────────────────┘ │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                  Business Logic Layer                        │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ Workflow │ Hooks    │ Perms    │ Naming   │ Versions │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                    Data Layer (ORM)                          │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ Modules  │ Doctypes │Documents │ Security │ Audit    │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│               Database (PostgreSQL/SQLite)                   │
└─────────────────────────────────────────────────────────────┘
```

### Data Model Hierarchy

```
Module (e.g., CRM, HR, Accounting)
  └── Doctype (e.g., Customer, Employee, Invoice)
      ├── Fields (schema definition)
      ├── Permissions (role-based access)
      ├── Workflows (state machines)
      ├── Hooks (event handlers)
      ├── Naming Series (auto-numbering)
      └── Documents (actual data records)
```

## Security

### Security Philosophy

This framework follows the principle of defense in depth, implementing multiple layers of security controls. Security features are enabled by default and can be configured through the System Settings interface in the admin panel.

### Attack Vector Protection

#### 1. Brute Force Protection

**Threat**: Automated credential stuffing and password guessing attacks.

**Mitigation**:
- Account lockout after N failed attempts (configurable, default: 5)
- Temporary account lockout duration (configurable, default: 15 minutes)
- IP-based rate limiting for login endpoints
- Automatic IP blacklisting for persistent attackers
- Failed login attempt tracking and logging
- CAPTCHA support after threshold violations

**Implementation**:
- `LoginAttempt` model tracks all authentication attempts
- `BruteForceProtectionMiddleware` intercepts login requests
- `check_brute_force()` utility validates attempt patterns
- Exponential backoff can be configured for repeat offenders

**Configuration** (System Settings):
```python
enable_brute_force_protection = True
max_login_attempts = 5
account_lockout_duration = 900  # seconds (15 minutes)
```

#### 2. DDoS and Rate Limiting

**Threat**: Denial of service through resource exhaustion.

**Mitigation**:
- Global rate limiting on all API endpoints
- Separate limits for authenticated vs anonymous users
- Per-endpoint rate limiting support
- Distributed rate limiting ready (Redis integration)
- Custom rate limits per API key
- Request throttling with retry-after headers

**Implementation**:
- `RateLimitMiddleware` enforces global limits
- Cache-based request counting (local memory or Redis)
- `check_rate_limit()` utility for custom enforcement
- `@rate_limit_decorator` for view-level control

**Configuration** (System Settings):
```python
enable_rate_limiting = True
api_rate_limit_anonymous = 20      # requests per minute
api_rate_limit_authenticated = 100  # requests per minute
rate_limit_requests = 100
rate_limit_window = 60  # seconds
```

#### 3. IP-Based Attacks

**Threat**: Attacks originating from malicious IP addresses.

**Mitigation**:
- Dynamic IP blacklisting based on suspicious activity
- Manual IP blacklist management
- IP whitelist for admin access (optional)
- Automatic blacklist expiration
- Geographic IP tracking (optional with GeoIP)
- Proxy and VPN detection capability

**Implementation**:
- `IPBlacklist` model with auto-expiration
- `IPBlacklistMiddleware` blocks requests early
- `IPWhitelistMiddleware` restricts admin access
- `auto_blacklist_ip()` utility for automated blocking

**Configuration** (System Settings):
```python
enable_ip_blacklist = True
ip_blacklist_threshold = 10  # failed attempts
ip_blacklist_duration = 3600  # seconds (1 hour)
ip_whitelist = []  # empty = all allowed
require_whitelist_for_admin = False
```

#### 4. Injection Attacks (SQL, XSS, Command)

**Threat**: Injection of malicious code through user inputs.

**Mitigation**:
- Django ORM prevents SQL injection by default
- Input sanitization on all user-provided data
- JSON schema validation with depth and size limits
- Content Security Policy headers
- X-XSS-Protection headers
- HTML escaping in templates
- Parameterized queries enforcement

**Implementation**:
- `sanitize_input()` utility function
- `validate_json_schema()` prevents deeply nested objects
- `SecureJSONMiddleware` validates all JSON payloads
- Django's template auto-escaping enabled

**Configuration**:
```python
# Automatic - no configuration needed
# JSON validation: max_depth=10, max_keys=1000
```

#### 5. Session Hijacking

**Threat**: Unauthorized access through stolen session tokens.

**Mitigation**:
- Secure session cookies (HTTPOnly, Secure flags)
- Session timeout and inactivity detection
- Maximum concurrent sessions per user
- Session refresh on activity (optional)
- IP and user-agent binding
- JWT token rotation
- Refresh token blacklisting

**Implementation**:
- `UserSession` model tracks all active sessions
- JWT with short-lived access tokens (1 hour)
- Refresh tokens with rotation
- Session deactivation on logout
- Automatic session cleanup

**Configuration** (System Settings):
```python
session_timeout = 1800  # 30 minutes
max_sessions_per_user = 5
session_refresh_on_activity = True
```

#### 6. Cross-Site Request Forgery (CSRF)

**Threat**: Unauthorized actions performed on behalf of authenticated users.

**Mitigation**:
- Django CSRF middleware enabled
- CSRF tokens on all state-changing operations
- SameSite cookie attribute
- Origin and Referer header validation
- Custom CSRF token rotation

**Implementation**:
- Django's built-in CSRF protection
- `CsrfViewMiddleware` active by default
- API endpoints can use JWT (CSRF-exempt)

**Configuration**:
```python
CSRF_COOKIE_SECURE = True  # in production
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'
```

#### 7. Man-in-the-Middle (MITM)

**Threat**: Interception of communication between client and server.

**Mitigation**:
- Enforce HTTPS in production
- HTTP Strict Transport Security (HSTS)
- HSTS preloading
- Secure cookie transmission only
- Certificate pinning support
- TLS 1.2+ enforcement

**Implementation**:
- `SecurityHeadersMiddleware` adds HSTS headers
- Automatic HTTPS redirect in production
- Secure flag on all cookies

**Configuration** (System Settings):
```python
enable_security_headers = True
hsts_max_age = 31536000  # 1 year
SECURE_SSL_REDIRECT = True  # production only
```

### Security Headers

All responses include comprehensive security headers:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

### Audit Logging

**Purpose**: Compliance, forensics, incident response, security monitoring.

**Events Logged**:
- Login success/failure
- Logout
- Password changes
- Account lockouts
- IP blacklist/whitelist modifications
- Permission denied events
- API key creation/revocation
- 2FA enable/disable
- System settings changes
- Data export/import
- User creation/deletion
- Role changes
- Suspicious activity

**Implementation**:
- `SecurityAuditLog` model with indexed fields
- Automatic log rotation based on retention period
- Severity levels (low, medium, high, critical)
- Metadata storage for event context
- IP address and user agent tracking

**Configuration** (System Settings):
```python
enable_audit_logging = True
log_failed_logins = True
log_successful_logins = True
log_api_requests = False  # can impact performance
audit_log_retention_days = 90
```

### Password Policy

**Configurable Requirements**:
- Minimum length (default: 8 characters)
- Uppercase letter requirement
- Lowercase letter requirement
- Digit requirement
- Special character requirement
- Password expiration (default: 90 days)
- Password reuse prevention (default: last 5)

**Implementation**:
- `validate_password_strength()` utility function
- Integrated with Django's authentication system
- Password history tracking (future enhancement)

**Configuration** (System Settings):
```python
min_password_length = 8
require_uppercase = True
require_lowercase = True
require_digit = True
require_special_char = True
password_expiry_days = 90
prevent_password_reuse = 5
```

### API Key Management

**Purpose**: Service-to-service authentication, webhook callbacks, CLI tools.

**Features**:
- Cryptographically secure key generation
- SHA256 hashed storage (keys never stored in plain text)
- Prefix for identification (keys never shown after creation)
- Scope-based permissions
- Expiration dates
- Usage tracking
- Custom rate limits per key
- Revocation and regeneration

**Implementation**:
- `APIKey` model with secure key handling
- `APIKeyMiddleware` for authentication
- `verify_api_key()` utility function
- Admin interface with one-time key display

**Usage**:
```bash
curl -H "X-API-Key: YOUR_API_KEY" https://api.example.com/endpoint
```

## Installation

### Prerequisites

- Python 3.10+
- PostgreSQL 12+ (recommended for production)
- Redis (optional, for distributed caching and rate limiting)
- Git

### Local Development Setup

1. **Clone and Navigate**:
```bash
git clone https://github.com/yourusername/doctype.git
cd doctype
```

2. **Create Virtual Environment**:
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3. **Install Dependencies**:
```bash
pip install -r requirements.txt
# For development tools
pip install -r requirements-dev.txt
```

4. **Environment Configuration**:
```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:
```bash
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3  # or PostgreSQL URL
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

5. **Database Setup**:
```bash
python manage.py migrate
python manage.py createsuperuser
```

6. **Create Initial System Settings**:
```bash
python manage.py shell
>>> from core.security_models import SystemSettings
>>> SystemSettings.get_settings()  # Creates default settings
>>> exit()
```

7. **Start Development Server**:
```bash
python manage.py runserver
```

Access points:
- API: http://127.0.0.1:8000/api/
- Admin: http://127.0.0.1:8000/admin/
- Swagger: http://127.0.0.1:8000/api/docs/
- OpenAPI Schema: http://127.0.0.1:8000/api/schema/

### Docker Setup

1. **Build and Start**:
```bash
docker-compose up --build
```

2. **Run Migrations** (separate terminal):
```bash
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

3. **Access Application**:
- Application: http://127.0.0.1:8000

## API Documentation

### Authentication Endpoints

#### Login (Username/Password)
```http
POST /auth/login/
Content-Type: application/json

{
  "username": "admin",
  "password": "secure_password"
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "session_key": "abc123...",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  }
}
```

#### Magic Link (Passwordless)
```http
POST /auth/magic-link/request/
Content-Type: application/json

{
  "email": "user@example.com"
}

Response:
{
  "message": "Magic link sent to your email",
  "dev_token": "abc123..."  # Only in DEBUG mode
}
```

#### Refresh Token
```http
POST /auth/refresh/
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

#### Logout
```http
POST /auth/logout/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "session_key": "abc123..."
}

Response: 204 No Content
```

### Module Management

#### Create Module
```http
POST /api/modules/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "CRM",
  "icon": "users",
  "color": "#3498db",
  "description": "Customer Relationship Management"
}
```

#### List Modules
```http
GET /api/modules/
Authorization: Bearer <access_token>
```

### Doctype Management

#### Create Doctype
```http
POST /api/core/doctypes/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "Customer",
  "module_id": 1,
  "is_submittable": false,
  "naming_rule": "CUST-{####}",
  "schema": {
    "fields": [
      {
        "name": "customer_name",
        "type": "string",
        "required": true,
        "label": "Customer Name"
      },
      {
        "name": "email",
        "type": "email",
        "required": true,
        "label": "Email Address"
      },
      {
        "name": "phone",
        "type": "phone",
        "label": "Phone Number"
      },
      {
        "name": "status",
        "type": "select",
        "options": ["Active", "Inactive"],
        "default": "Active"
      }
    ]
  }
}
```

#### Create Document
```http
POST /api/core/doctypes/{doctype_id}/records/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "customer_name": "Acme Corporation",
  "email": "contact@acme.com",
  "phone": "+1-555-0123",
  "status": "Active"
}
```

### Security Endpoints

For detailed API documentation, visit `/api/docs/` (Swagger UI) when the server is running.

## Security Configuration

### System Settings Interface

Access the System Settings through the Django admin panel at `/admin/core/systemsettings/`.

All security features are controlled through a single, centralized interface organized into logical sections:

1. **Rate Limiting**: Configure global and endpoint-specific rate limits
2. **Brute Force Protection**: Set account lockout thresholds and durations
3. **IP Protection**: Manage blacklists, whitelists, and auto-blocking
4. **Session Management**: Control session behavior and limits
5. **Password Policy**: Define password requirements and expiration
6. **Two-Factor Authentication**: Enable and configure 2FA
7. **CAPTCHA**: Configure CAPTCHA triggers
8. **Security Headers**: Manage HTTP security headers
9. **Audit Logging**: Control what gets logged and retention periods
10. **API Security**: Configure API key requirements

### Security Best Practices

#### For Development

1. **Use DEBUG=True**: Enables detailed error messages
2. **Use SQLite**: Simple, file-based database
3. **Disable strict security headers**: Allows easier local testing
4. **Enable audit logging**: Learn how events are tracked
5. **Test with different security levels**: Understand the impact

#### For Production

1. **Set DEBUG=False**: Prevents information leakage
2. **Use PostgreSQL**: Production-grade database
3. **Enable all security middleware**: Defense in depth
4. **Configure Redis for caching**: Distributed rate limiting
5. **Set strong SECRET_KEY**: Use cryptographically secure random string
6. **Enable HTTPS**: Use SSL/TLS certificates
7. **Configure ALLOWED_HOSTS**: Restrict to known domains
8. **Set up monitoring**: Track security events
9. **Regular backups**: Include audit logs
10. **Update dependencies**: Patch security vulnerabilities

### Hardening Checklist

- [ ] Change default SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Configure ALLOWED_HOSTS
- [ ] Enable HTTPS/SSL
- [ ] Set SECURE_SSL_REDIRECT=True
- [ ] Configure HSTS headers
- [ ] Enable CSP headers
- [ ] Set up IP whitelist for admin
- [ ] Configure rate limiting
- [ ] Enable brute force protection
- [ ] Set strong password policy
- [ ] Enable audit logging
- [ ] Configure log retention
- [ ] Set up automated cleanup tasks
- [ ] Review and limit CORS origins
- [ ] Disable unnecessary endpoints
- [ ] Configure session timeouts
- [ ] Enable 2FA for admins
- [ ] Set up intrusion detection
- [ ] Configure backups
- [ ] Set up monitoring and alerts

## Development

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov

# Specific app
pytest core/ -v

# Specific test file
pytest core/tests/test_security.py -v

# Generate HTML coverage report
pytest --cov --cov-report=html
```

### Code Quality

```bash
# Install pre-commit hooks
pre-commit install

# Run on all files
pre-commit run --all-files

# Individual tools
black .
isort .
flake8
```

### Database Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migrations
python manage.py showmigrations

# Reverse migration
python manage.py migrate app_name migration_name
```

### Cleanup Tasks

Set up periodic cleanup using cron or Celery:

```python
from core.security_utils import cleanup_expired_data

# Run daily
results = cleanup_expired_data()
print(f"Cleaned up: {results}")
```

## Production Deployment

### Environment Setup

1. **Set Production Environment Variables**:
```bash
DEBUG=False
SECRET_KEY=<strong-random-key>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:pass@host:5432/dbname
CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

2. **Database Configuration**:
```python
# Use PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='5432'),
    }
}
```

3. **Cache Configuration (Redis)**:
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### Web Server Setup (Gunicorn + Nginx)

1. **Install Gunicorn**:
```bash
pip install gunicorn
```

2. **Run with Gunicorn**:
```bash
gunicorn doctype.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

3. **Nginx Configuration**:
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/staticfiles/;
    }

    location /media/ {
        alias /path/to/media/;
    }
}
```

### Monitoring and Logging

1. **Sentry Integration** (already configured):
```python
# In settings.py, Sentry SDK is configured
import sentry_sdk
sentry_sdk.init(dsn="your-sentry-dsn")
```

2. **System Health Monitoring**:
- Monitor login failure rates
- Track API response times
- Monitor rate limit violations
- Alert on IP blacklist additions
- Track audit log growth

### Backup Strategy

1. **Database Backups**:
```bash
# PostgreSQL backup
pg_dump dbname > backup_$(date +%Y%m%d).sql

# Automated with cron
0 2 * * * pg_dump dbname > /backups/db_$(date +\%Y\%m\%d).sql
```

2. **Media Files**:
```bash
# Sync to S3 or similar
aws s3 sync /path/to/media s3://your-bucket/media/
```

## Testing

### Security Testing

The framework includes comprehensive security tests:

```bash
# Test brute force protection
pytest core/tests/test_security.py::test_brute_force_protection

# Test rate limiting
pytest core/tests/test_security.py::test_rate_limiting

# Test IP blacklisting
pytest core/tests/test_security.py::test_ip_blacklist

# Test audit logging
pytest core/tests/test_security.py::test_audit_logging
```

### Load Testing

Use tools like Apache Bench or Locust:

```bash
# Apache Bench
ab -n 1000 -c 10 http://localhost:8000/api/endpoint/

# Locust
locust -f locustfile.py --host=http://localhost:8000
```

## Additional Documentation

### Core Documentation
- [ENGINE_GUIDE.md](ENGINE_GUIDE.md) - Complete guide to the doctype engine
- [API_GUIDE.md](API_GUIDE.md) - Detailed API documentation
- [API_EXAMPLES.md](API_EXAMPLES.md) - API usage examples

### Getting Started
- [QUICKSTART_10MIN.md](QUICKSTART_10MIN.md) - Build your first app in 10 minutes
- [REAL_WORLD_APPLICATIONS.md](REAL_WORLD_APPLICATIONS.md) - 6 complete use case examples

### Feature Guides
- [VISUAL_FIELD_BUILDER.md](VISUAL_FIELD_BUILDER.md) - Drag-and-drop schema designer guide
- [SECURITY_SUMMARY.md](SECURITY_SUMMARY.md) - Quick security reference
- [PRODUCTION_LOGGING.md](PRODUCTION_LOGGING.md) - Production logging & change management guide

### Project Information
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Complete project overview and status

## Support and Contributing

For issues, questions, or contributions:

1. Check existing documentation
2. Search GitHub issues
3. Create a new issue with detailed information
4. Follow the contribution guidelines
5. Submit pull requests with tests

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Security Disclosure

If you discover a security vulnerability, please email security@example.com. Do not create public GitHub issues for security vulnerabilities.

## Acknowledgments

Inspired by Frappe Framework but built with modern Python practices and enhanced security features. Thanks to the Django and Django REST Framework communities for excellent tooling.
