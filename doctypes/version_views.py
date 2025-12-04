"""
Secure Document Version Management API Views

SECURITY ENHANCEMENTS:
- Authentication required (OWASP A07)
- Authorization checks (OWASP A01)
- CSRF protection enabled (OWASP A05)
- Input sanitization (OWASP A03)
- Audit logging (OWASP A09)
- Rate limiting (OWASP A04)
- Integrity checking (OWASP A08)
"""

import logging
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import Document
from .engine_models import DocumentVersion
from .version_engine import VersionEngine
from .permissions import (
    require_document_permission,
    sanitize_user_input,
    get_user_ip,
    PermissionDenied
)
from .security_models import VersionAccessLog, SecurityEvent

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')


def log_version_access(version, user, action, request, success=True, error=''):
    """
    Log all version access for audit trail

    Security: Addresses OWASP A09 (Logging and Monitoring)
    """
    try:
        VersionAccessLog.objects.create(
            version=version,
            user=user,
            action=action,
            timestamp=None,  # auto_now_add
            ip_address=get_user_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            success=success,
            error_message=error,
            request_path=request.path,
            query_params=dict(request.GET) if hasattr(request, 'GET') else {}
        )
    except Exception as e:
        logger.error(f"Failed to log version access: {str(e)}")


def log_security_event(event_type, severity, user, request, description,
                       resource='', action=''):
    """
    Log security events for monitoring

    Security: Addresses OWASP A09 (Logging and Monitoring)
    """
    try:
        SecurityEvent.objects.create(
            event_type=event_type,
            severity=severity,
            user=user,
            ip_address=get_user_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            description=description,
            resource=resource,
            action=action
        )
    except Exception as e:
        logger.error(f"Failed to log security event: {str(e)}")


