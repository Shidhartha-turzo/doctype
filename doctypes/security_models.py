"""
Security and Audit Models

Implements audit trail and security monitoring.
Addresses OWASP A09 (Security Logging and Monitoring Failures).
"""

from django.db import models
from django.conf import settings
from django.utils import timezone


class VersionAccessLog(models.Model):
    """
    Audit log for all document version access

    Tracks who accessed versions, when, and what they did.
    Required for compliance (GDPR, HIPAA, SOC 2).
    """
    version = models.ForeignKey(
        'doctypes.DocumentVersion',
        on_delete=models.CASCADE,
        related_name='access_logs'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='version_accesses'
    )
    action = models.CharField(
        max_length=20,
        choices=[
            ('list', 'List Versions'),
            ('view', 'View Version'),
            ('compare', 'Compare Versions'),
            ('restore', 'Restore Version'),
            ('download', 'Download Version'),
        ],
        db_index=True
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    success = models.BooleanField(default=True, db_index=True)
    error_message = models.TextField(blank=True)

    # Additional context
    request_path = models.CharField(max_length=500, blank=True)
    query_params = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'version_access_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['version', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['success', 'timestamp']),
            models.Index(fields=['ip_address', 'timestamp']),
        ]
        verbose_name = 'Version Access Log'
        verbose_name_plural = 'Version Access Logs'

    def __str__(self):
        user_email = self.user.email if self.user else 'Anonymous'
        return (
            f"{user_email} - {self.action} - "
            f"Version {self.version.version_number} - {self.timestamp}"
        )


class SecurityEvent(models.Model):
    """
    Log security-related events for monitoring

    Captures suspicious activities, failed authentication, etc.
    """
    EVENT_TYPES = [
        ('auth_failed', 'Authentication Failed'),
        ('perm_denied', 'Permission Denied'),
        ('rate_limit', 'Rate Limit Exceeded'),
        ('suspicious', 'Suspicious Activity'),
        ('data_breach', 'Potential Data Breach'),
        ('integrity_fail', 'Data Integrity Check Failed'),
        ('csrf_fail', 'CSRF Validation Failed'),
    ]

    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES,
        db_index=True
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_LEVELS,
        default='medium',
        db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='security_events'
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)

    # Event details
    description = models.TextField()
    resource = models.CharField(max_length=200, blank=True)  # e.g., "document:123"
    action = models.CharField(max_length=100, blank=True)  # e.g., "restore_version"
    additional_data = models.JSONField(default=dict, blank=True)

    # Response
    alerted = models.BooleanField(default=False)
    alert_sent_at = models.DateTimeField(null=True, blank=True)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='resolved_security_events'
    )

    class Meta:
        db_table = 'security_event'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['severity', 'timestamp']),
            models.Index(fields=['resolved', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
        verbose_name = 'Security Event'
        verbose_name_plural = 'Security Events'

    def __str__(self):
        user_email = self.user.email if self.user else 'Anonymous'
        return (
            f"[{self.severity.upper()}] {self.event_type} - "
            f"{user_email} - {self.timestamp}"
        )


class RateLimitLog(models.Model):
    """
    Track rate limiting for actions

    Prevents abuse and DoS attacks.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rate_limit_logs'
    )
    action = models.CharField(max_length=50, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        db_table = 'rate_limit_log'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'action', 'timestamp']),
        ]
        verbose_name = 'Rate Limit Log'
        verbose_name_plural = 'Rate Limit Logs'

    def __str__(self):
        return f"{self.user.email} - {self.action} - {self.timestamp}"

    @classmethod
    def cleanup_old_logs(cls, days=7):
        """Delete logs older than specified days"""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        cls.objects.filter(timestamp__lt=cutoff).delete()


class VersionIntegrityLog(models.Model):
    """
    Log version integrity checks

    Detects tampering with version data.
    """
    version = models.ForeignKey(
        'doctypes.DocumentVersion',
        on_delete=models.CASCADE,
        related_name='integrity_checks'
    )
    checked_at = models.DateTimeField(auto_now_add=True)
    passed = models.BooleanField(db_index=True)
    expected_hash = models.CharField(max_length=64)
    actual_hash = models.CharField(max_length=64)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        db_table = 'version_integrity_log'
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['version', 'checked_at']),
            models.Index(fields=['passed', 'checked_at']),
        ]
        verbose_name = 'Version Integrity Log'
        verbose_name_plural = 'Version Integrity Logs'

    def __str__(self):
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"Version {self.version.version_number} - "
            f"{status} - {self.checked_at}"
        )


class DataRetentionLog(models.Model):
    """
    Track data retention and cleanup operations

    For compliance and audit purposes.
    """
    operation_type = models.CharField(
        max_length=20,
        choices=[
            ('cleanup', 'Cleanup'),
            ('archive', 'Archive'),
            ('delete', 'Delete'),
        ]
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    # Operation details
    resource_type = models.CharField(max_length=50)  # e.g., "DocumentVersion"
    records_affected = models.IntegerField(default=0)
    retention_policy = models.CharField(max_length=200)
    reason = models.TextField(blank=True)

    class Meta:
        db_table = 'data_retention_log'
        ordering = ['-timestamp']
        verbose_name = 'Data Retention Log'
        verbose_name_plural = 'Data Retention Logs'

    def __str__(self):
        return (
            f"{self.operation_type} - {self.resource_type} - "
            f"{self.records_affected} records - {self.timestamp}"
        )
