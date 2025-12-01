from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import secrets


class MagicLink(models.Model):
    """Magic link for passwordless authentication"""
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"MagicLink for {self.email}"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if the magic link is still valid"""
        return (
            self.is_active
            and not self.used_at
            and timezone.now() < self.expires_at
        )

    def mark_as_used(self):
        """Mark the magic link as used"""
        self.used_at = timezone.now()
        self.is_active = False
        self.save()


class UserSession(models.Model):
    """Track user sessions"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_sessions')
    session_key = models.CharField(max_length=255, unique=True, db_index=True)
    refresh_token = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-last_activity']

    def __str__(self):
        return f"Session for {self.user.username} - {self.session_key[:8]}"

    def save(self, *args, **kwargs):
        if not self.session_key:
            self.session_key = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if the session is still valid"""
        return self.is_active and timezone.now() < self.expires_at

    def deactivate(self):
        """Deactivate the session"""
        self.is_active = False
        self.save()
