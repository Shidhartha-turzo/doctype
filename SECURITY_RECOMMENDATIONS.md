# Security Recommendations for Versioning System

## Critical Security Issues

### 1. Add Authentication to APIs

**Current Problem:**
```python
@csrf_exempt  # No authentication!
@require_http_methods(["POST"])
def restore_version(request, document_id, version_number):
    document = get_object_or_404(Document, pk=document_id)
```

**Recommended Fix:**
```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_version(request, document_id, version_number):
    # User is now authenticated
    user = request.user

    # Check document access permission
    document = get_object_or_404(Document, pk=document_id)

    # Verify user has permission to restore
    if not has_permission(user, document, 'write'):
        return JsonResponse({
            'success': False,
            'error': 'Permission denied'
        }, status=403)

    # Proceed with restoration...
```

### 2. Implement Permission Checks

**Create Permission Helper:**
```python
# doctypes/permissions.py

def has_document_permission(user, document, permission_type):
    """
    Check if user has permission on document

    permission_type: 'read', 'write', 'delete'
    """
    if not user.is_authenticated:
        return False

    # Superusers have all permissions
    if user.is_superuser:
        return True

    # Check document creator
    if document.created_by == user:
        return True

    # Check shared permissions
    from .models import DocumentShare
    share = DocumentShare.objects.filter(
        document=document,
        shared_with=user
    ).first()

    if share:
        if permission_type == 'read' and share.permission in ['read', 'write']:
            return True
        if permission_type == 'write' and share.permission == 'write':
            return True

    # Check role-based permissions (if implemented)
    # TODO: Add role-based permission checks

    return False
```

**Apply to All Version APIs:**
```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_versions(request, document_id):
    user = request.user
    document = get_object_or_404(Document, pk=document_id)

    # Check read permission
    if not has_document_permission(user, document, 'read'):
        return JsonResponse({
            'success': False,
            'error': 'You do not have permission to view this document'
        }, status=403)

    # Proceed with listing versions...
```

### 3. Enable CSRF Protection

**Remove @csrf_exempt:**
```python
# Before (INSECURE):
@csrf_exempt
@require_http_methods(["POST"])
def restore_version(request, document_id, version_number):
    pass

# After (SECURE):
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_version(request, document_id, version_number):
    pass  # CSRF handled by DRF
```

**Update Frontend to Include CSRF Token:**
```javascript
// Get CSRF token from cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// Include in fetch requests
fetch('/api/doctypes/documents/123/versions/2/restore/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken
    },
    body: JSON.stringify({ comment: 'Restoring...' })
})
```

### 4. Encrypt Sensitive Version Data

**Option 1: Field-Level Encryption**
```python
from django.conf import settings
from cryptography.fernet import Fernet
import json

class VersionEngine:
    def __init__(self, document):
        self.document = document
        self.cipher = Fernet(settings.VERSION_ENCRYPTION_KEY)

    def create_version(self, user=None, comment=''):
        # Encrypt sensitive fields before storing
        data_snapshot = self.document.data.copy()

        # Define sensitive fields per doctype
        sensitive_fields = self._get_sensitive_fields()

        for field in sensitive_fields:
            if field in data_snapshot:
                # Encrypt the field value
                value = json.dumps(data_snapshot[field])
                encrypted = self.cipher.encrypt(value.encode())
                data_snapshot[f'{field}_encrypted'] = encrypted.decode()
                del data_snapshot[field]

        # Create version with encrypted data
        version = DocumentVersion.objects.create(
            document=self.document,
            version_number=new_version_number,
            data_snapshot=data_snapshot,
            changes=changes,
            changed_by=user,
            comment=comment
        )

        return version

    def _get_sensitive_fields(self):
        """Get list of sensitive fields for this doctype"""
        # Could be stored in doctype configuration
        sensitive_map = {
            'customer': ['credit_card', 'ssn', 'tax_id'],
            'employee': ['salary', 'ssn', 'bank_account'],
            'invoice': ['payment_details']
        }
        return sensitive_map.get(self.document.doctype.slug, [])
```

**Option 2: Full Database Encryption**
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'doctype_db',
        'OPTIONS': {
            'options': '-c encryption=on'
        }
    }
}
```

### 5. Add Audit Logging

**Track All Version Access:**
```python
# doctypes/models.py

