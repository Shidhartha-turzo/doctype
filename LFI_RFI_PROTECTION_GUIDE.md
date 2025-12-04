# LFI/RFI Protection Guide

## Table of Contents
1. [Overview](#overview)
2. [Current Security Status](#current-security-status)
3. [Attack Vectors](#attack-vectors)
4. [Protection Implementation](#protection-implementation)
5. [Code Examples](#code-examples)
6. [Testing](#testing)
7. [Best Practices](#best-practices)

---

## Overview

### What is LFI (Local File Inclusion)?
LFI attacks occur when an attacker can manipulate file paths to include local files on the server, potentially exposing sensitive data like:
- Configuration files (/etc/passwd, settings.py)
- Application source code
- Log files with sensitive information
- Database credentials

### What is RFI (Remote File Inclusion)?
RFI attacks allow attackers to include remote files from external servers, enabling:
- Remote code execution
- Server compromise
- Malware injection
- Data exfiltration

---

## Current Security Status

### [YES] Built-in Django Protections

Your Django application already has several built-in protections:

1. **Template System Security**
   - Django templates don't execute arbitrary Python code
   - No direct file inclusion via templates
   - Auto-escaping prevents XSS

2. **URL Routing**
   - URL patterns are explicitly defined
   - No dynamic file serving based on user input
   - Static files served from specific directories only

3. **Settings Configuration**
   - DEBUG = False in production (via settings_security.py)
   - ALLOWED_HOSTS restricts request origins
   - MEDIA_ROOT and STATIC_ROOT are controlled

### [WARNING] Potential Vulnerabilities Found

After analyzing your codebase, here are the areas that need attention:

#### 1. File Upload Handling (Medium Risk)
**Location**: `doctypes/models.py` - File field types

**Risk**: If file uploads are not properly validated, attackers could:
- Upload malicious files
- Overwrite existing files
- Execute uploaded scripts

#### 2. Template Rendering (Low Risk)
**Location**: `doctypes/views.py`, `doctypes/admin.py`

**Risk**: If template names come from user input without validation

#### 3. Backup/Restore Operations (High Risk)
**Location**: `core/backup_utils.py`, `core/management/commands/restorebackup.py`

**Risk**: File path manipulation in backup/restore operations

---

## Attack Vectors

### Vector 1: File Upload Exploitation

**Attack Example**:
```python
# VULNERABLE CODE (DO NOT USE)
def upload_file(request):
    filename = request.FILES['file'].name  # Attacker controls this
    path = os.path.join('/uploads/', filename)  # Path traversal possible
    with open(path, 'wb') as f:
        f.write(request.FILES['file'].read())
```

**Exploit**:
```
POST /upload
filename: "../../../etc/cron.d/malicious"
```

### Vector 2: Template Name Injection

**Attack Example**:
```python
# VULNERABLE CODE (DO NOT USE)
def view_template(request):
    template_name = request.GET.get('template')  # Attacker controls this
    return render(request, template_name, {})  # Dangerous!
```

**Exploit**:
```
GET /view?template=../../../../etc/passwd
GET /view?template=settings.py
```

### Vector 3: Backup File Access

**Attack Example**:
```python
# VULNERABLE CODE (DO NOT USE)
def restore_backup(request):
    backup_file = request.POST.get('filename')  # Attacker controls this
    path = f'/backups/{backup_file}'  # Path traversal possible
    with open(path, 'r') as f:
        data = f.read()
```

**Exploit**:
```
POST /restore
filename: "../../settings.py"
```

---

## Protection Implementation

### Step 1: Create File Path Validator

Create `/Users/spoofing/Documents/DT/doctype/core/file_security.py`:

```python
"""
File Security Utilities
Protects against LFI/RFI attacks
"""

import os
import re
from pathlib import Path
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation


class FileSecurityError(Exception):
    """Raised when file operation fails security checks"""
    pass


def validate_file_path(file_path, allowed_base_dirs=None):
    """
    Validate file path to prevent directory traversal attacks

    Args:
        file_path: Path to validate
        allowed_base_dirs: List of allowed base directories

    Returns:
        Absolute validated path

    Raises:
        FileSecurityError: If path is suspicious or outside allowed directories
    """
    # Convert to absolute path
    abs_path = os.path.abspath(file_path)

    # Check for path traversal patterns
    suspicious_patterns = [
        '..',           # Parent directory
        '~',            # Home directory
        '/etc',         # System files
        '/proc',        # Process info
        '/sys',         # System info
        'settings.py',  # Django settings
        '.env',         # Environment variables
        'SECRET',       # Secret keys
    ]

    for pattern in suspicious_patterns:
        if pattern in abs_path:
            raise FileSecurityError(f"Suspicious path pattern detected: {pattern}")

    # If base directories specified, ensure path is within them
    if allowed_base_dirs:
        is_allowed = False
        for base_dir in allowed_base_dirs:
            base_dir = os.path.abspath(base_dir)
            try:
                # Check if path is within base directory
                Path(abs_path).relative_to(base_dir)
                is_allowed = True
                break
            except ValueError:
                continue

        if not is_allowed:
            raise FileSecurityError(
                f"Path {abs_path} is outside allowed directories"
            )

    return abs_path


def validate_filename(filename):
    """
    Validate filename to prevent malicious uploads

    Args:
        filename: Filename to validate

    Returns:
        Sanitized filename

    Raises:
        FileSecurityError: If filename is suspicious
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Check for dangerous patterns
    if filename.startswith('.'):
        raise FileSecurityError("Filenames cannot start with a dot")

    # Check for null bytes
    if '\x00' in filename:
        raise FileSecurityError("Null bytes not allowed in filename")

    # Check for path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        raise FileSecurityError("Path traversal characters not allowed")

    # Allow only safe characters
    safe_pattern = re.compile(r'^[a-zA-Z0-9._-]+$')
    if not safe_pattern.match(filename):
        raise FileSecurityError(
            "Filename contains invalid characters. "
            "Only alphanumeric, dots, hyphens, and underscores allowed"
        )

    # Check file extension
    allowed_extensions = getattr(
        settings,
        'ALLOWED_UPLOAD_EXTENSIONS',
        ['.pdf', '.doc', '.docx', '.txt', '.csv', '.jpg', '.png']
    )

    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        raise FileSecurityError(f"File extension {ext} not allowed")

    return filename


def validate_template_name(template_name):
    """
    Validate template name to prevent template injection

    Args:
        template_name: Template name to validate

    Returns:
        Validated template name

    Raises:
        FileSecurityError: If template name is suspicious
    """
    # Only allow alphanumeric, hyphens, underscores, slashes, and dots
    safe_pattern = re.compile(r'^[a-zA-Z0-9/_.-]+$')
    if not safe_pattern.match(template_name):
        raise FileSecurityError("Invalid template name")

    # Prevent path traversal
    if '..' in template_name:
        raise FileSecurityError("Path traversal not allowed in template names")

    # Must end with .html
    if not template_name.endswith('.html'):
        raise FileSecurityError("Template must be an HTML file")

    # Check against whitelist of allowed templates
    allowed_template_dirs = [
        'doctypes/templates/',
        'authentication/templates/',
        'core/templates/',
    ]

    # Ensure template is in allowed directory
    is_allowed = any(
        template_name.startswith(dir_name)
        for dir_name in allowed_template_dirs
    )

    if not is_allowed:
        raise FileSecurityError("Template not in allowed directory")

    return template_name


def secure_file_open(file_path, mode='r', allowed_base_dirs=None):
    """
    Securely open a file with validation

    Args:
        file_path: Path to file
        mode: File open mode
        allowed_base_dirs: List of allowed base directories

    Returns:
        File handle

    Raises:
        FileSecurityError: If file path fails validation
    """
    # Validate path
    validated_path = validate_file_path(file_path, allowed_base_dirs)

    # Prevent opening sensitive files
    sensitive_files = [
        'settings.py',
        '.env',
        'SECRET_KEY',
        '/etc/passwd',
        '/etc/shadow',
    ]

    for sensitive in sensitive_files:
        if sensitive in validated_path:
            raise FileSecurityError(f"Cannot open sensitive file: {sensitive}")

    # Only allow read modes for now (disable write without explicit permission)
    if 'w' in mode or 'a' in mode:
        raise FileSecurityError("Write mode requires explicit permission")

    try:
        return open(validated_path, mode)
    except PermissionError:
        raise FileSecurityError("Permission denied")
    except FileNotFoundError:
        raise FileSecurityError("File not found")


def sanitize_url(url):
    """
    Validate and sanitize URLs to prevent RFI attacks

    Args:
        url: URL to validate

    Returns:
        Validated URL

    Raises:
        FileSecurityError: If URL is suspicious
    """
    # Block file:// protocol (local file access)
    if url.startswith('file://'):
        raise FileSecurityError("file:// protocol not allowed")

    # Only allow HTTP/HTTPS
    if not url.startswith(('http://', 'https://')):
        raise FileSecurityError("Only HTTP/HTTPS protocols allowed")

    # Block localhost and private IPs (SSRF protection)
    blocked_hosts = [
        'localhost',
        '127.0.0.1',
        '0.0.0.0',
        '10.',      # Private IP range
        '172.16.',  # Private IP range
        '192.168.', # Private IP range
        '169.254.', # Link-local
    ]

    for blocked in blocked_hosts:
        if blocked in url:
            raise FileSecurityError(f"Access to {blocked} not allowed (SSRF protection)")

    return url
```

### Step 2: Secure File Upload Handler

Add to `doctypes/permissions.py`:

```python
from core.file_security import validate_filename, FileSecurityError
from django.core.files.storage import default_storage
import hashlib
import uuid


def handle_secure_file_upload(uploaded_file, upload_dir='uploads'):
    """
    Securely handle file uploads with validation

    Args:
        uploaded_file: Django UploadedFile object
        upload_dir: Target directory for upload

    Returns:
        dict: {
            'filename': sanitized filename,
            'path': storage path,
            'size': file size,
            'hash': SHA-256 hash
        }

    Raises:
        FileSecurityError: If file fails validation
    """
    try:
        # Validate filename
        original_filename = uploaded_file.name
        safe_filename = validate_filename(original_filename)

        # Generate unique filename to prevent overwrites
        unique_id = uuid.uuid4().hex[:8]
        name, ext = os.path.splitext(safe_filename)
        unique_filename = f"{name}_{unique_id}{ext}"

        # Calculate file hash for integrity
        file_hash = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            file_hash.update(chunk)

        # Reset file pointer
        uploaded_file.seek(0)

        # Validate file size
        max_size = getattr(settings, 'FILE_UPLOAD_MAX_MEMORY_SIZE', 10 * 1024 * 1024)
        if uploaded_file.size > max_size:
            raise FileSecurityError(
                f"File size {uploaded_file.size} exceeds maximum {max_size}"
            )

        # Save file using Django storage (automatically handles path security)
        file_path = os.path.join(upload_dir, unique_filename)
        storage_path = default_storage.save(file_path, uploaded_file)

        return {
            'filename': safe_filename,
            'path': storage_path,
            'size': uploaded_file.size,
            'hash': file_hash.hexdigest(),
        }

    except FileSecurityError as e:
        # Log security event
        from .permissions import log_security_event
        log_security_event(
            'suspicious',
            'high',
            None,  # user
            '0.0.0.0',  # ip
            '',  # user_agent
            f"Malicious file upload attempt: {str(e)}",
            resource=f"file:{uploaded_file.name}"
        )
        raise
```

### Step 3: Secure Template Rendering

Add to `doctypes/views.py`:

```python
from core.file_security import validate_template_name, FileSecurityError


def secure_render(request, template_name, context=None):
    """
    Securely render template with validation

    Args:
        request: Django request object
        template_name: Template to render
        context: Template context

    Returns:
        HttpResponse

    Raises:
        FileSecurityError: If template name is invalid
    """
    try:
        # Validate template name
        safe_template = validate_template_name(template_name)

        # Use Django's render (which is already safe)
        return render(request, safe_template, context or {})

    except FileSecurityError as e:
        # Log security event
        log_security_event(
            'suspicious',
            'high',
            request.user if request.user.is_authenticated else None,
            get_client_ip(request),
            request.META.get('HTTP_USER_AGENT', ''),
            f"Template injection attempt: {str(e)}",
            resource=f"template:{template_name}"
        )

        # Return generic error
        return render(request, 'errors/403.html', status=403)
```

### Step 4: Secure Backup Operations

Update `core/backup_utils.py`:

```python
from core.file_security import validate_file_path, FileSecurityError
import os


def get_backup_path(backup_filename):
    """
    Get validated backup file path

    Args:
        backup_filename: Backup filename (NOT full path)

    Returns:
        Validated absolute path

    Raises:
        FileSecurityError: If path is invalid
    """
    # Get backup directory from settings
    backup_dir = getattr(settings, 'BACKUP_DIR', '/var/backups/doctype/')

    # Ensure backup_filename is just a filename, not a path
    if '/' in backup_filename or '\\' in backup_filename:
        raise FileSecurityError("Backup filename cannot contain path separators")

    # Construct full path
    full_path = os.path.join(backup_dir, backup_filename)

    # Validate path
    validated_path = validate_file_path(full_path, allowed_base_dirs=[backup_dir])

    return validated_path


def secure_backup_restore(backup_filename):
    """
    Securely restore from backup

    Args:
        backup_filename: Backup filename to restore

    Returns:
        Success status

    Raises:
        FileSecurityError: If backup file is invalid
    """
    try:
        # Get validated path
        backup_path = get_backup_path(backup_filename)

        # Verify file exists
        if not os.path.exists(backup_path):
            raise FileSecurityError("Backup file does not exist")

        # Verify file is actually a backup (check extension)
        if not backup_path.endswith(('.sql', '.json', '.backup')):
            raise FileSecurityError("Invalid backup file format")

        # Perform restore operation
        # ... (your restore logic here)

        return True

    except FileSecurityError as e:
        # Log security event
        from doctypes.permissions import log_security_event
        log_security_event(
            'suspicious',
            'critical',
            None,  # Should have user context here
            '0.0.0.0',
            '',
            f"Malicious backup access attempt: {str(e)}",
            resource=f"backup:{backup_filename}"
        )
        raise
```

---

## Code Examples

### Example 1: Secure Document View

```python
# In doctypes/views.py

from core.file_security import validate_file_path, FileSecurityError

@login_required
def view_document_attachment(request, document_id, attachment_id):
    """
    Securely serve document attachment
    """
    try:
        # Get document (with permission check)
        document = get_object_or_404(Document, pk=document_id)
        require_document_permission(request.user, document, 'read')

        # Get attachment from database (not from user input!)
        attachment = get_object_or_404(
            DocumentAttachment,
            pk=attachment_id,
            document=document
        )

        # Validate file path
        media_root = settings.MEDIA_ROOT
        file_path = validate_file_path(
            attachment.file.path,
            allowed_base_dirs=[media_root]
        )

        # Serve file securely
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'

        # Log access
        log_version_access(
            attachment,
            request.user,
            'download',
            request
        )

        return response

    except FileSecurityError as e:
        log_security_event(
            'suspicious',
            'high',
            request.user,
            get_client_ip(request),
            request.META.get('HTTP_USER_AGENT', ''),
            f"File inclusion attempt: {str(e)}",
            resource=f"document:{document_id}"
        )
        return HttpResponseForbidden("Access denied")
```

### Example 2: Secure File Upload API

```python
# In doctypes/views.py

from core.file_security import handle_secure_file_upload, FileSecurityError

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@check_rate_limit_decorator('file_upload', limit=20, window_minutes=60)
def upload_document_attachment(request, document_id):
    """
    Securely upload document attachment
    """
    try:
        # Get document with permission check
        document = get_object_or_404(Document, pk=document_id)
        require_document_permission(request.user, document, 'write')

        # Get uploaded file
        if 'file' not in request.FILES:
            return JsonResponse(
                {'error': 'No file provided'},
                status=400
            )

        uploaded_file = request.FILES['file']

        # Securely handle upload
        file_info = handle_secure_file_upload(
            uploaded_file,
            upload_dir=f'documents/{document_id}/attachments'
        )

        # Create attachment record
        attachment = DocumentAttachment.objects.create(
            document=document,
            filename=file_info['filename'],
            file_path=file_info['path'],
            file_size=file_info['size'],
            file_hash=file_info['hash'],
            uploaded_by=request.user
        )

        # Log upload
        log_security_event(
            'file_upload',
            'low',
            request.user,
            get_client_ip(request),
            request.META.get('HTTP_USER_AGENT', ''),
            f"File uploaded successfully",
            resource=f"document:{document_id}",
            additional_data={'attachment_id': attachment.id}
        )

        return JsonResponse({
            'success': True,
            'attachment_id': attachment.id,
            'filename': file_info['filename']
        })

    except FileSecurityError as e:
        return JsonResponse(
            {'error': 'File upload failed security validation'},
            status=400
        )
```

---

## Testing

### Test 1: Path Traversal Attack

```python
# Create test file: tests/test_lfi_protection.py

import pytest
from core.file_security import validate_file_path, FileSecurityError


def test_path_traversal_blocked():
    """Test that path traversal attacks are blocked"""

    malicious_paths = [
        '../../../etc/passwd',
        '..\\..\\..\\windows\\system32\\config\\sam',
        '/etc/shadow',
        '../../settings.py',
        '../.env',
        '~/secret_files/data.txt',
    ]

    for path in malicious_paths:
        with pytest.raises(FileSecurityError):
            validate_file_path(path, allowed_base_dirs=['/var/uploads'])


def test_valid_paths_allowed():
    """Test that legitimate paths are allowed"""

    valid_paths = [
        '/var/uploads/document.pdf',
        '/var/uploads/subdirectory/file.txt',
    ]

    for path in valid_paths:
        # Should not raise exception
        result = validate_file_path(path, allowed_base_dirs=['/var/uploads'])
        assert result is not None


def test_filename_validation():
    """Test filename validation"""
    from core.file_security import validate_filename

    # Malicious filenames
    malicious = [
        '../../../etc/passwd',
        'file\x00.txt',  # Null byte injection
        '.htaccess',      # Hidden file
        'script.php',     # Dangerous extension
    ]

    for filename in malicious:
        with pytest.raises(FileSecurityError):
            validate_filename(filename)

    # Valid filenames
    valid = [
        'document.pdf',
        'report_2025.docx',
        'data-export.csv',
    ]

    for filename in valid:
        result = validate_filename(filename)
        assert result == filename
```

### Test 2: Template Injection Attack

```python
def test_template_injection_blocked():
    """Test that template injection is blocked"""
    from core.file_security import validate_template_name

    malicious_templates = [
        '../../settings.py',
        '../../../etc/passwd',
        'malicious_template',  # No .html extension
        'path/../../injection.html',
    ]

    for template in malicious_templates:
        with pytest.raises(FileSecurityError):
            validate_template_name(template)


def test_valid_templates_allowed():
    """Test that valid templates are allowed"""

    valid_templates = [
        'doctypes/templates/document_list.html',
        'authentication/templates/login.html',
    ]

    for template in valid_templates:
        result = validate_template_name(template)
        assert result == template
```

### Test 3: File Upload Attack

```bash
# Manual penetration test

# Test 1: Path traversal in filename
curl -X POST http://localhost:8000/api/documents/1/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pdf;filename=../../../etc/passwd"
# Expected: 400 Bad Request - Security validation failed

# Test 2: Null byte injection
curl -X POST http://localhost:8000/api/documents/1/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pdf;filename=test%00.php"
# Expected: 400 Bad Request - Invalid filename

# Test 3: Disallowed extension
curl -X POST http://localhost:8000/api/documents/1/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@malware.exe"
# Expected: 400 Bad Request - File extension not allowed

# Test 4: Oversized file
curl -X POST http://localhost:8000/api/documents/1/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@huge_file.zip"
# Expected: 400 Bad Request - File size exceeds maximum
```

---

## Best Practices

### 1. Never Trust User Input

```python
# [NO] NEVER DO THIS
template_name = request.GET.get('template')
return render(request, template_name, {})

# [YES] ALWAYS DO THIS
allowed_templates = ['list.html', 'detail.html', 'form.html']
template_name = request.GET.get('template')
if template_name not in allowed_templates:
    raise SuspiciousOperation("Invalid template")
return render(request, f'doctypes/templates/{template_name}', {})
```

### 2. Use Whitelists, Not Blacklists

```python
# [NO] Blacklist approach (easily bypassed)
if '..' not in filename and '/etc' not in filename:
    open(filename)

# [YES] Whitelist approach
allowed_extensions = ['.pdf', '.doc', '.txt']
ext = os.path.splitext(filename)[1]
if ext in allowed_extensions:
    open(filename)
```

### 3. Validate at Multiple Layers

```python
# Layer 1: Input validation
safe_filename = validate_filename(uploaded_file.name)

# Layer 2: Storage validation
storage_path = default_storage.save(path, uploaded_file)

# Layer 3: Access validation
validated_path = validate_file_path(storage_path, allowed_dirs=[MEDIA_ROOT])

# Layer 4: Permission check
require_document_permission(user, document, 'read')
```

### 4. Use Django's Built-in Security

```python
# [YES] Use Django's FileField (handles security)
class Document(models.Model):
    attachment = models.FileField(upload_to='documents/')

# [YES] Use Django's storage system
from django.core.files.storage import default_storage
path = default_storage.save('uploads/file.pdf', content)

# [YES] Use Django's static file serving (in production)
# settings.py
STATIC_ROOT = '/var/www/static/'
MEDIA_ROOT = '/var/www/media/'
```

### 5. Implement Defense in Depth

- **Filesystem Permissions**: Restrict file permissions (chmod 600/700)
- **Separate Storage**: Store uploads outside web root
- **Integrity Checks**: Verify file hashes
- **Access Logging**: Log all file access
- **Rate Limiting**: Limit upload frequency
- **Malware Scanning**: Scan uploaded files (use ClamAV)

---

## Deployment Checklist

Before deploying to production:

- [ ] All file operations use `validate_file_path()`
- [ ] All uploads use `handle_secure_file_upload()`
- [ ] All template rendering validates template names
- [ ] Backup operations validate file paths
- [ ] File download endpoints check permissions
- [ ] Uploaded files stored outside web root
- [ ] File permissions set correctly (600/700)
- [ ] ALLOWED_UPLOAD_EXTENSIONS configured
- [ ] FILE_UPLOAD_MAX_MEMORY_SIZE set appropriately
- [ ] Security logging enabled for file operations
- [ ] Penetration testing completed
- [ ] Code review completed

---

## Summary

Your Django application has good built-in protection against LFI/RFI, but you should:

1. **Implement** the file security utilities (`core/file_security.py`)
2. **Update** all file operations to use validation functions
3. **Test** thoroughly with the provided test cases
4. **Monitor** security logs for suspicious activity
5. **Review** code regularly for new file operations

[CRITICAL] Priority Actions:
1. Create `core/file_security.py` with validation functions
2. Audit `core/backup_utils.py` for path traversal risks
3. Review any user-controlled file paths
4. Implement security logging for file operations

[SUCCESS] Your existing security implementation (authentication, authorization, input sanitization) provides a strong foundation. Adding LFI/RFI protection completes your defense-in-depth strategy.
