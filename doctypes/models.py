from django.db import models
from django.contrib.auth.models import Group
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.db.models import Q
import json
from datetime import datetime


class Module(models.Model):
    """
    Modules organize doctypes into logical groups (like HR, CRM, Accounting).
    Similar to Frappe's module system but with enhanced features.
    """
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True, help_text="Icon class or emoji")
    color = models.CharField(max_length=7, default='#3498db', help_text="Hex color code")

    parent_module = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='submodules'
    )

    order = models.IntegerField(default=0, help_text="Display order")
    is_active = models.BooleanField(default=True)
    is_custom = models.BooleanField(default=True, help_text="Custom vs system module")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_modules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['slug', 'is_active']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_all_doctypes(self):
        """Get all doctypes in this module including submodules"""
        doctypes = list(self.doctypes.all())
        for submodule in self.submodules.all():
            doctypes.extend(submodule.get_all_doctypes())
        return doctypes


class Doctype(models.Model):
    """
    Enhanced Doctype with module support, permissions, workflows, and advanced features.
    Inspired by Frappe but with modern innovations.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    # Basic Info
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctypes')

    # Schema & Configuration
    schema = models.JSONField(help_text="JSON schema definition with fields, permissions, hooks")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Features
    is_submittable = models.BooleanField(default=False, help_text="Can documents be submitted/approved")
    is_single = models.BooleanField(default=False, help_text="Single doctype (only one document)")
    is_child = models.BooleanField(default=False, help_text="Child table doctype")
    is_tree = models.BooleanField(default=False, help_text="Tree/hierarchical structure")

    # Naming
    naming_rule = models.CharField(max_length=255, blank=True, help_text="e.g., {module}-{####}")
    autoname = models.CharField(max_length=50, blank=True, choices=[
        ('prompt', 'Prompt User'),
        ('autoincrement', 'Auto Increment'),
        ('field', 'Based on Field'),
        ('expression', 'Expression'),
        ('uuid', 'UUID'),
    ], default='autoincrement')

    # Permissions & Security
    has_permissions = models.BooleanField(default=True)
    track_changes = models.BooleanField(default=True, help_text="Version history")
    track_views = models.BooleanField(default=False)

    # UI Customization
    icon = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=7, blank=True)
    title_field = models.CharField(max_length=255, blank=True, help_text="Field to use as document title")

    # Metadata
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_doctypes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_custom = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug', 'status']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        # Initialize schema with empty fields if not set
        if not self.schema:
            self.schema = {'fields': []}
        elif isinstance(self.schema, dict) and 'fields' not in self.schema:
            self.schema['fields'] = []

        self.validate_schema()
        super().save(*args, **kwargs)

    def validate_schema(self):
        """Validate the schema structure"""
        if not isinstance(self.schema, dict):
            raise ValidationError("Schema must be a dictionary")

        if 'fields' not in self.schema:
            raise ValidationError("Schema must contain 'fields' key")

        if not isinstance(self.schema['fields'], list):
            raise ValidationError("Schema fields must be a list")

        # Validate each field definition with enhanced types
        valid_types = [
            'string', 'text', 'integer', 'decimal', 'boolean', 'date', 'datetime', 'json',
            'link', 'select', 'multiselect', 'table', 'file', 'image', 'email', 'phone',
            'url', 'color', 'rating', 'currency', 'percent', 'duration', 'computed'
        ]
        for field in self.schema['fields']:
            if 'name' not in field or 'type' not in field:
                raise ValidationError("Each field must have 'name' and 'type'")
            if field['type'] not in valid_types:
                raise ValidationError(f"Invalid field type: {field['type']}")

            # Validate link fields have target doctype
            if field['type'] == 'link' and 'link_doctype' not in field:
                raise ValidationError(f"Link field '{field['name']}' must specify 'link_doctype'")

            # Validate computed fields have formula
            if field['type'] == 'computed' and 'formula' not in field:
                raise ValidationError(f"Computed field '{field['name']}' must have a 'formula'")

    def get_table_name(self):
        """Get the database table name for this doctype"""
        options = self.schema.get('options', {})
        return options.get('table_name', f'dynamic_{self.slug}')

    def get_model_class_name(self):
        """Get the model class name for this doctype"""
        options = self.schema.get('options', {})
        return options.get('class_name', self.name.replace(' ', ''))


class Document(models.Model):
    """
    Enhanced Document model with submission, naming, and workflow support.
    """
    doctype = models.ForeignKey(Doctype, on_delete=models.CASCADE, related_name='documents')
    data = models.JSONField(help_text="Document data conforming to the doctype schema")

    # Naming
    name = models.CharField(max_length=255, blank=True, db_index=True, help_text="Document identifier")

    # Submission workflow
    docstatus = models.IntegerField(default=0, choices=[
        (0, 'Draft'),
        (1, 'Submitted'),
        (2, 'Cancelled'),
    ])
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_documents')
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Hierarchy (for tree doctypes)
    parent_document = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    is_group = models.BooleanField(default=False, help_text="Is this a group/folder")

    # Metadata
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_documents')

    # Versioning
    version_number = models.IntegerField(default=1)

    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_documents')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['doctype', '-created_at']),
        ]

    def __str__(self):
        return f"{self.doctype.name} #{self.pk}"

    def validate_data(self):
        """Validate document data against doctype schema"""
        schema = self.doctype.schema
        fields = schema.get('fields', [])

        for field_config in fields:
            field_name = field_config['name']
            field_type = field_config['type']
            required = field_config.get('required', False)

            # Check required fields
            if required and field_name not in self.data:
                raise ValidationError(f"Field '{field_name}' is required")

            # Type validation (basic)
            if field_name in self.data:
                value = self.data[field_name]
                if field_type == 'integer' and not isinstance(value, int):
                    try:
                        self.data[field_name] = int(value)
                    except (ValueError, TypeError):
                        raise ValidationError(f"Field '{field_name}' must be an integer")

                elif field_type == 'boolean' and not isinstance(value, bool):
                    raise ValidationError(f"Field '{field_name}' must be a boolean")

    def save(self, *args, **kwargs):
        self.validate_data()
        super().save(*args, **kwargs)

    def get_link(self, field_name):
        """Get the linked document for a link field"""
        try:
            link = self.outgoing_links.get(field_name=field_name)
            return link.target_document
        except:
            return None

    def set_link(self, field_name, target_document, user=None):
        """
        Set a link to another document

        Args:
            field_name: Name of the link field
            target_document: Document instance to link to (or None to remove link)
            user: User creating the link
        """
        from .models import DocumentLink

        # Remove existing link if any
        self.outgoing_links.filter(field_name=field_name).delete()

        # Create new link if target provided
        if target_document:
            DocumentLink.objects.create(
                source_document=self,
                target_document=target_document,
                field_name=field_name,
                created_by=user
            )

    def get_linked_documents(self, field_name):
        """Get all documents linked from this document (for multiselect)"""
        return [link.target_document for link in self.multi_links_out.filter(field_name=field_name)]

    def get_child_documents(self):
        """Get all child documents (for table fields)"""
        return self.children.filter(is_deleted=False).order_by('id')

    def get_parent_document(self):
        """Get parent document if this is a child"""
        return self.parent_document

    def get_referencing_documents(self):
        """Get all documents that link to this document"""
        return [link.source_document for link in self.incoming_links.all()]


class DocumentShare(models.Model):
    """
    Track document sharing via email
    """
    SHARE_STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('opened', 'Opened'),
        ('failed', 'Failed'),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='shares')
    shared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shared_documents')
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=255, blank=True)

    personal_message = models.TextField(blank=True)
    share_url = models.URLField(blank=True)

    status = models.CharField(max_length=20, choices=SHARE_STATUS_CHOICES, default='sent')
    sent_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)

    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['document', 'recipient_email']),
            models.Index(fields=['shared_by', '-sent_at']),
        ]

    def __str__(self):
        return f"{self.document} shared with {self.recipient_email}"


class DocumentLink(models.Model):
    """
    Proper database relationship for Link fields
    Enables Many-to-One and One-to-One relationships between documents

    Example: If Order has a 'customer' link field pointing to Customer doctype,
    this model stores that relationship in the database.
    """
    # Source document (the document that has the link field)
    source_document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='outgoing_links',
        help_text="Document that contains the link field"
    )

    # Target document (the document being linked to)
    target_document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,  # Prevent deletion of linked documents
        related_name='incoming_links',
        help_text="Document being linked to"
    )

    # Field information
    field_name = models.CharField(
        max_length=255,
        help_text="Name of the link field in the source document"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_links'
    )

    class Meta:
        ordering = ['source_document', 'field_name']
        indexes = [
            models.Index(fields=['source_document', 'field_name']),
            models.Index(fields=['target_document']),
        ]
        # Ensure one link per field per document
        unique_together = [['source_document', 'field_name']]

    def __str__(self):
        return f"{self.source_document} -> {self.field_name} -> {self.target_document}"

    def save(self, *args, **kwargs):
        """Validate that field exists and is a link field"""
        schema = self.source_document.doctype.schema
        fields = schema.get('fields', [])

        # Find the field in schema
        field_config = next((f for f in fields if f['name'] == self.field_name), None)

        if not field_config:
            raise ValidationError(f"Field '{self.field_name}' does not exist in {self.source_document.doctype.name}")

        if field_config.get('type') != 'link':
            raise ValidationError(f"Field '{self.field_name}' is not a link field")

        # Validate that target document matches the linked doctype
        link_doctype_name = field_config.get('link_doctype')
        if link_doctype_name and self.target_document.doctype.name != link_doctype_name:
            raise ValidationError(
                f"Target document must be of type '{link_doctype_name}', "
                f"got '{self.target_document.doctype.name}'"
            )

        super().save(*args, **kwargs)

        # Update JSON data to include the link
        if self.source_document.data is None:
            self.source_document.data = {}
        self.source_document.data[self.field_name] = self.target_document.name
        self.source_document.save()


class DocumentLinkMultiple(models.Model):
    """
    For handling Many-to-Many relationships (multiselect link fields)

    Example: If Project has 'team_members' multiselect link field pointing to User doctype,
    this model stores multiple user links for one project.
    """
    source_document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='multi_links_out'
    )

    target_document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        related_name='multi_links_in'
    )

    field_name = models.CharField(max_length=255)

    # Order for maintaining sequence
    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['source_document', 'field_name', 'order']
        indexes = [
            models.Index(fields=['source_document', 'field_name']),
            models.Index(fields=['target_document']),
        ]

    def __str__(self):
        return f"{self.source_document} -> {self.field_name}[{self.order}] -> {self.target_document}"

# Import security models for migration
from .security_models import (
    VersionAccessLog,
    SecurityEvent,
    RateLimitLog,
    VersionIntegrityLog,
    DataRetentionLog
)

