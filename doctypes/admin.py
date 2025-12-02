from django.contrib import admin
from django.urls import path, re_path, reverse
from django.shortcuts import get_object_or_404, redirect
from django.utils.html import format_html
from django.template.response import TemplateResponse
from django import forms
import json
from .models import Doctype, Document, Module, DocumentShare, DocumentLink, DocumentLinkMultiple
from .engine_models import (
    DoctypePermission, DocumentVersion, Workflow, WorkflowState, WorkflowTransition,
    DocumentWorkflowState, NamingSeries, DoctypeHook, CustomField, Report
)


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent_module', 'order', 'is_active', 'is_custom', 'created_at']
    list_filter = ['is_active', 'is_custom', 'parent_module']
    search_fields = ['name', 'description']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    list_editable = ['order', 'is_active']


class DoctypeAdminForm(forms.ModelForm):
    """Custom form for Doctype with visual field builder"""

    class Meta:
        model = Doctype
        fields = '__all__'
        widgets = {
            'schema': forms.HiddenInput(),  # Hide the raw JSON field
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # For new instances, set initial values
        if not self.instance.pk:
            # Initialize schema with empty fields array if not set
            if not self.initial.get('schema'):
                self.initial['schema'] = {'fields': []}

            # Set default values from model
            if not self.initial.get('status'):
                self.initial['status'] = 'draft'
            if not self.initial.get('version'):
                self.initial['version'] = 1

        # Make slug not required in form since it's auto-generated
        if 'slug' in self.fields:
            self.fields['slug'].required = False

        # Make created_by not required since it's auto-set
        if 'created_by' in self.fields:
            self.fields['created_by'].required = False

    def clean(self):
        cleaned_data = super().clean()
        # Ensure schema is initialized
        if not cleaned_data.get('schema'):
            cleaned_data['schema'] = {'fields': []}
        return cleaned_data


@admin.register(Doctype)
class DoctypeAdmin(admin.ModelAdmin):
    form = DoctypeAdminForm
    list_display = ['name', 'slug', 'module', 'status', 'created_by', 'created_at', 'updated_at', 'version', 'is_active', 'view_link']
    list_filter = ['status', 'module', 'is_active', 'is_submittable', 'is_single', 'is_child', 'track_changes', 'created_by']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['slug', 'version', 'created_at', 'updated_at', 'api_link_button']
    list_editable = ['status', 'is_active']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'module', 'icon', 'color', 'api_link_button')
        }),
        ('Type & Features', {
            'fields': ('is_submittable', 'is_single', 'is_child', 'is_tree', 'track_changes', 'track_views')
        }),
        ('Naming', {
            'fields': ('naming_rule', 'autoname', 'title_field')
        }),
        ('Permissions & Security', {
            'fields': ('has_permissions', 'status')
        }),
        ('Schema (JSON)', {
            'fields': ('schema',),
            'classes': ('collapse',),
            'description': 'Raw JSON schema - use the visual field builder below instead'
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'version', 'is_active', 'is_custom'),
            'classes': ('collapse',)
        }),
    )

    class Media:
        css = {
            'all': ('admin/css/doctype_builder.css',)
        }
        js = ('admin/js/doctype_builder.js',)

    def view_link(self, obj):
        """Add a link to view the doctype by slug"""
        if obj.slug:
            url = reverse('admin:doctypes_doctype_change_by_slug', args=[obj.slug])
            return format_html('<a href="{}" target="_blank">View by Slug</a>', url)
        return '-'
    view_link.short_description = 'Actions'

    def api_link_button(self, obj):
        """Add a button to view the API endpoint for this doctype"""
        if obj.slug:
            api_url = f'/api/core/{obj.slug}/'
            return format_html(
                '<a href="{}" target="_blank" class="button" style="padding: 8px 12px; background-color: #417690; color: white; text-decoration: none; border-radius: 4px; display: inline-block;">'
                '📡 View API Endpoint'
                '</a>',
                api_url
            )
        return '-'
    api_link_button.short_description = 'API Endpoint'

    def get_urls(self):
        """Add custom URL patterns for slug-based access"""
        urls = super().get_urls()
        custom_urls = [
            # Use regex to match slugs that are NOT pure numbers
            # This prevents interference with ID-based URLs
            re_path(
                r'^(?P<slug>[a-z][a-z0-9_-]*)/change/$',
                self.admin_site.admin_view(self.change_view_by_slug),
                name='doctypes_doctype_change_by_slug',
            ),
            re_path(
                r'^(?P<slug>[a-z][a-z0-9_-]*)/delete/$',
                self.admin_site.admin_view(self.delete_view_by_slug),
                name='doctypes_doctype_delete_by_slug',
            ),
        ]
        return custom_urls + urls

    def change_view_by_slug(self, request, slug, form_url='', extra_context=None):
        """Handle change view with slug instead of ID"""
        doctype = get_object_or_404(Doctype, slug=slug)
        return self.change_view(request, str(doctype.pk), form_url, extra_context)

    def delete_view_by_slug(self, request, slug, extra_context=None):
        """Handle delete view with slug instead of ID"""
        doctype = get_object_or_404(Doctype, slug=slug)
        return self.delete_view(request, str(doctype.pk), extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Override change view to add field builder context"""
        if extra_context is None:
            extra_context = {}

        if object_id:
            obj = self.get_object(request, object_id)
            if obj:
                # Parse schema fields for visual display
                schema = obj.schema or {}
                fields = schema.get('fields', [])
                field_types = [
                    'string', 'text', 'integer', 'decimal', 'boolean', 'date', 'datetime',
                    'json', 'link', 'select', 'multiselect', 'table', 'file', 'image',
                    'email', 'phone', 'url', 'color', 'rating', 'currency', 'percent',
                    'duration', 'computed'
                ]

                # Get available child doctypes and all doctypes for links
                child_doctypes = list(Doctype.objects.filter(is_child=True, is_active=True).values_list('name', flat=True))
                all_doctypes = list(Doctype.objects.filter(is_active=True).values_list('name', flat=True))

                # Pass both JSON and list versions
                extra_context.update({
                    'doctype_fields_json': json.dumps(fields),
                    'field_types_json': json.dumps(field_types),
                    'field_types': field_types,
                    'child_doctypes_json': json.dumps(child_doctypes),
                    'all_doctypes_json': json.dumps(all_doctypes),
                })

        return super().change_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        """Override save_model to set created_by and handle auto fields"""
        if not change:  # Only on creation
            obj.created_by = request.user
            if not obj.version:
                obj.version = 1
        super().save_model(request, obj, form, change)

    def add_view(self, request, form_url='', extra_context=None):
        """Override add view to add field builder context"""
        if extra_context is None:
            extra_context = {}

        field_types = [
            'string', 'text', 'integer', 'decimal', 'boolean', 'date', 'datetime',
            'json', 'link', 'select', 'multiselect', 'table', 'file', 'image',
            'email', 'phone', 'url', 'color', 'rating', 'currency', 'percent',
            'duration', 'computed'
        ]

        # Get available child doctypes and all doctypes for links
        child_doctypes = list(Doctype.objects.filter(is_child=True, is_active=True).values_list('name', flat=True))
        all_doctypes = list(Doctype.objects.filter(is_active=True).values_list('name', flat=True))

        # Pass both JSON and list versions
        extra_context.update({
            'doctype_fields_json': json.dumps([]),
            'field_types_json': json.dumps(field_types),
            'field_types': field_types,
            'child_doctypes_json': json.dumps(child_doctypes),
            'all_doctypes_json': json.dumps(all_doctypes),
        })

        return super().add_view(request, form_url, extra_context)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'doctype', 'docstatus', 'created_by', 'created_at', 'modified_by', 'updated_at', 'version_number']
    list_filter = ['doctype', 'docstatus', 'is_deleted', 'created_at', 'updated_at', 'modified_by']
    search_fields = ['name', 'data']
    readonly_fields = ['created_at', 'updated_at', 'version_number']


@admin.register(DoctypePermission)
class DoctypePermissionAdmin(admin.ModelAdmin):
    list_display = ['doctype', 'role', 'can_read', 'can_write', 'can_create', 'can_delete', 'can_submit']
    list_filter = ['doctype', 'role']
    list_editable = ['can_read', 'can_write', 'can_create', 'can_delete']


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ['document', 'version_number', 'changed_by', 'changed_at']
    list_filter = ['changed_at']
    readonly_fields = ['version_number', 'data_snapshot', 'changes', 'changed_at']


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ['name', 'doctype', 'is_active', 'created_at']
    list_filter = ['doctype', 'is_active']
    search_fields = ['name', 'description']


@admin.register(WorkflowState)
class WorkflowStateAdmin(admin.ModelAdmin):
    list_display = ['workflow', 'name', 'is_initial', 'is_final', 'is_success', 'color']
    list_filter = ['workflow', 'is_initial', 'is_final']


@admin.register(WorkflowTransition)
class WorkflowTransitionAdmin(admin.ModelAdmin):
    list_display = ['workflow', 'from_state', 'to_state', 'label', 'require_comment']
    list_filter = ['workflow']


@admin.register(DocumentWorkflowState)
class DocumentWorkflowStateAdmin(admin.ModelAdmin):
    list_display = ['document', 'workflow', 'current_state', 'state_changed_at', 'state_changed_by']
    list_filter = ['workflow', 'current_state']


@admin.register(NamingSeries)
class NamingSeriesAdmin(admin.ModelAdmin):
    list_display = ['doctype', 'series_name', 'prefix', 'current_value', 'padding', 'is_active']
    list_filter = ['doctype', 'is_active']
    list_editable = ['is_active']


@admin.register(DoctypeHook)
class DoctypeHookAdmin(admin.ModelAdmin):
    list_display = ['doctype', 'hook_type', 'action_type', 'is_active', 'order']
    list_filter = ['doctype', 'hook_type', 'action_type', 'is_active']
    list_editable = ['is_active', 'order']


@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ['doctype', 'fieldname', 'label', 'fieldtype', 'is_required', 'is_hidden', 'created_by']
    list_filter = ['doctype', 'fieldtype', 'is_required', 'is_hidden']
    search_fields = ['fieldname', 'label']


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['name', 'doctype', 'report_type', 'is_public', 'created_by', 'created_at']
    list_filter = ['doctype', 'report_type', 'is_public']
    search_fields = ['name', 'description']


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    list_display = ['document', 'recipient_email', 'shared_by', 'status', 'sent_at', 'opened_at']
    list_filter = ['status', 'sent_at', 'shared_by']
    search_fields = ['recipient_email', 'recipient_name', 'document__name']
    readonly_fields = ['sent_at', 'opened_at']
    date_hierarchy = 'sent_at'


@admin.register(DocumentLink)
class DocumentLinkAdmin(admin.ModelAdmin):
    list_display = ['source_document', 'field_name', 'target_document', 'created_at', 'created_by']
    list_filter = ['field_name', 'created_at', 'source_document__doctype', 'target_document__doctype']
    search_fields = ['source_document__name', 'target_document__name', 'field_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['source_document', 'target_document', 'created_by']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Link Information', {
            'fields': ('source_document', 'field_name', 'target_document')
        }),
        ('Metadata', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DocumentLinkMultiple)
class DocumentLinkMultipleAdmin(admin.ModelAdmin):
    list_display = ['source_document', 'field_name', 'target_document', 'order', 'created_at']
    list_filter = ['field_name', 'created_at', 'source_document__doctype', 'target_document__doctype']
    search_fields = ['source_document__name', 'target_document__name', 'field_name']
    readonly_fields = ['created_at']
    raw_id_fields = ['source_document', 'target_document']
    list_editable = ['order']
    date_hierarchy = 'created_at'
