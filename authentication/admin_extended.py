"""
Admin configuration for extended authentication models
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    User, UserEmailSettings, OnboardingInvitation,
    OAuthProvider, MFADevice, PasswordResetToken
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model"""

    list_display = [
        'email', 'username', 'full_name', 'onboarding_status',
        'signup_source', 'email_verified_badge', 'mfa_enabled_badge',
        'is_staff', 'created_at'
    ]
    list_filter = [
        'onboarding_status', 'signup_source', 'email_verified',
        'is_email_fixed', 'mfa_enabled', 'is_staff', 'is_active'
    ]
    search_fields = ['email', 'username', 'full_name', 'phone']
    ordering = ['-created_at']
    readonly_fields = [
        'created_at', 'updated_at', 'last_login',
        'email_verification_sent_at', 'onboarding_completed_at'
    ]

    fieldsets = (
        ('Identity', {
            'fields': ('email', 'username', 'full_name', 'phone')
        }),
        ('Email Management', {
            'fields': (
                'is_email_fixed', 'email_verified',
                'email_verification_token', 'email_verification_sent_at'
            )
        }),
        ('Onboarding', {
            'fields': (
                'onboarding_status', 'signup_source',
                'onboarding_completed_at'
            )
        }),
        ('Authentication', {
            'fields': ('password', 'mfa_enabled', 'mfa_required')
        }),
        ('OAuth', {
            'fields': ('oauth_provider', 'oauth_uid'),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'groups', 'user_permissions'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_login'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        ('Create User', {
            'classes': ('wide',),
            'fields': (
                'email', 'username', 'full_name', 'phone',
                'password1', 'password2', 'is_staff', 'is_superuser'
            ),
        }),
    )

    def email_verified_badge(self, obj):
        if obj.email_verified:
            return format_html(
                '<span style="color: green;">[YES] Verified</span>'
            )
        return format_html(
            '<span style="color: red;">[NO] Not Verified</span>'
        )
    email_verified_badge.short_description = 'Email Status'

    def mfa_enabled_badge(self, obj):
        if obj.mfa_enabled:
            return format_html(
                '<span style="color: green;">[YES] Enabled</span>'
            )
        return format_html(
            '<span style="color: gray;">[NO] Disabled</span>'
        )
    mfa_enabled_badge.short_description = 'MFA'


@admin.register(UserEmailSettings)
class UserEmailSettingsAdmin(admin.ModelAdmin):
    """Admin interface for UserEmailSettings"""

    list_display = [
        'user', 'notifications_enabled', 'marketing_opt_in',
        'email_bounce_status', 'bounce_count',
        'emails_sent_today', 'last_email_sent_at'
    ]
    list_filter = [
        'notifications_enabled', 'marketing_opt_in',
        'security_alerts_enabled', 'email_bounce_status'
    ]
    search_fields = ['user__email']
    readonly_fields = [
        'bounce_count', 'emails_sent_today', 'last_email_reset',
        'last_email_sent_at', 'last_bounce_at', 'created_at', 'updated_at'
    ]

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Preferences', {
            'fields': (
                'notifications_enabled', 'marketing_opt_in',
                'security_alerts_enabled'
            )
        }),
        ('Delivery Status', {
            'fields': (
                'email_bounce_status', 'bounce_count', 'last_bounce_at'
            )
        }),
        ('Rate Limiting', {
            'fields': (
                'daily_email_limit', 'emails_sent_today',
                'last_email_reset', 'last_email_sent_at'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OnboardingInvitation)
class OnboardingInvitationAdmin(admin.ModelAdmin):
    """Admin interface for OnboardingInvitation"""

    list_display = [
        'id', 'user', 'invited_by', 'status',
        'email_sent', 'expires_at', 'created_at'
    ]
    list_filter = ['status', 'email_sent', 'created_at']
    search_fields = ['user__email', 'invited_by__email', 'invitation_token']
    readonly_fields = [
        'invitation_token', 'invitation_url',
        'email_sent_at', 'accepted_at', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Invitation Details', {
            'fields': (
                'user', 'invited_by', 'status',
                'invitation_token', 'invitation_url'
            )
        }),
        ('Email', {
            'fields': ('email_sent', 'email_sent_at')
        }),
        ('Metadata', {
            'fields': ('role_assigned', 'welcome_message')
        }),
        ('Dates', {
            'fields': ('expires_at', 'accepted_at', 'created_at', 'updated_at')
        }),
    )

    def has_add_permission(self, request):
        # Use the API endpoint to create invitations
        return False


@admin.register(OAuthProvider)
class OAuthProviderAdmin(admin.ModelAdmin):
    """Admin interface for OAuthProvider"""

    list_display = [
        'id', 'user', 'provider', 'provider_email',
        'is_primary', 'is_active', 'last_login_at', 'created_at'
    ]
    list_filter = ['provider', 'is_primary', 'is_active', 'created_at']
    search_fields = [
        'user__email', 'provider_email',
        'provider_username', 'provider_uid'
    ]
    readonly_fields = [
        'provider_uid', 'access_token', 'refresh_token',
        'token_expires_at', 'profile_data',
        'last_login_at', 'created_at', 'updated_at'
    ]

    fieldsets = (
        ('Connection', {
            'fields': ('user', 'provider', 'is_primary', 'is_active')
        }),
        ('Provider Details', {
            'fields': (
                'provider_uid', 'provider_email', 'provider_username'
            )
        }),
        ('OAuth Tokens', {
            'fields': (
                'access_token', 'refresh_token', 'token_expires_at'
            ),
            'classes': ('collapse',)
        }),
        ('Profile Data', {
            'fields': ('profile_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('last_login_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MFADevice)
class MFADeviceAdmin(admin.ModelAdmin):
    """Admin interface for MFADevice"""

    list_display = [
        'id', 'user', 'device_name', 'device_type',
        'is_primary', 'is_verified', 'is_active',
        'use_count', 'last_used_at'
    ]
    list_filter = [
        'device_type', 'is_primary', 'is_verified',
        'is_active', 'created_at'
    ]
    search_fields = ['user__email', 'device_name']
    readonly_fields = [
        'totp_secret', 'backup_codes', 'use_count',
        'failed_attempts', 'last_failed_at',
        'last_used_at', 'created_at', 'updated_at'
    ]

    fieldsets = (
        ('Device Info', {
            'fields': (
                'user', 'device_type', 'device_name',
                'is_primary', 'is_verified', 'is_active'
            )
        }),
        ('TOTP (Authenticator)', {
            'fields': ('totp_secret',),
            'classes': ('collapse',)
        }),
        ('SMS/Email', {
            'fields': ('phone_number', 'email_address'),
            'classes': ('collapse',)
        }),
        ('Backup Codes', {
            'fields': ('backup_codes',),
            'classes': ('collapse',)
        }),
        ('Usage Stats', {
            'fields': (
                'use_count', 'failed_attempts',
                'last_used_at', 'last_failed_at'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    """Admin interface for PasswordResetToken"""

    list_display = [
        'id', 'user', 'is_used', 'created_at', 'expires_at'
    ]
    list_filter = ['is_used', 'created_at']
    search_fields = ['user__email', 'token', 'ip_address']
    readonly_fields = [
        'token', 'ip_address', 'user_agent',
        'created_at', 'expires_at', 'used_at'
    ]

    fieldsets = (
        ('Token', {
            'fields': ('user', 'token', 'is_used')
        }),
        ('Security', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Dates', {
            'fields': ('created_at', 'expires_at', 'used_at')
        }),
    )

    def has_add_permission(self, request):
        # Use the API endpoint to create reset tokens
        return False
