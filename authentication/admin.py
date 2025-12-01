from django.contrib import admin
from .models import MagicLink, UserSession


@admin.register(MagicLink)
class MagicLinkAdmin(admin.ModelAdmin):
    list_display = ['email', 'token', 'created_at', 'expires_at', 'used_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['email', 'token']
    readonly_fields = ['token', 'created_at', 'expires_at', 'used_at']


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'session_key', 'ip_address', 'created_at', 'last_activity', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__username', 'session_key', 'ip_address']
    readonly_fields = ['session_key', 'refresh_token', 'created_at', 'last_activity']
