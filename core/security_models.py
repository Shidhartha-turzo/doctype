"""
Security models for the Doctype Engine
Includes: System Settings, Login Attempts, IP Blacklist, Security Audit Log
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
import hashlib


class SystemSettings(models.Model):
    """
    Centralized system security settings (Single doctype - only one record).
    Controls all security features including rate limiting, brute force protection, etc.
    """
    # Rate Limiting Settings
    enable_rate_limiting = models.BooleanField(
        default=True,
        help_text="Enable global rate limiting"
    )
    rate_limit_requests = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        help_text="Number of requests allowed per time window"
    )
    rate_limit_window = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(3600)],
        help_text="Time window in seconds for rate limiting"
    )

    # API-specific rate limits
    api_rate_limit_anonymous = models.IntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Requests per minute for anonymous users"
    )
    api_rate_limit_authenticated = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(5000)],
        help_text="Requests per minute for authenticated users"
    )

    # Login rate limits
    login_rate_limit = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Login attempts allowed per IP per time window"
    )
    login_rate_window = models.IntegerField(
        default=300,
        validators=[MinValueValidator(60), MaxValueValidator(3600)],
        help_text="Time window in seconds for login rate limiting"
    )

    # Brute Force Protection
    enable_brute_force_protection = models.BooleanField(
        default=True,
        help_text="Enable brute force attack protection"
    )
    max_login_attempts = models.IntegerField(
        default=5,
        validators=[MinValueValidator(3), MaxValueValidator(20)],
        help_text="Maximum failed login attempts before account lockout"
    )
    account_lockout_duration = models.IntegerField(
        default=900,
        validators=[MinValueValidator(60), MaxValueValidator(86400)],
        help_text="Account lockout duration in seconds (default 15 minutes)"
    )

    # IP-based protection
    enable_ip_blacklist = models.BooleanField(
        default=True,
        help_text="Enable IP blacklisting for suspicious activity"
    )
    ip_blacklist_threshold = models.IntegerField(
        default=10,
        validators=[MinValueValidator(3), MaxValueValidator(100)],
        help_text="Failed attempts before IP is blacklisted"
    )
    ip_blacklist_duration = models.IntegerField(
        default=3600,
        validators=[MinValueValidator(300), MaxValueValidator(86400)],
        help_text="IP blacklist duration in seconds (default 1 hour)"
    )

    # Session Management
    session_timeout = models.IntegerField(
        default=1800,
        validators=[MinValueValidator(300), MaxValueValidator(86400)],
        help_text="Session timeout in seconds (default 30 minutes)"
    )
    max_sessions_per_user = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        help_text="Maximum concurrent sessions per user"
    )

    # Email Configuration - Outgoing
    enable_email = models.BooleanField(
        default=False,
        help_text="Enable email functionality"
    )
    email_backend = models.CharField(
        max_length=255,
        default='django.core.mail.backends.smtp.EmailBackend',
        help_text="Email backend (SMTP, Console, etc.)"
    )
    email_host = models.CharField(
        max_length=255,
        default='smtp.gmail.com',
        blank=True,
        help_text="SMTP server hostname"
    )
    email_port = models.IntegerField(
        default=587,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text="SMTP server port"
    )
    email_use_tls = models.BooleanField(
        default=True,
        help_text="Use TLS encryption"
    )
    email_use_ssl = models.BooleanField(
        default=False,
        help_text="Use SSL encryption (mutually exclusive with TLS)"
    )
    email_host_user = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP username/email address"
    )
    email_host_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP password (stored encrypted)"
    )
    email_from_address = models.EmailField(
        blank=True,
        help_text="Default 'From' email address"
    )
    email_from_name = models.CharField(
        max_length=255,
        default='Doctype Engine',
        help_text="Default 'From' name"
    )

    # Email Configuration - Incoming (IMAP)
    enable_incoming_email = models.BooleanField(
        default=False,
        help_text="Enable incoming email processing"
    )
    imap_host = models.CharField(
        max_length=255,
        default='imap.gmail.com',
        blank=True,
        help_text="IMAP server hostname"
    )
    imap_port = models.IntegerField(
        default=993,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text="IMAP server port"
    )
    imap_use_ssl = models.BooleanField(
        default=True,
        help_text="Use SSL for IMAP connection"
    )
    imap_username = models.CharField(
        max_length=255,
        blank=True,
        help_text="IMAP username/email address"
    )
    imap_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="IMAP password (stored encrypted)"
    )

    # Email Features
    allow_document_sharing = models.BooleanField(
        default=True,
        help_text="Allow users to share documents via email"
    )
    email_rate_limit = models.IntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(1000)],
        help_text="Maximum emails per user per hour"
    )
    session_refresh_on_activity = models.BooleanField(
        default=True,
        help_text="Refresh session timeout on user activity"
    )

    # Password Policy
    min_password_length = models.IntegerField(
        default=8,
        validators=[MinValueValidator(6), MaxValueValidator(128)],
        help_text="Minimum password length"
    )
    require_uppercase = models.BooleanField(
        default=True,
        help_text="Require at least one uppercase letter"
    )
    require_lowercase = models.BooleanField(
        default=True,
        help_text="Require at least one lowercase letter"
    )
    require_digit = models.BooleanField(
        default=True,
        help_text="Require at least one digit"
    )
    require_special_char = models.BooleanField(
        default=True,
        help_text="Require at least one special character"
    )
    password_expiry_days = models.IntegerField(
        default=90,
        validators=[MinValueValidator(0), MaxValueValidator(365)],
        help_text="Password expiry in days (0 = never expires)"
    )
    prevent_password_reuse = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
        help_text="Number of previous passwords to prevent reuse (0 = disabled)"
    )

    # Two-Factor Authentication
    enable_2fa = models.BooleanField(
        default=False,
        help_text="Enable two-factor authentication"
    )
    require_2fa_for_admin = models.BooleanField(
        default=False,
        help_text="Require 2FA for admin users"
    )

    # CAPTCHA Settings
    enable_captcha = models.BooleanField(
        default=False,
        help_text="Enable CAPTCHA on login"
    )
    captcha_after_failed_attempts = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Show CAPTCHA after N failed attempts"
    )

    # Security Headers
    enable_security_headers = models.BooleanField(
        default=True,
        help_text="Enable security headers (HSTS, CSP, etc.)"
    )
    hsts_max_age = models.IntegerField(
        default=31536000,
        validators=[MinValueValidator(0)],
        help_text="HTTP Strict Transport Security max age in seconds"
    )
    enable_csp = models.BooleanField(
        default=True,
        help_text="Enable Content Security Policy"
    )

    # Audit Logging
    enable_audit_logging = models.BooleanField(
        default=True,
        help_text="Enable comprehensive audit logging"
    )
    log_failed_logins = models.BooleanField(
        default=True,
        help_text="Log all failed login attempts"
    )
    log_successful_logins = models.BooleanField(
        default=True,
        help_text="Log successful logins"
    )
    log_api_requests = models.BooleanField(
        default=False,
        help_text="Log all API requests (may impact performance)"
    )
    audit_log_retention_days = models.IntegerField(
        default=90,
        validators=[MinValueValidator(1), MaxValueValidator(3650)],
        help_text="Days to retain audit logs"
    )

    # IP Whitelist (for admin access)
    ip_whitelist = models.JSONField(
        default=list,
        blank=True,
        help_text="List of whitelisted IP addresses (empty = all allowed)"
    )
    require_whitelist_for_admin = models.BooleanField(
        default=False,
        help_text="Require IP whitelist for admin panel access"
    )

    # API Security
    require_api_key = models.BooleanField(
        default=False,
        help_text="Require API key for all API requests"
    )
    api_key_header_name = models.CharField(
        max_length=100,
        default='X-API-Key',
        help_text="Header name for API key authentication"
    )

    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='system_settings_updates'
    )

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return "System Settings"

    def save(self, *args, **kwargs):
        """Ensure only one instance exists (Single doctype pattern)"""
        self.pk = 1
        super().save(*args, **kwargs)
        # Update Django email settings when saved
        self.configure_email_settings()

    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

    def is_ip_whitelisted(self, ip_address):
        """Check if IP is whitelisted"""
        if not self.ip_whitelist:
            return True  # Empty whitelist means all allowed
        return ip_address in self.ip_whitelist

    def configure_email_settings(self):
        """Configure Django email settings from SystemSettings"""
        from django.conf import settings
        if self.enable_email:
            settings.EMAIL_BACKEND = self.email_backend
            settings.EMAIL_HOST = self.email_host
            settings.EMAIL_PORT = self.email_port
            settings.EMAIL_USE_TLS = self.email_use_tls
            settings.EMAIL_USE_SSL = self.email_use_ssl
            settings.EMAIL_HOST_USER = self.email_host_user
            settings.EMAIL_HOST_PASSWORD = self.email_host_password
            settings.DEFAULT_FROM_EMAIL = f"{self.email_from_name} <{self.email_from_address}>"

    def get_email_config(self):
        """Get email configuration as dict"""
        return {
            'enabled': self.enable_email,
            'backend': self.email_backend,
            'host': self.email_host,
            'port': self.email_port,
            'use_tls': self.email_use_tls,
            'use_ssl': self.email_use_ssl,
            'username': self.email_host_user,
            'from_email': self.email_from_address,
            'from_name': self.email_from_name,
        }


class LoginAttempt(models.Model):
    """
    Track login attempts for brute force protection.
    Records both successful and failed attempts.
    """
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('blocked', 'Blocked'),
    ]

    username = models.CharField(max_length=255, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    failure_reason = models.CharField(max_length=255, blank=True)

    attempted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Geographic data (optional)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-attempted_at']
        indexes = [
            models.Index(fields=['username', '-attempted_at']),
            models.Index(fields=['ip_address', '-attempted_at']),
            models.Index(fields=['status', '-attempted_at']),
        ]

    def __str__(self):
        return f"{self.username} - {self.status} - {self.attempted_at}"

    @classmethod
    def get_recent_failures(cls, username=None, ip_address=None, minutes=15):
        """Get recent failed login attempts"""
        time_threshold = timezone.now() - timedelta(minutes=minutes)
        query = cls.objects.filter(
            status='failed',
            attempted_at__gte=time_threshold
        )

        if username:
            query = query.filter(username=username)
        if ip_address:
            query = query.filter(ip_address=ip_address)

        return query.count()

    @classmethod
    def is_account_locked(cls, username):
        """Check if account is locked due to failed attempts"""
        settings = SystemSettings.get_settings()
        if not settings.enable_brute_force_protection:
            return False

        time_threshold = timezone.now() - timedelta(seconds=settings.account_lockout_duration)
        failed_attempts = cls.objects.filter(
            username=username,
            status='failed',
            attempted_at__gte=time_threshold
        ).count()

        return failed_attempts >= settings.max_login_attempts

    @classmethod
    def record_attempt(cls, username, ip_address, status, user_agent='', failure_reason=''):
        """Record a login attempt"""
        return cls.objects.create(
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            failure_reason=failure_reason
        )


class IPBlacklist(models.Model):
    """
    IP addresses that are temporarily or permanently blacklisted.
    Automatically manages blacklist based on suspicious activity.
    """
    ip_address = models.GenericIPAddressField(unique=True, db_index=True)
    reason = models.CharField(max_length=255)

    # Blacklist type
    is_permanent = models.BooleanField(
        default=False,
        help_text="Permanent blacklist (manual)"
    )
    is_auto = models.BooleanField(
        default=True,
        help_text="Auto-generated from failed attempts"
    )

    # Timing
    blacklisted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When auto-blacklist expires (null = permanent)"
    )

    # Tracking
    failed_attempts_count = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    # Admin info
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Admin who manually blacklisted (if applicable)"
    )

    class Meta:
        ordering = ['-blacklisted_at']
        indexes = [
            models.Index(fields=['ip_address', 'expires_at']),
        ]

    def __str__(self):
        return f"{self.ip_address} - {self.reason}"

    def is_active(self):
        """Check if blacklist is still active"""
        if self.is_permanent:
            return True
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    @classmethod
    def is_blacklisted(cls, ip_address):
        """Check if an IP is currently blacklisted"""
        now = timezone.now()
        return cls.objects.filter(
            ip_address=ip_address
        ).filter(
            models.Q(is_permanent=True) |
            models.Q(expires_at__gt=now)
        ).exists()

    @classmethod
    def auto_blacklist_ip(cls, ip_address, failed_attempts):
        """Automatically blacklist an IP based on failed attempts"""
        settings = SystemSettings.get_settings()

        if not settings.enable_ip_blacklist:
            return None

        if failed_attempts >= settings.ip_blacklist_threshold:
            expires_at = timezone.now() + timedelta(seconds=settings.ip_blacklist_duration)

            blacklist, created = cls.objects.update_or_create(
                ip_address=ip_address,
                defaults={
                    'reason': f'Auto-blacklisted: {failed_attempts} failed login attempts',
                    'is_permanent': False,
                    'is_auto': True,
                    'expires_at': expires_at,
                    'failed_attempts_count': failed_attempts,
                    'last_attempt_at': timezone.now()
                }
            )
            return blacklist
        return None


class SecurityAuditLog(models.Model):
    """
    Comprehensive audit log for security events.
    Tracks all security-relevant actions in the system.
    """
    EVENT_TYPES = [
        ('login_success', 'Login Success'),
        ('login_failed', 'Login Failed'),
        ('logout', 'Logout'),
        ('password_change', 'Password Change'),
        ('password_reset', 'Password Reset'),
        ('account_locked', 'Account Locked'),
        ('account_unlocked', 'Account Unlocked'),
        ('ip_blacklisted', 'IP Blacklisted'),
        ('ip_whitelisted', 'IP Whitelisted'),
        ('permission_denied', 'Permission Denied'),
        ('api_key_created', 'API Key Created'),
        ('api_key_revoked', 'API Key Revoked'),
        ('2fa_enabled', '2FA Enabled'),
        ('2fa_disabled', '2FA Disabled'),
        ('settings_changed', 'Settings Changed'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('data_export', 'Data Export'),
        ('data_import', 'Data Import'),
        ('user_created', 'User Created'),
        ('user_deleted', 'User Deleted'),
        ('role_changed', 'Role Changed'),
    ]

    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    # Event details
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='low', db_index=True)
    description = models.TextField()

    # User & IP
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who triggered the event"
    )
    username = models.CharField(max_length=255, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField(blank=True)

    # Request details
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)

    # Additional data
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event-specific data"
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', '-created_at']),
            models.Index(fields=['severity', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['ip_address', '-created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.username or 'Anonymous'} - {self.created_at}"

    @classmethod
    def log_event(cls, event_type, description, user=None, username='', ip_address='',
                  severity='low', request_path='', request_method='', user_agent='', metadata=None):
        """Create an audit log entry"""
        settings = SystemSettings.get_settings()

        if not settings.enable_audit_logging:
            return None

        # Check specific logging settings
        if event_type == 'login_failed' and not settings.log_failed_logins:
            return None
        if event_type == 'login_success' and not settings.log_successful_logins:
            return None

        return cls.objects.create(
            event_type=event_type,
            severity=severity,
            description=description,
            user=user,
            username=username or (user.username if user else ''),
            ip_address=ip_address or '0.0.0.0',
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            metadata=metadata or {}
        )

    @classmethod
    def cleanup_old_logs(cls):
        """Remove logs older than retention period"""
        settings = SystemSettings.get_settings()
        cutoff_date = timezone.now() - timedelta(days=settings.audit_log_retention_days)
        deleted_count = cls.objects.filter(created_at__lt=cutoff_date).delete()[0]
        return deleted_count


class APIKey(models.Model):
    """
    API keys for secure API access.
    Provides an alternative to JWT for service-to-service communication.
    """
    name = models.CharField(max_length=255, help_text="Descriptive name for this API key")
    key_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="SHA256 hash of the API key"
    )
    prefix = models.CharField(
        max_length=8,
        help_text="First 8 characters of the key (for identification)"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='api_keys',
        help_text="User this API key belongs to"
    )

    # Permissions
    is_active = models.BooleanField(default=True)
    scopes = models.JSONField(
        default=list,
        help_text="List of allowed scopes/permissions"
    )

    # Rate limiting (overrides global settings)
    custom_rate_limit = models.IntegerField(
        null=True,
        blank=True,
        help_text="Custom rate limit for this key (requests per minute)"
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiration date (null = never expires)"
    )
    last_used_at = models.DateTimeField(null=True, blank=True)

    # Tracking
    usage_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    def is_valid(self):
        """Check if API key is valid and not expired"""
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    @classmethod
    def generate_key(cls):
        """Generate a new API key"""
        import secrets
        return secrets.token_urlsafe(32)

    @classmethod
    def hash_key(cls, key):
        """Hash an API key for storage"""
        return hashlib.sha256(key.encode()).hexdigest()

    @classmethod
    def create_key(cls, user, name, scopes=None, expires_at=None):
        """Create a new API key for a user"""
        key = cls.generate_key()
        key_hash = cls.hash_key(key)
        prefix = key[:8]

        api_key = cls.objects.create(
            user=user,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            scopes=scopes or [],
            expires_at=expires_at
        )

        # Log the event
        SecurityAuditLog.log_event(
            event_type='api_key_created',
            description=f'API key "{name}" created',
            user=user,
            severity='medium'
        )

        # Return both the key and the object (key won't be retrievable again)
        return api_key, key

    def record_usage(self):
        """Record API key usage"""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=['usage_count', 'last_used_at'])


class UserLoginHistory(models.Model):
    """
    Tracks all user login attempts and successful logins with IP addresses.
    Essential for security auditing and compliance in production.
    """
    # User information
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='login_history',
        help_text="User who logged in"
    )
    username = models.CharField(
        max_length=150,
        db_index=True,
        help_text="Username (denormalized for faster queries)"
    )

    # Login details
    login_type = models.CharField(
        max_length=20,
        choices=[
            ('password', 'Password'),
            ('magic_link', 'Magic Link'),
            ('api_key', 'API Key'),
            ('jwt_refresh', 'JWT Refresh'),
            ('social', 'Social Login'),
            ('sso', 'Single Sign-On'),
        ],
        default='password',
        help_text="Method used to authenticate"
    )

    success = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether login was successful"
    )

    failure_reason = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Reason for failed login (if applicable)"
    )

    # Network information
    ip_address = models.GenericIPAddressField(
        db_index=True,
        help_text="IP address of the login attempt"
    )

    user_agent = models.TextField(
        blank=True,
        help_text="Browser user agent string"
    )

    device_type = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('bot', 'Bot'),
            ('unknown', 'Unknown'),
        ],
        default='unknown',
        help_text="Type of device used"
    )

    # Geographic information (optional)
    country = models.CharField(
        max_length=2,
        null=True,
        blank=True,
        help_text="Country code (ISO 3166-1 alpha-2)"
    )

    city = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="City name"
    )

    # Session information
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="Django session key"
    )

    # Timing
    login_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp of login attempt"
    )

    logout_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of logout (if applicable)"
    )

    session_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Duration of the session"
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (referrer, etc.)"
    )

    class Meta:
        ordering = ['-login_at']
        indexes = [
            models.Index(fields=['user', '-login_at']),
            models.Index(fields=['ip_address', '-login_at']),
            models.Index(fields=['username', '-login_at']),
            models.Index(fields=['success', '-login_at']),
        ]
        verbose_name = 'User Login History'
        verbose_name_plural = 'User Login Histories'

    def __str__(self):
        status = "Success" if self.success else "Failed"
        return f"{self.username} - {status} - {self.ip_address} - {self.login_at}"

    def calculate_session_duration(self):
        """Calculate and update session duration"""
        if self.logout_at:
            self.session_duration = self.logout_at - self.login_at
            self.save(update_fields=['session_duration'])

    @classmethod
    def log_login(cls, user, request, success=True, failure_reason=None, login_type='password'):
        """
        Log a user login attempt.

        Args:
            user: User object
            request: Django request object
            success: Whether login was successful
            failure_reason: Reason for failure (if applicable)
            login_type: Type of login (password, magic_link, etc.)

        Returns:
            UserLoginHistory object
        """
        from core.security_utils import get_client_ip, parse_user_agent

        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        device_info = parse_user_agent(user_agent)

        login_history = cls.objects.create(
            user=user,
            username=user.username,
            login_type=login_type,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_info.get('device_type', 'unknown'),
            session_key=request.session.session_key if hasattr(request, 'session') else None,
            metadata={
                'referrer': request.META.get('HTTP_REFERER', ''),
                'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
                'browser': device_info.get('browser', ''),
                'os': device_info.get('os', ''),
            }
        )

        # Also log to SecurityAuditLog for critical events
        if success:
            SecurityAuditLog.log_event(
                event_type='login_success',
                description=f'User {user.username} logged in successfully via {login_type}',
                user=user,
                ip_address=ip_address,
                severity='low',
                metadata={'login_type': login_type}
            )
        else:
            SecurityAuditLog.log_event(
                event_type='login_failed',
                description=f'Failed login for {user.username}: {failure_reason}',
                user=user,
                ip_address=ip_address,
                severity='medium',
                metadata={'login_type': login_type, 'reason': failure_reason}
            )

        return login_history

    @classmethod
    def log_logout(cls, user, request):
        """
        Log a user logout.

        Args:
            user: User object
            request: Django request object
        """
        from core.security_utils import get_client_ip

        # Find the most recent active session for this user
        session_key = request.session.session_key if hasattr(request, 'session') else None
        if session_key:
            login_history = cls.objects.filter(
                user=user,
                session_key=session_key,
                logout_at__isnull=True
            ).first()

            if login_history:
                login_history.logout_at = timezone.now()
                login_history.calculate_session_duration()

        # Log to security audit
        SecurityAuditLog.log_event(
            event_type='logout',
            description=f'User {user.username} logged out',
            user=user,
            ip_address=get_client_ip(request),
            severity='low'
        )

    @classmethod
    def get_user_last_login(cls, user):
        """Get user's last successful login information"""
        return cls.objects.filter(
            user=user,
            success=True
        ).first()

    @classmethod
    def get_failed_logins(cls, username=None, ip_address=None, hours=24):
        """Get failed login attempts within specified hours"""
        queryset = cls.objects.filter(
            success=False,
            login_at__gte=timezone.now() - timedelta(hours=hours)
        )

        if username:
            queryset = queryset.filter(username=username)
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)

        return queryset


