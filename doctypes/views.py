from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from .models import Doctype, Document
from .serializers import DoctypeSerializer, DoctypeListSerializer, DynamicDocumentSerializer


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