def check_rate_limit_decorator(action, limit=10, window_minutes=60):
    """
    Decorator to check rate limits

    Security: Addresses OWASP A04 (Insecure Design - Rate Limiting)
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            from datetime import timedelta
            from django.utils import timezone
            from .security_models import RateLimitLog

            user = request.user
            cutoff = timezone.now() - timedelta(minutes=window_minutes)

            count = RateLimitLog.objects.filter(
                user=user,
                action=action,
                timestamp__gte=cutoff
            ).count()

            if count >= limit:
                security_logger.warning(
                    f"Rate limit exceeded: User {user.email} "
                    f"performed {action} {count} times in {window_minutes} minutes"
                )

                log_security_event(
                    'rate_limit', 'medium', user, request,
                    f"Rate limit exceeded for {action}",
                    action=action
                )

                return JsonResponse({
                    'success': False,
                    'error': 'Rate limit exceeded. Please try again later.'
                }, status=429)

            # Log this action
            RateLimitLog.objects.create(
                user=user,
                action=action,
                ip_address=get_user_ip(request)
            )

            return func(request, *args, **kwargs)
        return wrapper
    return decorator


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_versions(request, document_id):
    """
    List all versions of a document

    Security:
        - Authentication required (OWASP A07)
        - Authorization check (OWASP A01)
        - Audit logging (OWASP A09)
        - CSRF protection enabled (OWASP A05)

    GET /api/doctypes/documents/{document_id}/versions/

    Query Parameters:
        limit: Maximum number of versions to return (optional)

    Returns:
        {
            "success": true,
            "versions": [...],
            "current_version": 3,
            "total_versions": 3
        }
    """
    try:
        document = get_object_or_404(Document, pk=document_id)

        # Authorization check
        try:
            require_document_permission(request.user, document, 'read')
        except PermissionDenied as e:
            log_security_event(
                'perm_denied', 'medium', request.user, request,
                f"Permission denied accessing versions for document {document_id}",
                resource=f"document:{document_id}",
                action='list_versions'
            )
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=403)

        engine = VersionEngine(document)

        # Get limit from query params (with validation)
        limit = request.GET.get('limit')
        if limit:
            try:
                limit = int(limit)
                if limit < 1 or limit > 1000:
                    raise ValueError("Limit must be between 1 and 1000")
            except ValueError as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid limit parameter: {str(e)}'
                }, status=400)

        # Get version history
        history = engine.get_version_history()

        # Apply limit if specified
        if limit:
            history = history[:limit]

        # Log access for each version
        for version_info in history:
            version = engine.get_version(version_info['version_number'])
            if version:
                log_version_access(version, request.user, 'list', request)

        return JsonResponse({
            'success': True,
            'versions': history,
            'current_version': document.version_number,
            'total_versions': DocumentVersion.objects.filter(document=document).count()
        })

    except Exception as e:
        logger.error(f"Error listing versions: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please contact support.'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_version(request, document_id, version_number):
    """
    Get a specific version of a document

    Security:
        - Authentication required
        - Authorization check
        - Audit logging
        - Integrity verification

    GET /api/doctypes/documents/{document_id}/versions/{version_number}/
    """
    try:
        document = get_object_or_404(Document, pk=document_id)

        # Authorization check
        try:
            require_document_permission(request.user, document, 'read')
        except PermissionDenied as e:
            log_security_event(
                'perm_denied', 'medium', request.user, request,
                f"Permission denied viewing version {version_number} of document {document_id}",
                resource=f"document:{document_id}",
                action='get_version'
            )
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=403)

        engine = VersionEngine(document)
        version = engine.get_version(int(version_number))

        if not version:
            return JsonResponse({
                'success': False,
                'error': f'Version {version_number} not found'
            }, status=404)

        # Verify integrity
        if not version.verify_integrity():
            security_logger.critical(
                f"Version integrity check FAILED: "
                f"Document {document_id} Version {version_number}"
            )

            log_security_event(
                'integrity_fail', 'critical', request.user, request,
                f"Version integrity check failed for version {version_number}",
                resource=f"version:{version.id}",
                action='integrity_check'
            )

            return JsonResponse({
                'success': False,
                'error': 'Version data integrity check failed. This version may have been tampered with.'
            }, status=500)

        # Log access
        log_version_access(version, request.user, 'view', request)

        return JsonResponse({
            'success': True,
            'version': {
                'version_number': version.version_number,
                'data_snapshot': version.data_snapshot,
                'changes': version.changes,
                'changed_by': version.changed_by.email if version.changed_by else None,
                'changed_at': version.changed_at.isoformat(),
                'comment': version.comment,
                'integrity_verified': True
            }
        })

    except Exception as e:
        logger.error(f"Error getting version: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please contact support.'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compare_versions(request, document_id):
    """
    Compare two versions of a document

    Security:
        - Authentication required
        - Authorization check
        - Input validation
        - Audit logging

    GET /api/doctypes/documents/{document_id}/versions/compare/?v1=1&v2=2
    """
    try:
        document = get_object_or_404(Document, pk=document_id)

        # Authorization check
        try:
            require_document_permission(request.user, document, 'read')
        except PermissionDenied as e:
            log_security_event(
                'perm_denied', 'medium', request.user, request,
                f"Permission denied comparing versions of document {document_id}",
                resource=f"document:{document_id}",
                action='compare_versions'
            )
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=403)

        # Get and validate version numbers
        v1 = request.GET.get('v1')
        v2 = request.GET.get('v2')

        if not v1 or not v2:
            return JsonResponse({
                'success': False,
                'error': 'Both v1 and v2 parameters are required'
            }, status=400)

        try:
            v1 = int(v1)
            v2 = int(v2)
            if v1 < 1 or v2 < 1:
                raise ValueError("Version numbers must be positive")
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid version numbers: {str(e)}'
            }, status=400)

        engine = VersionEngine(document)

        # Get format and field parameters
        format_type = request.GET.get('format', 'json')
        field_name = request.GET.get('field')

        # Sanitize field name if provided
        if field_name:
            field_name = sanitize_user_input(field_name, max_length=100)

        # Log comparison
        version1 = engine.get_version(v1)
        version2 = engine.get_version(v2)
        if version1:
            log_version_access(version1, request.user, 'compare', request)
        if version2:
            log_version_access(version2, request.user, 'compare', request)

        if format_type == 'text':
            # Get unified diff text
            diff_text = engine.get_diff_text(v1, v2, field_name)
            return JsonResponse({
                'success': True,
                'diff_text': diff_text
            })
        else:
            # Get structured comparison
            comparison = engine.compare_versions(v1, v2)
            return JsonResponse({
                'success': True,
                'comparison': comparison
            })

    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=404)
    except Exception as e:
        logger.error(f"Error comparing versions: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please contact support.'
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@check_rate_limit_decorator('restore_version', limit=10, window_minutes=60)
@transaction.atomic
def restore_version(request, document_id, version_number):
    """
    Restore document to a specific version

    Security:
        - Authentication required
        - Authorization check (write permission)
        - Rate limiting (10 per hour)
        - Input sanitization
        - Audit logging
        - Integrity verification
        - Transaction safety

    POST /api/doctypes/documents/{document_id}/versions/{version_number}/restore/

    Request Body:
        {
            "comment": "Optional comment for restoration"
        }
    """
    try:
        document = get_object_or_404(Document, pk=document_id)

        # Authorization check (requires write permission)
        try:
            require_document_permission(request.user, document, 'write')
        except PermissionDenied as e:
            log_security_event(
                'perm_denied', 'high', request.user, request,
                f"Permission denied restoring version {version_number} of document {document_id}",
                resource=f"document:{document_id}",
                action='restore_version'
            )
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=403)

        engine = VersionEngine(document)

        # Parse and validate request body
        import json
        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)

        # Sanitize comment
        comment = sanitize_user_input(
            body.get('comment', ''),
            max_length=1000
        )

        # Get version to restore
        version_to_restore = engine.get_version(int(version_number))
        if not version_to_restore:
            return JsonResponse({
                'success': False,
                'error': f'Version {version_number} not found'
            }, status=404)

        # Verify integrity before restoration
        if not version_to_restore.verify_integrity():
            security_logger.critical(
                f"Attempted restore of tampered version: "
                f"Document {document_id} Version {version_number}"
            )

            log_security_event(
                'integrity_fail', 'critical', request.user, request,
                f"Attempted to restore tampered version {version_number}",
                resource=f"version:{version_to_restore.id}",
                action='restore_version'
            )

            return JsonResponse({
                'success': False,
                'error': 'Version integrity check failed. Cannot restore tampered version.'
            }, status=400)

        # Perform restoration
        new_version = engine.restore_version(
            int(version_number),
            user=request.user,
            comment=comment
        )

        # Log restoration
        log_version_access(version_to_restore, request.user, 'restore', request)

        security_logger.info(
            f"Version restored: User={request.user.email} "
            f"Document={document_id} FromVersion={version_number} "
            f"ToVersion={new_version.version_number} "
            f"IP={get_user_ip(request)}"
        )

        return JsonResponse({
            'success': True,
            'message': f'Document restored to version {version_number}',
            'new_version': {
                'version_number': new_version.version_number,
                'comment': new_version.comment,
                'changed_by': new_version.changed_by.email if new_version.changed_by else None,
                'changed_at': new_version.changed_at.isoformat()
            },
            'document': {
                'id': document.id,
                'current_version': document.version_number,
                'data': document.data
            }
        })

    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=404)
    except Exception as e:
        logger.error(f"Error restoring version: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please contact support.'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_version_history(request, document_id):
    """
    Get formatted version history

    Security:
        - Authentication required
        - Authorization check
        - Audit logging

    GET /api/doctypes/documents/{document_id}/versions/history/
    """
    try:
        document = get_object_or_404(Document, pk=document_id)

        # Authorization check
        try:
            require_document_permission(request.user, document, 'read')
        except PermissionDenied as e:
            log_security_event(
                'perm_denied', 'medium', request.user, request,
                f"Permission denied viewing history of document {document_id}",
                resource=f"document:{document_id}",
                action='get_version_history'
            )
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=403)

        engine = VersionEngine(document)
        history = engine.get_version_history()

        return JsonResponse({
            'success': True,
            'history': history,
            'document': {
                'id': document.id,
                'doctype': document.doctype.name,
                'current_version': document.version_number
            }
        })

    except Exception as e:
        logger.error(f"Error getting version history: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred. Please contact support.'
        }, status=500)