class VersionAccessLog(models.Model):
    """Log all version access for security audit"""
    version = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE)
    accessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    access_type = models.CharField(max_length=20, choices=[
        ('view', 'View'),
        ('compare', 'Compare'),
        ('restore', 'Restore'),
        ('download', 'Download')
    ])
    accessed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        db_table = 'version_access_log'
        indexes = [
            models.Index(fields=['version', 'accessed_at']),
            models.Index(fields=['accessed_by', 'accessed_at']),
        ]

# doctypes/version_views.py

def log_version_access(version, user, access_type, request):
    """Log version access for audit trail"""
    from .models import VersionAccessLog

    # Get client IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0]
    else:
        ip_address = request.META.get('REMOTE_ADDR')

    VersionAccessLog.objects.create(
        version=version,
        accessed_by=user,
        access_type=access_type,
        ip_address=ip_address,
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_version(request, document_id, version_number):
    # ... permission checks ...

    version = engine.get_version(int(version_number))

    # Log access
    log_version_access(version, request.user, 'view', request)

    # Return version...
```

### 6. Implement Rate Limiting

**Prevent Abuse:**
```python
# pip install django-ratelimit

from django_ratelimit.decorators import ratelimit

@ratelimit(key='user', rate='10/m', method='POST')
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_version(request, document_id, version_number):
    """
    Limit to 10 restore operations per minute per user
    """
    from django_ratelimit.exceptions import Ratelimited

    if getattr(request, 'limited', False):
        return JsonResponse({
            'success': False,
            'error': 'Rate limit exceeded. Please try again later.'
        }, status=429)

    # Proceed with restoration...
```

### 7. Add Restore Approval Workflow (Optional)

**For Critical Documents:**
```python
class VersionRestoreRequest(models.Model):
    """Require approval for version restoration"""
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    version_to_restore = models.ForeignKey(DocumentVersion, on_delete=models.CASCADE)
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='restore_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()

    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], default='pending')

    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='restore_reviews')
    reviewed_at = models.DateTimeField(null=True)
    review_comment = models.TextField(blank=True)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_version_restore(request, document_id, version_number):
    """Request restoration (requires approval)"""
    document = get_object_or_404(Document, pk=document_id)

    # Check if document requires approval for restoration
    if document.doctype.require_restore_approval:
        restore_request = VersionRestoreRequest.objects.create(
            document=document,
            version_to_restore_id=version_number,
            requested_by=request.user,
            reason=request.data.get('reason', '')
        )

        # Notify approvers
        notify_restore_approvers(restore_request)

        return JsonResponse({
            'success': True,
            'message': 'Restore request submitted for approval',
            'request_id': restore_request.id
        })
    else:
        # Direct restore (existing logic)
        pass
```

### 8. Data Retention Policies

**Auto-Delete Old Versions:**
```python
# doctypes/management/commands/cleanup_old_versions.py

from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from doctypes.engine_models import DocumentVersion

class Command(BaseCommand):
    help = 'Clean up old document versions based on retention policy'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=365,
                          help='Keep versions from last N days')
        parser.add_argument('--keep-monthly', action='store_true',
                          help='Keep one version per month for older data')
        parser.add_argument('--dry-run', action='store_true',
                          help='Show what would be deleted without deleting')

    def handle(self, *args, **options):
        days = options['days']
        cutoff_date = datetime.now() - timedelta(days=days)

        # Always keep first and current versions
        deletable_versions = DocumentVersion.objects.filter(
            changed_at__lt=cutoff_date
        ).exclude(
            version_number=1  # Keep first version
        )

        # For each document, exclude current version
        from doctypes.models import Document
        for doc in Document.objects.all():
            deletable_versions = deletable_versions.exclude(
                document=doc,
                version_number=doc.version_number
            )

        if options['keep_monthly']:
            # Keep one version per month
            # TODO: Implement monthly retention logic
            pass

        count = deletable_versions.count()

        if options['dry_run']:
            self.stdout.write(f'Would delete {count} versions (dry run)')
        else:
            deletable_versions.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {count} old versions'))

# Run periodically via cron:
# 0 2 * * 0 python manage.py cleanup_old_versions --days=365 --keep-monthly
```

### 9. Sanitize Version Comparison Output

**Prevent XSS in Diff Display:**
```python
from django.utils.html import escape

