from django.contrib import admin
from .models import Doctype, Document, Module
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


@admin.register(Doctype)
class DoctypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'module', 'status', 'is_submittable', 'track_changes', 'version', 'is_active']
    list_filter = ['status', 'module', 'is_active', 'is_submittable', 'is_single', 'is_child', 'track_changes']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['slug', 'created_at', 'updated_at']
    list_editable = ['status', 'is_active']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'doctype', 'docstatus', 'created_by', 'created_at', 'version_number']
    list_filter = ['doctype', 'docstatus', 'is_deleted', 'created_at']
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
