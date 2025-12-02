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
from .models import Doctype, Document
from .serializers import DoctypeSerializer, DoctypeListSerializer, DynamicDocumentSerializer
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
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    fields = doctype.schema.get('fields', [])

    if request.method == 'POST':
        # Collect and validate form data
        data = {}
        errors = {}

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
                if field_type == 'integer':
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
    }

    return render(request, 'doctypes/document_form.html', context)


@login_required
def document_edit(request, doctype_slug, document_id):
    """Edit an existing document with dynamic form"""
    doctype = get_object_or_404(Doctype, slug=doctype_slug, is_active=True)
    document = get_object_or_404(Document, id=document_id, doctype=doctype)
    fields = doctype.schema.get('fields', [])

    if request.method == 'POST':
        # Collect and validate form data
        data = {}
        errors = {}

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
                if field_type == 'integer':
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
            document.save()

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