class ChangeLog(models.Model):
    """
    Tracks major changes to the system for production change management.
    Essential for compliance, debugging, and rollback capabilities.
    """
    # Change information
    change_type = models.CharField(
        max_length=30,
        choices=[
            ('deployment', 'Deployment'),
            ('configuration', 'Configuration Change'),
            ('schema_change', 'Schema Change'),
            ('security_update', 'Security Update'),
            ('feature_added', 'Feature Added'),
            ('feature_removed', 'Feature Removed'),
            ('bug_fix', 'Bug Fix'),
            ('performance', 'Performance Optimization'),
            ('migration', 'Data Migration'),
            ('hotfix', 'Hotfix'),
            ('rollback', 'Rollback'),
            ('maintenance', 'Maintenance'),
            ('other', 'Other'),
        ],
        db_index=True,
        help_text="Type of change"
    )

    title = models.CharField(
        max_length=255,
        help_text="Brief title of the change"
    )

    description = models.TextField(
        help_text="Detailed description of the change"
    )

    # Version information
    version = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Version number (e.g., v1.2.3)"
    )

    # Impact assessment
    impact_level = models.CharField(
        max_length=20,
        choices=[
            ('critical', 'Critical'),
            ('high', 'High'),
            ('medium', 'Medium'),
            ('low', 'Low'),
        ],
        default='medium',
        db_index=True,
        help_text="Impact level of the change"
    )

    affected_systems = models.JSONField(
        default=list,
        help_text="List of affected systems/modules"
    )

    # Change management
    change_request_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Reference to change request/ticket ID"
    )

    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('emergency', 'Emergency (No Approval)'),
        ],
        default='approved',
        help_text="Approval status"
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_changes',
        help_text="User who approved the change"
    )

    # Execution information
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_changes',
        help_text="User who performed the change"
    )

    deployed_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the change was deployed"
    )

    # Rollback information
    can_rollback = models.BooleanField(
        default=False,
        help_text="Whether this change can be rolled back"
    )

    rollback_instructions = models.TextField(
        blank=True,
        help_text="Instructions for rolling back this change"
    )

    rolled_back = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this change has been rolled back"
    )

    rolled_back_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the rollback was performed"
    )

    rolled_back_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rollbacks_performed',
        help_text="User who performed the rollback"
    )

    # Testing and validation
    testing_notes = models.TextField(
        blank=True,
        help_text="Testing performed before deployment"
    )

    validation_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('passed', 'Passed'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),
        ],
        default='passed',
        help_text="Validation status"
    )

    # Documentation
    documentation_url = models.URLField(
        null=True,
        blank=True,
        help_text="Link to detailed documentation"
    )

    jira_ticket = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Jira/ticket reference"
    )

    git_commit = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="Git commit hash"
    )

    git_branch = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Git branch name"
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata about the change"
    )

    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-deployed_at']
        indexes = [
            models.Index(fields=['change_type', '-deployed_at']),
            models.Index(fields=['impact_level', '-deployed_at']),
            models.Index(fields=['rolled_back', '-deployed_at']),
        ]
        verbose_name = 'Change Log'
        verbose_name_plural = 'Change Logs'

    def __str__(self):
        return f"{self.get_change_type_display()} - {self.title} ({self.deployed_at.strftime('%Y-%m-%d')})"

    @classmethod
    def log_change(cls, change_type, title, description, performed_by, **kwargs):
        """
        Log a major system change.

        Args:
            change_type: Type of change
            title: Brief title
            description: Detailed description
            performed_by: User who performed the change
            **kwargs: Additional fields

        Returns:
            ChangeLog object
        """
        change_log = cls.objects.create(
            change_type=change_type,
            title=title,
            description=description,
            performed_by=performed_by,
            **kwargs
        )

        # Also log to SecurityAuditLog for critical changes
        if kwargs.get('impact_level') in ['critical', 'high']:
            SecurityAuditLog.log_event(
                event_type='system_change',
                description=f'{change_type}: {title}',
                user=performed_by,
                severity='high' if kwargs.get('impact_level') == 'critical' else 'medium',
                metadata={
                    'change_type': change_type,
                    'impact_level': kwargs.get('impact_level'),
                    'version': kwargs.get('version'),
                }
            )

        return change_log

    @classmethod
    def get_recent_changes(cls, days=30):
        """Get recent changes within specified days"""
        return cls.objects.filter(
            deployed_at__gte=timezone.now() - timedelta(days=days)
        )

    @classmethod
    def get_critical_changes(cls):
        """Get all critical changes"""
        return cls.objects.filter(impact_level='critical')

    def mark_rollback(self, user, notes=''):
        """Mark this change as rolled back"""
        self.rolled_back = True
        self.rolled_back_at = timezone.now()
        self.rolled_back_by = user
        self.save(update_fields=['rolled_back', 'rolled_back_at', 'rolled_back_by'])

        # Create a rollback change log
        ChangeLog.log_change(
            change_type='rollback',
            title=f'Rollback: {self.title}',
            description=f'Rolled back change from {self.deployed_at}. {notes}',
            performed_by=user,
            impact_level=self.impact_level,
            affected_systems=self.affected_systems,
            metadata={'original_change_id': self.id}
        )
