"""
Document Version Management API Views

REST API endpoints for document versioning operations.
"""

import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
import json

from .models import Document, Doctype
from .engine_models import DocumentVersion
from .version_engine import VersionEngine

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET"])
def list_versions(request, document_id):
    """
    List all versions of a document

    GET /api/doctypes/documents/{document_id}/versions/

    Query Parameters:
        limit: Maximum number of versions to return (optional)

    Returns:
        {
            "success": true,
            "versions": [
                {
                    "version_number": 3,
                    "changed_by": "user@example.com",
                    "changed_at": "2025-12-03T10:30:00Z",
                    "comment": "Updated pricing",
                    "changes_summary": "2 fields modified",
                    "is_current": true
                },
                ...
            ],
            "current_version": 3,
            "total_versions": 3
        }
    """
    try:
        document = get_object_or_404(Document, pk=document_id)
        engine = VersionEngine(document)

        # Get limit from query params
        limit = request.GET.get('limit')
        if limit:
            try:
                limit = int(limit)
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid limit parameter'
                }, status=400)

        # Get version history
        history = engine.get_version_history()

        # Apply limit if specified
        if limit:
            history = history[:limit]

        return JsonResponse({
            'success': True,
            'versions': history,
            'current_version': document.version_number,
            'total_versions': DocumentVersion.objects.filter(document=document).count()
        })

    except Exception as e:
        logger.error(f"Error listing versions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_version(request, document_id, version_number):
    """
    Get a specific version of a document

    GET /api/doctypes/documents/{document_id}/versions/{version_number}/

    Returns:
        {
            "success": true,
            "version": {
                "version_number": 2,
                "data_snapshot": {...},
                "changes": {...},
                "changed_by": "user@example.com",
                "changed_at": "2025-12-03T10:00:00Z",
                "comment": "Initial version"
            }
        }
    """
    try:
        document = get_object_or_404(Document, pk=document_id)
        engine = VersionEngine(document)

        version = engine.get_version(int(version_number))

        if not version:
            return JsonResponse({
                'success': False,
                'error': f'Version {version_number} not found'
            }, status=404)

        return JsonResponse({
            'success': True,
            'version': {
                'version_number': version.version_number,
                'data_snapshot': version.data_snapshot,
                'changes': version.changes,
                'changed_by': version.changed_by.email if version.changed_by else None,
                'changed_at': version.changed_at.isoformat(),
                'comment': version.comment
            }
        })

    except Exception as e:
        logger.error(f"Error getting version: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def compare_versions(request, document_id):
    """
    Compare two versions of a document

    GET /api/doctypes/documents/{document_id}/versions/compare/?v1=1&v2=2

    Query Parameters:
        v1: First version number (required)
        v2: Second version number (required)
        field: Optional field name to compare (optional)
        format: 'json' or 'text' (default: 'json')

    Returns (format=json):
        {
            "success": true,
            "comparison": {
                "version1": {...},
                "version2": {...},
                "diff": {
                    "added": {...},
                    "modified": {...},
                    "removed": {...}
                },
                "has_changes": true
            }
        }

    Returns (format=text):
        {
            "success": true,
            "diff_text": "--- Version 1\n+++ Version 2\n..."
        }
    """
    try:
        document = get_object_or_404(Document, pk=document_id)
        engine = VersionEngine(document)

        # Get version numbers from query params
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
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Version numbers must be integers'
            }, status=400)

        # Get format and field parameters
        format_type = request.GET.get('format', 'json')
        field_name = request.GET.get('field')

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
        logger.error(f"Error comparing versions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def restore_version(request, document_id, version_number):
    """
    Restore document to a specific version

    POST /api/doctypes/documents/{document_id}/versions/{version_number}/restore/

    Request Body:
        {
            "comment": "Optional comment for restoration" (optional)
        }

    Returns:
        {
            "success": true,
            "message": "Document restored to version 2",
            "new_version": {
                "version_number": 4,
                "comment": "Restored to version 2",
                "changed_by": "user@example.com",
                "changed_at": "2025-12-03T11:00:00Z"
            },
            "document": {
                "id": 123,
                "current_version": 4,
                "data": {...}
            }
        }
    """
    try:
        document = get_object_or_404(Document, pk=document_id)
        engine = VersionEngine(document)

        # Parse request body
        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)

        comment = body.get('comment', '')

        # Get user from request (if available)
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            pass
        else:
            user = None

        # Restore version
        new_version = engine.restore_version(
            int(version_number),
            user=user,
            comment=comment
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
        logger.error(f"Error restoring version: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def get_version_history(request, document_id):
    """
    Get formatted version history

    GET /api/doctypes/documents/{document_id}/versions/history/

    Returns:
        {
            "success": true,
            "history": [
                {
                    "version_number": 3,
                    "changed_by": "user@example.com",
                    "changed_at": "2025-12-03T10:30:00Z",
                    "comment": "Updated pricing",
                    "changes_summary": "2 fields modified",
                    "is_current": true
                },
                ...
            ],
            "document": {
                "id": 123,
                "doctype": "Sales Order",
                "current_version": 3
            }
        }
    """
    try:
        document = get_object_or_404(Document, pk=document_id)
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
        logger.error(f"Error getting version history: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
