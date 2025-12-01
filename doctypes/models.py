from django.db import models
from django.contrib.auth.models import User, Group
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

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_modules')
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
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_doctypes')
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
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_documents')
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Hierarchy (for tree doctypes)
    parent_document = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    is_group = models.BooleanField(default=False, help_text="Is this a group/folder")

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='modified_documents')

    # Versioning
    version_number = models.IntegerField(default=1)

    # Soft delete
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_documents')

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
