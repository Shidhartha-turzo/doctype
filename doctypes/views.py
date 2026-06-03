from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Doctype, Document, DocumentShare, DocumentAttachment, DocumentLinkMultiple
from .serializers import (
    DoctypeSerializer, DoctypeListSerializer, DynamicDocumentSerializer,
    DocumentShareSerializer, BulkShareSerializer,
    DocumentWorkflowStateSerializer, PerformTransitionSerializer,
    WorkflowTransitionLogSerializer, DocumentAttachmentSerializer,
)
from .workflow_engine import WorkflowService, WorkflowError
from .hook_engine import HookService, HookError
from .report_engine import ReportService, ReportError, ReportPermissionError
from .print_engine import PrintService, PrintError
from .search_engine import SearchService, SearchError
from .child_tables import validate_table, ChildTableError
from . import import_export
from .permissions import has_doctype_permission, get_field_restrictions
import logging
import json
from decimal import Decimal
from datetime import datetime


class DoctypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing doctypes (document type schemas)
    """
    queryset = Doctype.objects.filter(is_active=True)
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return DoctypeListSerializer
        return DoctypeSerializer

    @extend_schema(
        responses={200: DoctypeListSerializer(many=True)},
        parameters=[
            OpenApiParameter('status', str, description='Filter by status'),
            OpenApiParameter('search', str, description='Search by name or description'),
        ]
    )
    def list(self, request):
        """List all active doctypes"""
        queryset = self.get_queryset()

        # Filter by status
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Search
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(request=DoctypeSerializer, responses={201: DoctypeSerializer})
    def create(self, request):
        """Create a new doctype"""
        serializer = DoctypeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(responses={200: DoctypeSerializer})
    def retrieve(self, request, pk=None):
        """Get a specific doctype by slug or ID"""
        try:
            if pk.isdigit():
                doctype = get_object_or_404(Doctype, pk=pk, is_active=True)
            else:
                doctype = get_object_or_404(Doctype, slug=pk, is_active=True)

            serializer = DoctypeSerializer(doctype)
            return Response(serializer.data)
        except Doctype.DoesNotExist:
            return Response({'error': 'Doctype not found'}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        responses={200: DynamicDocumentSerializer},
        parameters=[
            OpenApiParameter('slug', str, description='Doctype slug', location=OpenApiParameter.PATH)
        ]
    )
    @action(detail=True, methods=['get', 'post'], url_path='records')
    def records(self, request, pk=None):
        """List or create documents for this doctype"""
        doctype = self.get_object()

        action = 'create' if request.method == 'POST' else 'read'
        if not has_doctype_permission(request.user, doctype, action):
            return Response(
                {'detail': f"You do not have '{action}' permission on this doctype."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == 'GET':
            documents = Document.objects.filter(doctype=doctype)

            # Search in JSON data
            search = request.query_params.get('q')
            if search:
                documents = documents.filter(data__icontains=search)

            serializer = DynamicDocumentSerializer(
                documents,
                many=True,
                doctype=doctype,
                context={'request': request}
            )
            return Response(serializer.data)

        elif request.method == 'POST':
            serializer = DynamicDocumentSerializer(
                data=request.data,
                doctype=doctype,
                context={'request': request}
            )
            if serializer.is_valid():
                try:
                    document = serializer.save()
                except HookError as e:
                    return Response(
                        {'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST
                    )
                try:
                    WorkflowService.initialize_workflow(document, user=request.user)
                except WorkflowError as e:
                    logging.getLogger(__name__).warning(f'Workflow init failed: {e}')
                return Response(
                    DynamicDocumentSerializer(document, doctype=doctype).data,
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(responses={200: dict})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctype_schema(request, slug):
    """Get the schema for a specific doctype"""
    doctype = get_object_or_404(Doctype, slug=slug, is_active=True)
    if not has_doctype_permission(request.user, doctype, 'read'):
        return Response(
            {'detail': "You do not have 'read' permission on this doctype."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return Response({
        'name': doctype.name,
        'slug': doctype.slug,
        'description': doctype.description,
        'schema': doctype.schema,
        'version': doctype.version
    })


@extend_schema(
    responses={200: dict},
    parameters=[
        OpenApiParameter('q', str, description='Search query', required=True),
        OpenApiParameter('slug', str, description='Doctype slug', location=OpenApiParameter.PATH)
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_documents(request, slug):
    """Search documents within a doctype"""
    doctype = get_object_or_404(Doctype, slug=slug, is_active=True)
    if not has_doctype_permission(request.user, doctype, 'read'):
        return Response(
            {'detail': "You do not have 'read' permission on this doctype."},
            status=status.HTTP_403_FORBIDDEN,
        )
    query = request.query_params.get('q', '')

    if not query:
        return Response({'error': 'Search query parameter "q" is required'}, status=status.HTTP_400_BAD_REQUEST)

    documents = Document.objects.filter(
        doctype=doctype,
        data__icontains=query
    )

    serializer = DynamicDocumentSerializer(
        documents,
        many=True,
        doctype=doctype,
        context={'request': request}
    )

    return Response({
        'query': query,
        'count': documents.count(),
        'results': serializer.data
    })


@extend_schema(responses={200: dict})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def openapi_schema(request):
    """Get OpenAPI schema for all doctypes"""
    from rest_framework.schemas.openapi import SchemaGenerator
    from django.urls import path

    generator = SchemaGenerator(title='Doctype API')
    schema = generator.get_schema()

    return Response(schema)


@extend_schema(
    request=BulkShareSerializer,
    responses={200: dict},
    parameters=[
        OpenApiParameter('document_id', int, description='Document ID to share', location=OpenApiParameter.PATH)
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def share_document(request, document_id):
    """
    Share a document via email

    Send a document to one or multiple email addresses with an optional personal message.
    Rate limiting applies based on SystemSettings.
    """
    from core.email_service import EmailService
    from core.security_models import SystemSettings
    from django.conf import settings

    # Get document
    document = get_object_or_404(Document, id=document_id)

    if not has_doctype_permission(request.user, document.doctype, 'read'):
        return Response(
            {'error': "You do not have 'read' permission on this doctype."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check if email is enabled
    system_settings = SystemSettings.get_settings()
    if not system_settings.enable_email:
        return Response(
            {'error': 'Email functionality is disabled. Please enable it in System Settings.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    if not system_settings.allow_document_sharing:
        return Response(
            {'error': 'Document sharing is disabled. Please enable it in System Settings.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Validate request data
    serializer = BulkShareSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    recipient_emails = serializer.validated_data['recipient_emails']
    personal_message = serializer.validated_data.get('personal_message', '')

    # Check rate limit
    if not EmailService.check_rate_limit(request.user, 'document_share'):
        return Response(
            {'error': 'Email rate limit exceeded. Please try again later.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    # Generate share URL
    share_url = f"{getattr(settings, 'SITE_URL', 'http://localhost:8000')}/doctypes/{document.doctype.slug}/documents/{document.id}/"

    # Send emails and track shares
    results = {
        'success_count': 0,
        'failed_count': 0,
        'total': len(recipient_emails),
        'shares': []
    }

    for recipient_email in recipient_emails:
        try:
            # Send email
            email_sent = EmailService.send_document_share_email(
                document=document,
                recipient_email=recipient_email,
                sender=request.user,
                message=personal_message,
                share_url=share_url
            )

            # Track the share
            share_status = 'sent' if email_sent else 'failed'
            document_share = DocumentShare.objects.create(
                document=document,
                shared_by=request.user,
                recipient_email=recipient_email,
                personal_message=personal_message,
                share_url=share_url,
                status=share_status,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

            if email_sent:
                results['success_count'] += 1
            else:
                results['failed_count'] += 1

            results['shares'].append({
                'id': document_share.id,
                'recipient_email': recipient_email,
                'status': share_status
            })

        except Exception as e:
            results['failed_count'] += 1
            results['shares'].append({
                'recipient_email': recipient_email,
                'status': 'failed',
                'error': str(e)
            })

    return Response({
        'message': f'Document shared with {results["success_count"]} out of {results["total"]} recipients',
        'results': results
    }, status=status.HTTP_200_OK if results['success_count'] > 0 else status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# Reports API
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def report_list(request):
    """List the reports the current user is allowed to run."""
    reports = ReportService.list_for_user(request.user)
    return Response([
        {
            'id': r.id,
            'name': r.name,
            'doctype': r.doctype.slug,
            'report_type': r.report_type,
            'description': r.description,
        }
        for r in reports
    ])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def report_run(request, report_id):
    """
    Run a report and return its result as JSON, or as CSV with ?format=csv.

    Runtime filters may be passed via a JSON-encoded ?filters= parameter,
    e.g. filters=[{"field":"status","op":"eq","value":"open"}].
    """
    from .engine_models import Report

    report = get_object_or_404(Report, id=report_id)

    runtime_filters = []
    raw_filters = request.query_params.get('filters')
    if raw_filters:
        try:
            runtime_filters = json.loads(raw_filters)
        except json.JSONDecodeError:
            return Response(
                {'detail': "'filters' must be valid JSON."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(runtime_filters, list):
            return Response(
                {'detail': "'filters' must be a JSON list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        result = ReportService.run(report, request.user, runtime_filters=runtime_filters)
    except ReportPermissionError as e:
        return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)
    except ReportError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    if request.query_params.get('format') == 'csv':
        from django.http import HttpResponse
        response = HttpResponse(ReportService.to_csv(result), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{report.name}.csv"'
        return response

    return Response(result)


# ============================================================================
# Attachments API
# ============================================================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def document_attachments(request, document_id):
    """List a document's attachments (GET) or upload a new one (POST)."""
    document = get_object_or_404(Document, id=document_id)

    if request.method == 'GET':
        if not has_doctype_permission(request.user, document.doctype, 'read'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        attachments = document.attachments.all()
        return Response(
            DocumentAttachmentSerializer(attachments, many=True, context={'request': request}).data
        )

    # POST = upload
    if not has_doctype_permission(request.user, document.doctype, 'write'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    upload = request.FILES.get('file')
    if not upload:
        return Response(
            {'detail': "No file provided (use multipart field 'file')."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from django.conf import settings
    from core.security_models import SystemSettings
    import os

    # Limits are admin-configurable via SystemSettings, falling back to the
    # static settings.py defaults if the singleton has no value.
    system_settings = SystemSettings.get_settings()
    max_mb = system_settings.max_attachment_size_mb or getattr(settings, 'MAX_ATTACHMENT_SIZE_MB', 10)
    max_bytes = max_mb * 1024 * 1024
    if upload.size > max_bytes:
        return Response(
            {'detail': f'File exceeds the {max_mb} MB limit.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    configured = system_settings.allowed_attachment_extensions
    if configured is None:
        configured = getattr(settings, 'ALLOWED_ATTACHMENT_EXTENSIONS', [])
    extension = os.path.splitext(upload.name)[1].lstrip('.').lower()
    allowed = [e.lower().lstrip('.') for e in configured]
    if allowed and extension not in allowed:
        return Response(
            {'detail': f"File type '.{extension}' is not allowed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    attachment = DocumentAttachment.objects.create(
        document=document,
        file=upload,
        filename=upload.name,
        content_type=getattr(upload, 'content_type', '') or '',
        size=upload.size,
        uploaded_by=request.user,
    )
    return Response(
        DocumentAttachmentSerializer(attachment, context={'request': request}).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def attachment_detail(request, attachment_id):
    """Download (GET) or delete (DELETE) a single attachment."""
    attachment = get_object_or_404(DocumentAttachment, id=attachment_id)
    doctype = attachment.document.doctype

    if request.method == 'DELETE':
        if not has_doctype_permission(request.user, doctype, 'delete'):
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # GET = download
    if not has_doctype_permission(request.user, doctype, 'read'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    from django.http import FileResponse
    return FileResponse(
        attachment.file.open('rb'), as_attachment=True, filename=attachment.filename
    )


# ============================================================================
# Print API
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def print_document(request, document_id):
    """
    Render a document for printing.

    Query params:
      - format_id: specific PrintFormat to use (defaults to the doctype default)
      - output: 'html' (default) or 'pdf' (requires xhtml2pdf)

    Note: 'output' is used rather than 'format' because DRF reserves the
    'format' query parameter for content negotiation.
    """
    document = get_object_or_404(Document, id=document_id)
    if not has_doctype_permission(request.user, document.doctype, 'read'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    format_id = request.query_params.get('format_id')
    output = request.query_params.get('output', 'html').lower()

    from django.http import HttpResponse
    try:
        if output == 'pdf':
            pdf_bytes = PrintService.render_pdf(document, format_id=format_id)
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{document.name}.pdf"'
            return response
        html = PrintService.render_html(document, format_id=format_id)
        return HttpResponse(html, content_type='text/html')
    except PrintError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Import / Export API
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctype_export(request, doctype_slug):
    """Export all of a doctype's documents as a CSV download."""
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    if not has_doctype_permission(request.user, doctype, 'export'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    from django.http import HttpResponse
    response = HttpResponse(import_export.export_csv(doctype), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{doctype.slug}.csv"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctype_import_template(request, doctype_slug):
    """Download an empty CSV template (header row) for importing."""
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    if not has_doctype_permission(request.user, doctype, 'export'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    from django.http import HttpResponse
    response = HttpResponse(import_export.import_template(doctype), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{doctype.slug}_template.csv"'
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def doctype_import(request, doctype_slug):
    """Import documents from an uploaded CSV file (multipart field 'file')."""
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    if not has_doctype_permission(request.user, doctype, 'import'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    upload = request.FILES.get('file')
    if not upload:
        return Response(
            {'detail': "No file provided (use multipart field 'file')."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        result = import_export.import_csv(doctype, upload, request.user)
    except import_export.ImportExportError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # 207-ish semantics: created some, maybe with row errors.
    http_status = status.HTTP_201_CREATED if result['created'] else status.HTTP_400_BAD_REQUEST
    return Response(result, status=http_status)


# ============================================================================
# Advanced Search API
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_search(request, doctype_slug):
    """
    Advanced structured search within a doctype.

    JSON body:
      {
        "query": "free text",            # optional, matches name/data
        "filters": [{"field","op","value"}],
        "match": "all" | "any",          # how filters combine (default all)
        "sort": "field" | "-field",
        "page": 1, "page_size": 50
      }
    """
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    if not has_doctype_permission(request.user, doctype, 'read'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    body = request.data if isinstance(request.data, dict) else {}
    try:
        result = SearchService.search(
            doctype,
            request.user,
            filters=body.get('filters'),
            match=body.get('match', 'all'),
            query=body.get('query'),
            sort=body.get('sort'),
            page=body.get('page', 1),
            page_size=body.get('page_size', 50),
        )
    except SearchError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def global_search(request):
    """Search a term (?q=) across every doctype the user can read."""
    try:
        result = SearchService.global_search(request.user, request.query_params.get('q', ''))
    except SearchError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


# ============================================================================
# Dynamic Form Views for Document Management
# ============================================================================

def _sync_multi_links(document, multi_link_fields_data):
    """Create ordered DocumentLinkMultiple rows for many-to-many fields."""
    for field_name, target_ids in multi_link_fields_data.items():
        for order, target_id in enumerate(target_ids):
            try:
                target_doc = Document.objects.get(id=int(target_id))
                DocumentLinkMultiple.objects.create(
                    source_document=document,
                    target_document=target_doc,
                    field_name=field_name,
                    order=order,
                )
            except (Document.DoesNotExist, ValueError):
                pass  # Already validated during form processing


def _require_doctype_perm(request, doctype, action, document=None):
    """Raise PermissionDenied (403) if the user lacks the action on the doctype."""
    if not has_doctype_permission(request.user, doctype, action, document=document):
        raise PermissionDenied(
            f"You do not have '{action}' permission on {doctype.name}."
        )


@login_required
def document_list(request, doctype_slug):
    """List all documents for a doctype with dynamic table"""
    from .engine_models import DocumentWorkflowState

    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    _require_doctype_perm(request, doctype, 'read')
    documents = Document.objects.filter(doctype=doctype).order_by('-created_at')

    # Check if this doctype has an active workflow
    has_workflow = WorkflowService.get_active_workflow(doctype) is not None

    if has_workflow:
        from django.db.models import Prefetch
        documents = documents.prefetch_related(
            Prefetch(
                'workflow_state',
                queryset=DocumentWorkflowState.objects.select_related('current_state'),
            )
        )

    # Get schema fields
    fields = doctype.schema.get('fields', [])

    context = {
        'doctype': doctype,
        'documents': documents,
        'fields': fields,
        'field_names': [f['name'] for f in fields],
        'has_workflow': has_workflow,
    }

    return render(request, 'doctypes/document_list.html', context)


@login_required
def document_create(request, doctype_slug):
    """Create a new document with dynamic form"""
    from .models import DocumentLink

    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    _require_doctype_perm(request, doctype, 'create')

    fields = doctype.schema.get('fields', [])
    hidden_fields, readonly_fields = get_field_restrictions(request.user, doctype)
    # Drop hidden fields entirely; flag read-only fields so the template
    # disables them. Work on copies so the persisted schema is untouched.
    fields = [
        {**f, 'readonly': True} if f['name'] in readonly_fields else f
        for f in fields
        if f['name'] not in hidden_fields
    ]

    # Get available documents for link fields
    link_field_options = {}
    for field in fields:
        # 'link' (single) and 'multiselect' with a link_doctype (many-to-many)
        # both pick from the target doctype's documents.
        if field['type'] in ('link', 'multiselect') and field.get('link_doctype'):
            link_doctype_name = field.get('link_doctype')
            try:
                link_doctype = Doctype.objects.get(name=link_doctype_name, is_active=True)
                link_field_options[field['name']] = Document.objects.filter(
                    doctype=link_doctype,
                    is_deleted=False
                ).order_by('name')
            except Doctype.DoesNotExist:
                link_field_options[field['name']] = []

    if request.method == 'POST':
        # Collect and validate form data
        data = {}
        errors = {}
        link_fields_data = {}  # Store link field values separately
        multi_link_fields_data = {}  # field_name -> [target document ids]

        for field in fields:
            field_name = field['name']
            field_type = field['type']
            # Never accept values for read-only fields, even if posted.
            if field_name in readonly_fields:
                continue

            # Multiselect: many-to-many document link (with link_doctype) or a
            # plain list of static option values. Uses getlist for multi-values.
            if field_type == 'multiselect':
                selected = request.POST.getlist(field_name)
                if field.get('link_doctype'):
                    names = []
                    ids = []
                    for val in selected:
                        try:
                            target = Document.objects.get(id=int(val))
                            names.append(target.name)
                            ids.append(target.id)
                        except (Document.DoesNotExist, ValueError):
                            errors[field_name] = f"Invalid {field.get('label', field_name)} selection"
                    if field.get('required') and not names:
                        errors[field_name] = f"{field.get('label', field_name)} is required"
                    elif field_name not in errors:
                        data[field_name] = names
                        multi_link_fields_data[field_name] = ids
                else:
                    if field.get('required') and not selected:
                        errors[field_name] = f"{field.get('label', field_name)} is required"
                    else:
                        data[field_name] = selected
                continue

            field_value = request.POST.get(field_name, '').strip()

            # Check required fields
            if field.get('required') and not field_value:
                errors[field_name] = f"{field.get('label', field_name)} is required"
                continue

            # Skip empty optional fields
            if not field_value:
                continue

            # Type conversion and validation
            try:
                if field_type == 'link':
                    # Store link field for later processing
                    link_fields_data[field_name] = field_value
                    # Get linked document name for JSON storage
                    try:
                        linked_doc = Document.objects.get(id=int(field_value))
                        data[field_name] = linked_doc.name
                    except (Document.DoesNotExist, ValueError):
                        errors[field_name] = f"Invalid {field.get('label', field_name)} selection"
                elif field_type == 'integer':
                    data[field_name] = int(field_value) if field_value else None
                elif field_type == 'decimal':
                    data[field_name] = str(Decimal(field_value)) if field_value else None
                elif field_type == 'boolean':
                    data[field_name] = field_value.lower() in ['true', '1', 'yes', 'on']
                elif field_type == 'json':
                    data[field_name] = json.loads(field_value) if field_value else None
                elif field_type == 'table':
                    rows = validate_table(field, field_value)
                    if field.get('required') and not rows:
                        errors[field_name] = f"{field.get('label', field_name)} requires at least one row"
                    else:
                        data[field_name] = rows
                else:
                    data[field_name] = field_value
            except (ValueError, json.JSONDecodeError) as e:
                errors[field_name] = f"Invalid {field_type} value"
            except ChildTableError as e:
                errors[field_name] = str(e)

        if not errors:
            # Generate document name
            name = data.get('name') or data.get(fields[0]['name']) if fields else 'NEW'

            # Create document (firing before/after insert + save hooks)
            document = Document(
                doctype=doctype,
                name=str(name),
                data=data,
                created_by=request.user
            )
            try:
                HookService.save_with_hooks(document, user=request.user, is_new=True)
            except HookError as e:
                messages.error(request, f'Document not created: {e}')
                return render(request, 'doctypes/document_form.html', {
                    'doctype': doctype, 'fields': fields, 'action': 'Create',
                    'submit_url': request.path, 'link_field_options': link_field_options,
                })

            # Initialize workflow if doctype has one
            try:
                WorkflowService.initialize_workflow(document, user=request.user)
            except WorkflowError as e:
                messages.warning(request, f'Workflow could not be initialized: {e}')

            # Create DocumentLink entries for link fields
            for field_name, doc_id in link_fields_data.items():
                try:
                    target_doc = Document.objects.get(id=int(doc_id))
                    DocumentLink.objects.create(
                        source_document=document,
                        target_document=target_doc,
                        field_name=field_name,
                        created_by=request.user
                    )
                except (Document.DoesNotExist, ValueError):
                    pass  # Already validated above

            # Create DocumentLinkMultiple entries for many-to-many fields
            _sync_multi_links(document, multi_link_fields_data)

            messages.success(request, f'{doctype.name} "{document.name}" created successfully!')
            return redirect('document_list', doctype_slug=doctype_slug)
        else:
            for field_name, error in errors.items():
                messages.error(request, error)

    context = {
        'doctype': doctype,
        'fields': fields,
        'action': 'Create',
        'submit_url': request.path,
        'link_field_options': link_field_options,
    }

    return render(request, 'doctypes/document_form.html', context)


@login_required
def document_edit(request, doctype_slug, document_id):
    """Edit an existing document with dynamic form"""
    from .models import DocumentLink

    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    document = get_object_or_404(Document, id=document_id, doctype=doctype)

    # Reading the form requires 'read'; saving requires 'write'.
    _require_doctype_perm(request, doctype, 'read', document=document)
    if request.method == 'POST':
        _require_doctype_perm(request, doctype, 'write', document=document)

    fields = doctype.schema.get('fields', [])
    hidden_fields, readonly_fields = get_field_restrictions(request.user, doctype)
    fields = [
        {**f, 'readonly': True} if f['name'] in readonly_fields else f
        for f in fields
        if f['name'] not in hidden_fields
    ]

    # Check workflow editability
    can_edit, edit_reason = WorkflowService.can_edit_document(document)

    # Get available documents for link fields
    link_field_options = {}
    for field in fields:
        # 'link' (single) and 'multiselect' with a link_doctype (many-to-many)
        # both pick from the target doctype's documents.
        if field['type'] in ('link', 'multiselect') and field.get('link_doctype'):
            link_doctype_name = field.get('link_doctype')
            try:
                link_doctype = Doctype.objects.get(name=link_doctype_name, is_active=True)
                link_field_options[field['name']] = Document.objects.filter(
                    doctype=link_doctype,
                    is_deleted=False
                ).order_by('name')
            except Doctype.DoesNotExist:
                link_field_options[field['name']] = []

    if request.method == 'POST' and not can_edit:
        messages.error(request, edit_reason)
        return redirect('document_edit', doctype_slug=doctype_slug, document_id=document_id)

    if request.method == 'POST':
        # Start from existing data so hidden/read-only fields (and any keys not
        # in the schema) are preserved rather than wiped on save.
        data = dict(document.data or {})
        errors = {}
        link_fields_data = {}  # Store link field values separately
        multi_link_fields_data = {}  # field_name -> [target document ids]

        for field in fields:
            field_name = field['name']
            field_type = field['type']
            # Never accept values for read-only fields, even if posted.
            if field_name in readonly_fields:
                continue

            # Multiselect: many-to-many document link (with link_doctype) or a
            # plain list of static option values. Uses getlist for multi-values.
            if field_type == 'multiselect':
                selected = request.POST.getlist(field_name)
                if field.get('link_doctype'):
                    names = []
                    ids = []
                    for val in selected:
                        try:
                            target = Document.objects.get(id=int(val))
                            names.append(target.name)
                            ids.append(target.id)
                        except (Document.DoesNotExist, ValueError):
                            errors[field_name] = f"Invalid {field.get('label', field_name)} selection"
                    if field.get('required') and not names:
                        errors[field_name] = f"{field.get('label', field_name)} is required"
                    elif field_name not in errors:
                        data[field_name] = names
                        multi_link_fields_data[field_name] = ids
                else:
                    if field.get('required') and not selected:
                        errors[field_name] = f"{field.get('label', field_name)} is required"
                    else:
                        data[field_name] = selected
                continue

            field_value = request.POST.get(field_name, '').strip()

            # Check required fields
            if field.get('required') and not field_value:
                errors[field_name] = f"{field.get('label', field_name)} is required"
                continue

            # Clear emptied optional fields
            if not field_value:
                data.pop(field_name, None)
                continue

            # Type conversion and validation
            try:
                if field_type == 'link':
                    # Store link field for later processing
                    link_fields_data[field_name] = field_value
                    # Get linked document name for JSON storage
                    try:
                        linked_doc = Document.objects.get(id=int(field_value))
                        data[field_name] = linked_doc.name
                    except (Document.DoesNotExist, ValueError):
                        errors[field_name] = f"Invalid {field.get('label', field_name)} selection"
                elif field_type == 'integer':
                    data[field_name] = int(field_value) if field_value else None
                elif field_type == 'decimal':
                    data[field_name] = str(Decimal(field_value)) if field_value else None
                elif field_type == 'boolean':
                    data[field_name] = field_value.lower() in ['true', '1', 'yes', 'on']
                elif field_type == 'json':
                    data[field_name] = json.loads(field_value) if field_value else None
                elif field_type == 'table':
                    rows = validate_table(field, field_value)
                    if field.get('required') and not rows:
                        errors[field_name] = f"{field.get('label', field_name)} requires at least one row"
                    else:
                        data[field_name] = rows
                else:
                    data[field_name] = field_value
            except (ValueError, json.JSONDecodeError) as e:
                errors[field_name] = f"Invalid {field_type} value"
            except ChildTableError as e:
                errors[field_name] = str(e)

        if not errors:
            # Update document (firing before/after save hooks)
            document.data = data
            document.modified_by = request.user  # Track who modified the document
            try:
                HookService.save_with_hooks(document, user=request.user, is_new=False)
            except HookError as e:
                messages.error(request, f'Document not saved: {e}')
                return redirect('document_edit', doctype_slug=doctype_slug, document_id=document_id)

            # Update DocumentLink entries for link fields
            # First, remove old links
            for field_name in link_fields_data.keys():
                document.outgoing_links.filter(field_name=field_name).delete()

            # Then create new links
            for field_name, doc_id in link_fields_data.items():
                try:
                    target_doc = Document.objects.get(id=int(doc_id))
                    DocumentLink.objects.create(
                        source_document=document,
                        target_document=target_doc,
                        field_name=field_name,
                        created_by=request.user
                    )
                except (Document.DoesNotExist, ValueError):
                    pass  # Already validated above

            # Replace many-to-many links for the submitted multiselect fields
            for field_name in multi_link_fields_data.keys():
                document.multi_links_out.filter(field_name=field_name).delete()
            _sync_multi_links(document, multi_link_fields_data)

            messages.success(request, f'{doctype.name} "{document.name}" updated successfully!')
            return redirect('document_list', doctype_slug=doctype_slug)
        else:
            for field_name, error in errors.items():
                messages.error(request, error)

    # Workflow context
    workflow_state = WorkflowService.get_document_workflow_state(document)
    available_transitions = WorkflowService.get_available_transitions(document, request.user) if workflow_state else []
    transition_history = WorkflowService.get_transition_history(document) if workflow_state else []

    context = {
        'doctype': doctype,
        'document': document,
        'fields': fields,
        'action': 'Edit',
        'submit_url': request.path,
        'link_field_options': link_field_options,
        'can_edit': can_edit,
        'edit_reason': edit_reason,
        'workflow_state': workflow_state,
        'available_transitions': available_transitions,
        'transition_history': transition_history,
    }

    return render(request, 'doctypes/document_form.html', context)


@login_required
@require_http_methods(["POST"])
def document_transition(request, doctype_slug, document_id):
    """Perform a workflow transition from the HTML UI."""
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    document = get_object_or_404(Document, id=document_id, doctype=doctype)
    # Read to reach the document; the workflow's own role checks authorize
    # the actual transition inside WorkflowService.perform_transition.
    _require_doctype_perm(request, doctype, 'read', document=document)

    transition_id = request.POST.get('transition_id')
    comment = request.POST.get('comment', '')

    try:
        WorkflowService.perform_transition(
            document=document,
            transition_id=int(transition_id),
            user=request.user,
            comment=comment,
        )
        messages.success(request, 'Workflow transition completed successfully.')
    except (WorkflowError, ValueError, TypeError) as e:
        messages.error(request, str(e))

    return redirect('document_edit', doctype_slug=doctype_slug, document_id=document_id)


@login_required
@require_http_methods(["POST"])
def document_delete(request, doctype_slug, document_id):
    """Delete a document"""
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    document = get_object_or_404(Document, id=document_id, doctype=doctype)
    _require_doctype_perm(request, doctype, 'delete', document=document)

    # Check workflow editability
    can_edit, edit_reason = WorkflowService.can_edit_document(document)
    if not can_edit:
        messages.error(request, f'Cannot delete: {edit_reason}')
        return redirect('document_list', doctype_slug=doctype_slug)

    document_name = document.name
    try:
        HookService.delete_with_hooks(document, user=request.user)
    except HookError as e:
        messages.error(request, f'Document not deleted: {e}')
        return redirect('document_list', doctype_slug=doctype_slug)

    messages.success(request, f'{doctype.name} "{document_name}" deleted successfully!')
    return redirect('document_list', doctype_slug=doctype_slug)


# --- Workflow API Endpoints ---

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_workflow_state(request, document_id):
    """Get the current workflow state and available transitions for a document."""
    document = get_object_or_404(Document, id=document_id)
    if not has_doctype_permission(request.user, document.doctype, 'read'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    dws = WorkflowService.get_document_workflow_state(document)
    if not dws:
        return Response(
            {'detail': 'No workflow active for this document.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    serializer = DocumentWorkflowStateSerializer(dws, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_perform_transition(request, document_id):
    """Perform a workflow transition on a document."""
    document = get_object_or_404(Document, id=document_id)
    # Reaching the document requires read; the transition itself is authorized
    # by the workflow's own role checks in WorkflowService.perform_transition.
    if not has_doctype_permission(request.user, document.doctype, 'read'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    serializer = PerformTransitionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        dws = WorkflowService.perform_transition(
            document=document,
            transition_id=serializer.validated_data['transition_id'],
            user=request.user,
            comment=serializer.validated_data.get('comment', ''),
        )
    except WorkflowError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        DocumentWorkflowStateSerializer(dws, context={'request': request}).data
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_workflow_history(request, document_id):
    """Get the workflow transition history for a document."""
    document = get_object_or_404(Document, id=document_id)
    if not has_doctype_permission(request.user, document.doctype, 'read'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    logs = WorkflowService.get_transition_history(document)
    serializer = WorkflowTransitionLogSerializer(logs, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_submit(request, document_id):
    """Submit a document (docstatus 0 -> 1)."""
    document = get_object_or_404(Document, id=document_id)
    if not has_doctype_permission(request.user, document.doctype, 'submit'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        document = WorkflowService.submit_document(document, request.user)
    except (WorkflowError, HookError) as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': 'Document submitted.', 'docstatus': document.docstatus})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_cancel(request, document_id):
    """Cancel a submitted document (docstatus 1 -> 2)."""
    document = get_object_or_404(Document, id=document_id)
    if not has_doctype_permission(request.user, document.doctype, 'cancel'):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        document = WorkflowService.cancel_document(document, request.user)
    except WorkflowError as e:
        return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': 'Document cancelled.', 'docstatus': document.docstatus})