def format_diff_for_display(diff_data):
    """Sanitize diff output to prevent XSS"""
    sanitized = {}

    for key in ['added', 'modified', 'removed']:
        if key in diff_data:
            sanitized[key] = {}
            for field, value in diff_data[key].items():
                # Escape HTML in values
                if isinstance(value, dict):
                    sanitized[key][field] = {
                        k: escape(str(v)) for k, v in value.items()
                    }
                else:
                    sanitized[key][field] = escape(str(value))

    return sanitized
```

### 10. Validate Version Integrity

**Detect Tampering:**
```python
import hashlib
import json

class DocumentVersion(models.Model):
    # ... existing fields ...
    data_hash = models.CharField(max_length=64, blank=True)  # SHA-256 hash

    def save(self, *args, **kwargs):
        # Calculate hash of data snapshot
        if self.data_snapshot:
            data_str = json.dumps(self.data_snapshot, sort_keys=True)
            self.data_hash = hashlib.sha256(data_str.encode()).hexdigest()
        super().save(*args, **kwargs)

    def verify_integrity(self):
        """Verify version data hasn't been tampered with"""
        data_str = json.dumps(self.data_snapshot, sort_keys=True)
        calculated_hash = hashlib.sha256(data_str.encode()).hexdigest()
        return calculated_hash == self.data_hash

# Check integrity before restoration
def restore_version(self, version_number, user=None, comment=''):
    version = self.get_version(version_number)

    if not version.verify_integrity():
        raise ValueError('Version data integrity check failed. Version may have been tampered with.')

    # Proceed with restoration...
```

## Security Checklist

- [ ] Add authentication to all version APIs
- [ ] Implement permission checks (read/write)
- [ ] Enable CSRF protection
- [ ] Add audit logging for version access
- [ ] Implement rate limiting
- [ ] Encrypt sensitive fields in versions
- [ ] Add data retention policies
- [ ] Sanitize diff output for XSS prevention
- [ ] Add version integrity checking
- [ ] Document security requirements
- [ ] Set up monitoring and alerts
- [ ] Regular security audits

## Quick Wins (Implement First)

1. **Authentication** - Add `@permission_classes([IsAuthenticated])`
2. **CSRF** - Remove `@csrf_exempt`
3. **Permission Checks** - Verify user can access document
4. **Audit Logging** - Track who accessed what
5. **Rate Limiting** - Prevent abuse

## Additional Security Measures

### Environment Variables
```python
# settings.py
VERSION_ENCRYPTION_KEY = os.environ.get('VERSION_ENCRYPTION_KEY')
VERSION_RETENTION_DAYS = int(os.environ.get('VERSION_RETENTION_DAYS', 365))
VERSION_REQUIRE_2FA_FOR_RESTORE = os.environ.get('VERSION_REQUIRE_2FA', 'false').lower() == 'true'
```

### Monitoring
```python
# Set up alerts for:
- Multiple restore operations by single user
- Version access outside business hours
- Failed permission checks
- Large number of version comparisons
```

### Compliance
```python
# For GDPR, HIPAA, SOC2:
- Add version data anonymization
- Implement "right to be forgotten"
- Audit trail retention
- Encryption at rest
- Access logs for compliance reporting
```

## Testing Security

```python
# tests/test_version_security.py

def test_unauthenticated_user_cannot_list_versions():
    """Ensure authentication is required"""
    response = client.get('/api/doctypes/documents/1/versions/')
    assert response.status_code == 401

def test_user_cannot_view_other_users_document_versions():
    """Ensure users can only see their own documents"""
    # Create document owned by user1
    doc = create_document(owner=user1)

    # Try to access as user2
    client.force_authenticate(user=user2)
    response = client.get(f'/api/doctypes/documents/{doc.id}/versions/')
    assert response.status_code == 403

def test_restore_requires_write_permission():
    """Ensure write permission required for restore"""
    # Share document with read-only permission
    share_document(doc, user2, permission='read')

    client.force_authenticate(user=user2)
    response = client.post(f'/api/doctypes/documents/{doc.id}/versions/1/restore/')
    assert response.status_code == 403

def test_version_integrity_check():
    """Ensure tampered versions are detected"""
    version = create_version(document)

    # Tamper with data
    version.data_snapshot['tampered'] = True
    version.save(update_fields=['data_snapshot'])

    # Should fail integrity check
    assert not version.verify_integrity()
```

---

**Priority:** HIGH - Implement authentication and permission checks immediately.

**Last Updated:** 2025-12-04
