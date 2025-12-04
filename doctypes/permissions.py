"""
Document Permission System

Implements granular permission checking for document access control.
Addresses OWASP A01 (Broken Access Control) and A07 (Authentication Failures).
"""

import logging
from typing import Optional
from django.contrib.auth.models import User
from .models import Document, DocumentShare

logger = logging.getLogger(__name__)


class PermissionDenied(Exception):
    """Raised when user doesn't have required permission"""
    pass


def has_document_permission(user: Optional[User], document: Document,
                           permission_type: str) -> bool:
    """
    Check if user has specific permission on document

    Args:
        user: User instance (None for unauthenticated)
        document: Document instance
        permission_type: 'read', 'write', or 'delete'

    Returns:
        bool: True if user has permission, False otherwise

    Security:
        - Unauthenticated users have no permissions
        - Superusers have all permissions
        - Document creator has all permissions
        - Shared users have permissions based on share settings
    """
    # Unauthenticated users have no access
    if not user or not user.is_authenticated:
        logger.warning(f"Permission check failed: Unauthenticated user")
        return False

    # Superusers have all permissions
    if user.is_superuser:
        return True

    # Document creator has all permissions
    if document.created_by == user:
        return True

    # Check shared permissions
    try:
        share = DocumentShare.objects.filter(
            document=document,
            shared_with=user
        ).first()

        if share:
            # Map permission types
            if permission_type == 'read':
                return share.permission in ['read', 'write']
            elif permission_type == 'write':
                return share.permission == 'write'
            elif permission_type == 'delete':
                # Only creator can delete
                return False

            logger.warning(
                f"Invalid permission type: {permission_type}"
            )
            return False

    except Exception as e:
        logger.error(f"Error checking document share: {str(e)}")
        return False

    # Default: no permission
    logger.info(
        f"Permission denied: User {user.email} lacks {permission_type} "
        f"access to document {document.id}"
    )
    return False


def require_document_permission(user: Optional[User], document: Document,
                                permission_type: str) -> None:
    """
    Require permission or raise PermissionDenied

    Args:
        user: User instance
        document: Document instance
        permission_type: 'read', 'write', or 'delete'

    Raises:
        PermissionDenied: If user lacks required permission

    Usage:
        require_document_permission(request.user, document, 'write')
    """
    if not has_document_permission(user, document, permission_type):
        logger.warning(
            f"Permission denied: User {user.email if user else 'anonymous'} "
            f"attempted {permission_type} on document {document.id}"
        )
        raise PermissionDenied(
            f"You do not have {permission_type} permission on this document"
        )


def has_version_permission(user: Optional[User], version,
                          permission_type: str) -> bool:
    """
    Check if user has permission to access document version

    Args:
        user: User instance
        version: DocumentVersion instance
        permission_type: 'read' or 'restore'

    Returns:
        bool: True if user has permission
    """
    from .engine_models import DocumentVersion

    # Check document permission
    if permission_type == 'read':
        return has_document_permission(user, version.document, 'read')
    elif permission_type == 'restore':
        # Restore requires write permission
        return has_document_permission(user, version.document, 'write')

    return False


def require_version_permission(user: Optional[User], version,
                               permission_type: str) -> None:
    """
    Require version permission or raise PermissionDenied

    Args:
        user: User instance
        version: DocumentVersion instance
        permission_type: 'read' or 'restore'

    Raises:
        PermissionDenied: If user lacks required permission
    """
    if not has_version_permission(user, version, permission_type):
        raise PermissionDenied(
            f"You do not have {permission_type} permission on this version"
        )


def get_user_ip(request) -> str:
    """
    Get user's IP address from request

    Handles proxy headers (X-Forwarded-For)

    Args:
        request: Django request object

    Returns:
        str: IP address
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def log_permission_denied(user: Optional[User], resource: str,
                         action: str, request=None) -> None:
    """
    Log permission denial for security monitoring

    Args:
        user: User who was denied
        resource: Resource being accessed (e.g., "document:123")
        action: Action attempted (e.g., "restore_version")
        request: Django request object (optional)
    """
    security_logger = logging.getLogger('security')

    ip = get_user_ip(request) if request else 'unknown'
    user_email = user.email if user else 'anonymous'

    security_logger.warning(
        f"PERMISSION_DENIED: User={user_email} IP={ip} "
        f"Resource={resource} Action={action}"
    )


def check_rate_limit(user: Optional[User], action: str,
                    limit: int, window_minutes: int = 60) -> bool:
    """
    Check if user has exceeded rate limit for action

    Args:
        user: User instance
        action: Action being performed (e.g., 'restore_version')
        limit: Maximum number of actions allowed
        window_minutes: Time window in minutes

    Returns:
        bool: True if within limit, False if exceeded
    """
    if not user or not user.is_authenticated:
        return False

    from datetime import timedelta
    from django.utils import timezone
    from .models import RateLimitLog

    cutoff = timezone.now() - timedelta(minutes=window_minutes)

    count = RateLimitLog.objects.filter(
        user=user,
        action=action,
        timestamp__gte=cutoff
    ).count()

    if count >= limit:
        logger.warning(
            f"Rate limit exceeded: User {user.email} "
            f"performed {action} {count} times in {window_minutes} minutes"
        )
        return False

    # Log this action
    RateLimitLog.objects.create(user=user, action=action)

    return True


def sanitize_user_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injection attacks

    Args:
        text: User input text
        max_length: Maximum allowed length

    Returns:
        str: Sanitized text

    Security:
        - Removes HTML tags
        - Escapes special characters
        - Limits length
        - Prevents XSS and injection
    """
    if not text:
        return ''

    import bleach
    from django.utils.html import escape

    # Remove all HTML tags
    text = bleach.clean(text, tags=[], strip=True)

    # Escape special characters
    text = escape(text)

    # Limit length
    text = text[:max_length]

    return text


def is_admin_user(user: Optional[User]) -> bool:
    """
    Check if user is admin

    Args:
        user: User instance

    Returns:
        bool: True if user is admin
    """
    if not user or not user.is_authenticated:
        return False

    return user.is_superuser or user.is_staff


def require_admin(user: Optional[User]) -> None:
    """
    Require user to be admin or raise PermissionDenied

    Args:
        user: User instance

    Raises:
        PermissionDenied: If user is not admin
    """
    if not is_admin_user(user):
        raise PermissionDenied("This operation requires admin privileges")
