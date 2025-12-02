from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Doctype, Document, DocumentShare
from .serializers import (
    DoctypeSerializer, DoctypeListSerializer, DynamicDocumentSerializer,
    DocumentShareSerializer, BulkShareSerializer
)
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
                document = serializer.save()
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
# Dynamic Form Views for Document Management
# ============================================================================

@login_required
def document_list(request, doctype_slug):
    """List all documents for a doctype with dynamic table"""
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    documents = Document.objects.filter(doctype=doctype).order_by('-created_at')

    # Get schema fields
    fields = doctype.schema.get('fields', [])

    context = {
        'doctype': doctype,
        'documents': documents,
        'fields': fields,
        'field_names': [f['name'] for f in fields],
    }

    return render(request, 'doctypes/document_list.html', context)


@login_required
def document_create(request, doctype_slug):
    """Create a new document with dynamic form"""
    from .models import DocumentLink

    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    fields = doctype.schema.get('fields', [])

    # Get available documents for link fields
    link_field_options = {}
    for field in fields:
        if field['type'] == 'link':
            link_doctype_name = field.get('link_doctype')
            if link_doctype_name:
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

        for field in fields:
            field_name = field['name']
            field_type = field['type']
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
                else:
                    data[field_name] = field_value
            except (ValueError, json.JSONDecodeError) as e:
                errors[field_name] = f"Invalid {field_type} value"

        if not errors:
            # Generate document name
            name = data.get('name') or data.get(fields[0]['name']) if fields else 'NEW'

            # Create document
            document = Document.objects.create(
                doctype=doctype,
                name=str(name),
                data=data,
                created_by=request.user
            )

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
    fields = doctype.schema.get('fields', [])

    # Get available documents for link fields
    link_field_options = {}
    for field in fields:
        if field['type'] == 'link':
            link_doctype_name = field.get('link_doctype')
            if link_doctype_name:
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

        for field in fields:
            field_name = field['name']
            field_type = field['type']
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
                else:
                    data[field_name] = field_value
            except (ValueError, json.JSONDecodeError) as e:
                errors[field_name] = f"Invalid {field_type} value"

        if not errors:
            # Update document
            document.data = data
            document.modified_by = request.user  # Track who modified the document
            document.save()

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

            messages.success(request, f'{doctype.name} "{document.name}" updated successfully!')
            return redirect('document_list', doctype_slug=doctype_slug)
        else:
            for field_name, error in errors.items():
                messages.error(request, error)

    context = {
        'doctype': doctype,
        'document': document,
        'fields': fields,
        'action': 'Edit',
        'submit_url': request.path,
        'link_field_options': link_field_options,
    }

    return render(request, 'doctypes/document_form.html', context)


@login_required
@require_http_methods(["POST"])
def document_delete(request, doctype_slug, document_id):
    """Delete a document"""
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    document = get_object_or_404(Document, id=document_id, doctype=doctype)

    document_name = document.name
    document.delete()

    messages.success(request, f'{doctype.name} "{document_name}" deleted successfully!')
    return redirect('document_list', doctype_slug=doctype_slug)
