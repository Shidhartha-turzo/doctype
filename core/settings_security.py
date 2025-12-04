"""
Security-Enhanced Django Settings

IMPORTANT: These settings implement OWASP Top 10 security controls.
Apply these in production by importing in your settings.py:

    from core.settings_security import apply_security_settings
    apply_security_settings(globals())

Or manually copy relevant settings to your production configuration.
"""

import os


def apply_security_settings(settings_dict):
    """
    Apply security settings to Django configuration

    Args:
        settings_dict: Django settings globals() dictionary

    Usage:
        # In settings.py
        from core.settings_security import apply_security_settings
        apply_security_settings(globals())
    """

    # ===================================================================
    # OWASP A05: Security Misconfiguration
    # ===================================================================

    # CRITICAL: Disable debug in production
    settings_dict['DEBUG'] = False

    # Set allowed hosts (must be configured per environment)
    if 'ALLOWED_HOSTS' not in settings_dict or not settings_dict['ALLOWED_HOSTS']:
        settings_dict['ALLOWED_HOSTS'] = os.environ.get('ALLOWED_HOSTS', '').split(',')

    # Strong secret key (must be set via environment variable)
    secret_key = os.environ.get('DJANGO_SECRET_KEY')
    if not secret_key:
        raise ValueError(
            "DJANGO_SECRET_KEY environment variable must be set in production. "
            "Generate one with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )
    settings_dict['SECRET_KEY'] = secret_key

    # Version signing key for integrity checks
    settings_dict['VERSION_SIGNING_KEY'] = os.environ.get(
        'VERSION_SIGNING_KEY',
        secret_key  # Fallback to SECRET_KEY
    )

    # ===================================================================
    # OWASP A05: HTTPS/SSL Configuration
    # ===================================================================

    # Force HTTPS
    settings_dict['SECURE_SSL_REDIRECT'] = True

    # HSTS (HTTP Strict Transport Security)
    settings_dict['SECURE_HSTS_SECONDS'] = 31536000  # 1 year
    settings_dict['SECURE_HSTS_INCLUDE_SUBDOMAINS'] = True
    settings_dict['SECURE_HSTS_PRELOAD'] = True

    # Secure cookies
    settings_dict['SESSION_COOKIE_SECURE'] = True
    settings_dict['CSRF_COOKIE_SECURE'] = True
    settings_dict['SESSION_COOKIE_HTTPONLY'] = True
    settings_dict['CSRF_COOKIE_HTTPONLY'] = True

    # Cookie SameSite policy
    settings_dict['SESSION_COOKIE_SAMESITE'] = 'Lax'
    settings_dict['CSRF_COOKIE_SAMESITE'] = 'Lax'

    # ===================================================================
    # OWASP A05: Security Headers
    # ===================================================================

    # XSS Protection
    settings_dict['SECURE_BROWSER_XSS_FILTER'] = True

    # Content Type Options
    settings_dict['SECURE_CONTENT_TYPE_NOSNIFF'] = True

    # X-Frame-Options
    settings_dict['X_FRAME_OPTIONS'] = 'DENY'

    # Referrer Policy
    settings_dict['SECURE_REFERRER_POLICY'] = 'strict-origin-when-cross-origin'

    # ===================================================================
    # OWASP A05: CORS Configuration
    # ===================================================================

    # Restrictive CORS (configure based on your frontend domains)
    if 'CORS_ALLOWED_ORIGINS' not in settings_dict:
        cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
        if cors_origins:
            settings_dict['CORS_ALLOWED_ORIGINS'] = cors_origins.split(',')
        else:
            settings_dict['CORS_ALLOWED_ORIGINS'] = []

    # Never allow all origins in production
    settings_dict['CORS_ALLOW_ALL_ORIGINS'] = False

    # ===================================================================
    # OWASP A07: Session Security
    # ===================================================================

    # Session timeout (1 hour)
    settings_dict['SESSION_COOKIE_AGE'] = 3600

    # Update session on every request
    settings_dict['SESSION_SAVE_EVERY_REQUEST'] = True

    # Expire session when browser closes
    settings_dict['SESSION_EXPIRE_AT_BROWSER_CLOSE'] = True

    # Session engine
    settings_dict['SESSION_ENGINE'] = 'django.contrib.sessions.backends.db'

    # ===================================================================
    # OWASP A07: Password Security
    # ===================================================================

    # Strong password validation
    settings_dict['AUTH_PASSWORD_VALIDATORS'] = [
        {
            'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        },
        {
            'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
            'OPTIONS': {'min_length': 12}
        },
        {
            'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
        },
        {
            'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
        },
    ]

    # ===================================================================
    # OWASP A09: Security Logging
    # ===================================================================

    # Configure security logging
    if 'LOGGING' not in settings_dict:
        settings_dict['LOGGING'] = {}

    logging_config = settings_dict['LOGGING']

    # Ensure handlers exist
    if 'handlers' not in logging_config:
        logging_config['handlers'] = {}

    # Security log handler
    logging_config['handlers']['security_file'] = {
        'level': 'WARNING',
        'class': 'logging.handlers.RotatingFileHandler',
        'filename': os.path.join(
            os.environ.get('LOG_DIR', '/var/log/django'),
            'security.log'
        ),
        'maxBytes': 1024 * 1024 * 50,  # 50MB
        'backupCount': 10,
        'formatter': 'verbose',
    }

    # Ensure formatters exist
    if 'formatters' not in logging_config:
        logging_config['formatters'] = {}

    logging_config['formatters']['verbose'] = {
        'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
        'style': '{',
    }

    # Ensure loggers exist
    if 'loggers' not in logging_config:
        logging_config['loggers'] = {}

    # Security logger
    logging_config['loggers']['security'] = {
        'handlers': ['security_file'],
        'level': 'WARNING',
        'propagate': False,
    }

    # Django security logger
    logging_config['loggers']['django.security'] = {
        'handlers': ['security_file'],
        'level': 'WARNING',
        'propagate': False,
    }

    # ===================================================================
    # OWASP A04: Rate Limiting
    # ===================================================================

    # Rate limiting configuration
    settings_dict['RATELIMIT_ENABLE'] = True
    settings_dict['RATELIMIT_USE_CACHE'] = 'default'

    # ===================================================================
    # OWASP A02: Data Protection
    # ===================================================================

    # Database encryption (if using encrypted database)
    # Configure based on your database setup

    # ===================================================================
    # Content Security Policy (Advanced)
    # ===================================================================

    # CSP configuration (requires django-csp)
    settings_dict['CSP_DEFAULT_SRC'] = ("'self'",)
    settings_dict['CSP_SCRIPT_SRC'] = ("'self'",)
    settings_dict['CSP_STYLE_SRC'] = ("'self'", "'unsafe-inline'")
    settings_dict['CSP_IMG_SRC'] = ("'self'", "data:", "https:")
    settings_dict['CSP_FONT_SRC'] = ("'self'",)
    settings_dict['CSP_CONNECT_SRC'] = ("'self'",)
    settings_dict['CSP_FRAME_ANCESTORS'] = ("'none'",)
    settings_dict['CSP_BASE_URI'] = ("'self'",)
    settings_dict['CSP_FORM_ACTION'] = ("'self'",)

    # ===================================================================
    # Admin Security
    # ===================================================================

    # Custom admin URL (security through obscurity - helps but not sufficient)
    # Change '/admin/' to something unique
    # settings_dict['ADMIN_URL'] = os.environ.get('ADMIN_URL', 'admin/')

    # ===================================================================
    # File Upload Security
    # ===================================================================

    # Max upload size (10MB)
    settings_dict['FILE_UPLOAD_MAX_MEMORY_SIZE'] = 10 * 1024 * 1024

    # Allowed file extensions
    settings_dict['ALLOWED_UPLOAD_EXTENSIONS'] = [
        '.pdf', '.doc', '.docx', '.xls', '.xlsx',
        '.jpg', '.jpeg', '.png', '.gif',
        '.txt', '.csv', '.zip'
    ]

    # ===================================================================
    # Email Security
    # ===================================================================

    # Use TLS for email
    settings_dict['EMAIL_USE_TLS'] = True

    # Email backend (configure based on your email provider)
    # settings_dict['EMAIL_BACKEND'] = 'django.core.mail.backends.smtp.EmailBackend'
    # settings_dict['EMAIL_HOST'] = os.environ.get('EMAIL_HOST', '')
    # settings_dict['EMAIL_PORT'] = int(os.environ.get('EMAIL_PORT', '587'))
    # settings_dict['EMAIL_HOST_USER'] = os.environ.get('EMAIL_HOST_USER', '')
    # settings_dict['EMAIL_HOST_PASSWORD'] = os.environ.get('EMAIL_HOST_PASSWORD', '')

    print("[SUCCESS] Security settings applied successfully")
    print("[SUCCESS] OWASP Top 10 protections enabled")


# Environment-specific settings

def get_development_overrides():
    """
    Settings overrides for development environment

    WARNING: These settings are INSECURE. Only use in development!
    """
    return {
        'DEBUG': True,
        'SECURE_SSL_REDIRECT': False,
        'SESSION_COOKIE_SECURE': False,
        'CSRF_COOKIE_SECURE': False,
        'SECURE_HSTS_SECONDS': 0,
        'ALLOWED_HOSTS': ['*'],
    }


def get_testing_overrides():
    """
    Settings overrides for testing environment
    """
    return {
        'DEBUG': False,
        'SECURE_SSL_REDIRECT': False,
        'PASSWORD_HASHERS': [
            'django.contrib.auth.hashers.MD5PasswordHasher',  # Fast for tests
        ],
    }


# Security checklist for deployment

SECURITY_CHECKLIST = """
====================================================================
SECURITY DEPLOYMENT CHECKLIST
====================================================================

Before deploying to production, ensure:

[ ] DJANGO_SECRET_KEY is set via environment variable
[ ] VERSION_SIGNING_KEY is set (optional, uses SECRET_KEY by default)
[ ] ALLOWED_HOSTS is properly configured
[ ] DEBUG is False
[ ] HTTPS is enabled on your server
[ ] SSL certificates are valid
[ ] CORS_ALLOWED_ORIGINS is configured for your frontend
[ ] Database backups are configured
[ ] Log directory exists and is writable (/var/log/django/)
[ ] Security logs are monitored
[ ] Rate limiting is tested
[ ] All OWASP fixes are reviewed
[ ] Penetration testing completed
[ ] Security audit passed

====================================================================
ENVIRONMENT VARIABLES REQUIRED
====================================================================

Production:
- DJANGO_SECRET_KEY (required)
- VERSION_SIGNING_KEY (optional)
- ALLOWED_HOSTS (comma-separated)
- CORS_ALLOWED_ORIGINS (comma-separated)
- LOG_DIR (default: /var/log/django)
- EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD

Development:
- DJANGO_ENV=development (to skip security checks)

====================================================================
GENERATE SECRET KEY
====================================================================

python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

====================================================================
"""


def print_security_checklist():
    """Print security checklist"""
    print(SECURITY_CHECKLIST)


# Usage example for settings.py
"""
# In your settings.py:

import os

# Detect environment
ENVIRONMENT = os.environ.get('DJANGO_ENV', 'production')

if ENVIRONMENT == 'production':
    # Apply security settings
    from core.settings_security import apply_security_settings
    apply_security_settings(globals())

elif ENVIRONMENT == 'development':
    # Development settings
    DEBUG = True
    ALLOWED_HOSTS = ['*']
    # ... other dev settings

elif ENVIRONMENT == 'testing':
    # Testing settings
    from core.settings_security import apply_security_settings, get_testing_overrides
    apply_security_settings(globals())
    globals().update(get_testing_overrides())
"""
