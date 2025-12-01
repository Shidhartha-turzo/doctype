from django.contrib import admin
from .security_models import (
    SystemSettings, LoginAttempt, IPBlacklist, SecurityAuditLog, APIKey
)


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    """Admin interface for System Settings (Single instance)"""

    fieldsets = (
        ('Rate Limiting', {
            'fields': ('enable_rate_limiting', 'rate_limit_requests', 'rate_limit_window',
                      'api_rate_limit_anonymous', 'api_rate_limit_authenticated',
                      'login_rate_limit', 'login_rate_window')
        }),
        ('Brute Force Protection', {
            'fields': ('enable_brute_force_protection', 'max_login_attempts',
                      'account_lockout_duration')
        }),
        ('IP Protection', {
            'fields': ('enable_ip_blacklist', 'ip_blacklist_threshold',
                      'ip_blacklist_duration', 'ip_whitelist',
                      'require_whitelist_for_admin')
        }),
        ('Session Management', {
            'fields': ('session_timeout', 'max_sessions_per_user',
                      'session_refresh_on_activity')
        }),
        ('Password Policy', {
            'fields': ('min_password_length', 'require_uppercase', 'require_lowercase',
                      'require_digit', 'require_special_char', 'password_expiry_days',
                      'prevent_password_reuse')
        }),
        ('Two-Factor Authentication', {
            'fields': ('enable_2fa', 'require_2fa_for_admin')
        }),
        ('CAPTCHA', {
            'fields': ('enable_captcha', 'captcha_after_failed_attempts')
        }),
        ('Security Headers', {
            'fields': ('enable_security_headers', 'hsts_max_age', 'enable_csp')
        }),
        ('Audit Logging', {
            'fields': ('enable_audit_logging', 'log_failed_logins', 'log_successful_logins',
                      'log_api_requests', 'audit_log_retention_days')
        }),
        ('API Security', {
            'fields': ('require_api_key', 'api_key_header_name')
        }),
        ('Metadata', {
            'fields': ('updated_at', 'updated_by')
        }),
    )

    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        """Prevent creating multiple instances"""
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton"""
        return False


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Admin interface for Login Attempts"""
    list_display = ['username', 'ip_address', 'status', 'attempted_at', 'failure_reason']
    list_filter = ['status', 'attempted_at']
    search_fields = ['username', 'ip_address', 'user_agent']
    readonly_fields = ['username', 'ip_address', 'user_agent', 'status', 'failure_reason',
                       'attempted_at', 'country', 'city']
    date_hierarchy = 'attempted_at'

    def has_add_permission(self, request):
        """Prevent manual creation"""
        return False

    def has_change_permission(self, request, obj=None):
        """Make read-only"""
        return False


@admin.register(IPBlacklist)
class IPBlacklistAdmin(admin.ModelAdmin):
    """Admin interface for IP Blacklist"""
    list_display = ['ip_address', 'reason', 'is_permanent', 'is_auto', 'blacklisted_at',
                   'expires_at', 'failed_attempts_count']
    list_filter = ['is_permanent', 'is_auto', 'blacklisted_at']
    search_fields = ['ip_address', 'reason']
    readonly_fields = ['is_auto', 'blacklisted_at', 'failed_attempts_count', 'last_attempt_at']
    date_hierarchy = 'blacklisted_at'

    fieldsets = (
        ('IP Information', {
            'fields': ('ip_address', 'reason')
        }),
        ('Blacklist Type', {
            'fields': ('is_permanent', 'is_auto', 'expires_at')
        }),
        ('Tracking', {
            'fields': ('failed_attempts_count', 'last_attempt_at', 'blacklisted_at')
        }),
        ('Admin', {
            'fields': ('created_by',)
        }),
    )


@admin.register(SecurityAuditLog)
class SecurityAuditLogAdmin(admin.ModelAdmin):
    """Admin interface for Security Audit Log"""
    list_display = ['event_type', 'severity', 'username', 'ip_address', 'created_at', 'description_short']
    list_filter = ['event_type', 'severity', 'created_at']
    search_fields = ['username', 'ip_address', 'description', 'user_agent']
    readonly_fields = ['event_type', 'severity', 'description', 'user', 'username', 'ip_address',
                       'user_agent', 'request_path', 'request_method', 'metadata', 'created_at']
    date_hierarchy = 'created_at'

    def description_short(self, obj):
        """Truncated description for list view"""
        return obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
    description_short.short_description = 'Description'

    def has_add_permission(self, request):
        """Prevent manual creation"""
        return False

    def has_change_permission(self, request, obj=None):
        """Make read-only"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup"""
        return request.user.is_superuser


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """Admin interface for API Keys"""
    list_display = ['name', 'prefix', 'user', 'is_active', 'created_at', 'expires_at',
                   'usage_count', 'last_used_at']
    list_filter = ['is_active', 'created_at', 'expires_at']
    search_fields = ['name', 'prefix', 'user__username']
    readonly_fields = ['key_hash', 'prefix', 'created_at', 'usage_count', 'last_used_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Key Information', {
            'fields': ('name', 'prefix', 'key_hash')
        }),
        ('User & Permissions', {
            'fields': ('user', 'is_active', 'scopes')
        }),
        ('Rate Limiting', {
            'fields': ('custom_rate_limit',)
        }),
        ('Timing', {
            'fields': ('created_at', 'expires_at', 'last_used_at')
        }),
        ('Usage', {
            'fields': ('usage_count',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """Generate API key on creation"""
        if not change:  # New object
            key = APIKey.generate_key()
            obj.key_hash = APIKey.hash_key(key)
            obj.prefix = key[:8]
            # Display the key to admin (only shown once)
            self.message_user(request, f'API Key created: {key} (Save this key, it will not be shown again!)')
        super().save_model(request, obj, form, change)
