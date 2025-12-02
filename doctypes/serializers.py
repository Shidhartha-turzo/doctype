from rest_framework import serializers
from .models import Doctype, Document, DocumentShare


class DoctypeSerializer(serializers.ModelSerializer):
    """Serializer for Doctype model"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Doctype
        fields = [
            'id', 'name', 'slug', 'description', 'schema', 'status',
            'created_by', 'created_by_username', 'created_at', 'updated_at',
            'version', 'is_active'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at', 'created_by']

    def validate_schema(self, value):
        """Validate schema structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Schema must be a dictionary")

        if 'fields' not in value:
            raise serializers.ValidationError("Schema must contain 'fields' key")

        if not isinstance(value['fields'], list):
            raise serializers.ValidationError("Schema fields must be a list")

        # Validate each field
        valid_types = ['string', 'text', 'integer', 'decimal', 'boolean', 'date', 'datetime', 'json']
        for field in value['fields']:
            if 'name' not in field:
                raise serializers.ValidationError("Each field must have a 'name'")
            if 'type' not in field:
                raise serializers.ValidationError("Each field must have a 'type'")
            if field['type'] not in valid_types:
                raise serializers.ValidationError(f"Invalid field type: {field['type']}")

        return value

    def create(self, validated_data):
        # Set created_by from request user
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class DoctypeListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing doctypes"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    field_count = serializers.SerializerMethodField()

    class Meta:
        model = Doctype
        fields = [
            'id', 'name', 'slug', 'description', 'status',
            'created_by_username', 'created_at', 'updated_at',
            'version', 'field_count'
        ]

    def get_field_count(self, obj):
        return len(obj.schema.get('fields', []))


class DynamicDocumentSerializer(serializers.Serializer):
    """Dynamic serializer for documents based on doctype schema"""

    def __init__(self, *args, doctype=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.doctype = doctype

        if doctype:
            # Add fields dynamically based on schema
            for field_config in doctype.schema.get('fields', []):
                field_name = field_config['name']
                field_type = field_config['type']
                required = field_config.get('required', False)

                # Create appropriate serializer field
                if field_type == 'string':
                    self.fields[field_name] = serializers.CharField(
                        required=required,
                        max_length=field_config.get('max_length', 255),
                        allow_blank=not required
                    )
                elif field_type == 'text':
                    self.fields[field_name] = serializers.CharField(
                        required=required,
                        allow_blank=not required
                    )
                elif field_type == 'integer':
                    self.fields[field_name] = serializers.IntegerField(required=required)
                elif field_type == 'decimal':
                    self.fields[field_name] = serializers.DecimalField(
                        required=required,
                        max_digits=field_config.get('max_digits', 10),
                        decimal_places=field_config.get('decimal_places', 2)
                    )
                elif field_type == 'boolean':
                    self.fields[field_name] = serializers.BooleanField(required=required)
                elif field_type == 'date':
                    self.fields[field_name] = serializers.DateField(required=required)
                elif field_type == 'datetime':
                    self.fields[field_name] = serializers.DateTimeField(required=required)
                elif field_type == 'json':
                    self.fields[field_name] = serializers.JSONField(required=required)

    def to_representation(self, instance):
        """Convert Document instance to dict"""
        if isinstance(instance, Document):
            data = {
                'id': instance.pk,
                'created_at': instance.created_at,
                'updated_at': instance.updated_at,
            }
            # Merge the JSON data
            data.update(instance.data)
            return data
        return instance

    def create(self, validated_data):
        """Create a Document instance"""
        from .models import Document
        from decimal import Decimal

        # Convert Decimal to string for JSON serialization
        cleaned_data = {}
        for key, value in validated_data.items():
            if isinstance(value, Decimal):
                cleaned_data[key] = str(value)
            else:
                cleaned_data[key] = value

        document = Document(
            doctype=self.doctype,
            data=cleaned_data,
            created_by=self.context['request'].user
        )
        document.save()
        return document

    def update(self, instance, validated_data):
        """Update a Document instance"""
        instance.data = validated_data
        instance.save()
        return instance


class DocumentShareSerializer(serializers.ModelSerializer):
    """Serializer for document sharing"""
    shared_by_username = serializers.CharField(source='shared_by.username', read_only=True)
    document_name = serializers.CharField(source='document.name', read_only=True)
    doctype_name = serializers.CharField(source='document.doctype.name', read_only=True)

    class Meta:
        model = DocumentShare
        fields = [
            'id', 'document', 'document_name', 'doctype_name',
            'shared_by', 'shared_by_username', 'recipient_email', 'recipient_name',
            'personal_message', 'share_url', 'status',
            'sent_at', 'opened_at'
        ]
        read_only_fields = ['id', 'shared_by', 'status', 'sent_at', 'opened_at']


class BulkShareSerializer(serializers.Serializer):
    """Serializer for bulk document sharing"""
    recipient_emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1,
        max_length=50,
        help_text="List of recipient email addresses (max 50)"
    )
    personal_message = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        help_text="Optional personal message to include in the email"
    )
