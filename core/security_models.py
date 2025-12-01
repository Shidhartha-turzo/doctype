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
