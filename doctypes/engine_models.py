"""
Extended models for the Doctype Engine
Includes: Permissions, Workflows, Versioning, Naming Series, Hooks
"""
from django.db import models
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from .models import Doctype, Document


class DoctypePermission(models.Model):
    """
    Role-based permissions for doctypes.
    Similar to Frappe's permission system but more flexible.
    """
    PERMISSION_CHOICES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('write', 'Write'),
        ('delete', 'Delete'),
        ('submit', 'Submit'),
        ('cancel', 'Cancel'),
        ('amend', 'Amend'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('share', 'Share'),
    ]

    doctype = models.ForeignKey(Doctype, on_delete=models.CASCADE, related_name='permissions')
    role = models.ForeignKey(Group, on_delete=models.CASCADE)

    # Permissions
    can_create = models.BooleanField(default=False)
    can_read = models.BooleanField(default=True)
    can_write = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_submit = models.BooleanField(default=False)
    can_cancel = models.BooleanField(default=False)
    can_export = models.BooleanField(default=False)
    can_import = models.BooleanField(default=False)

    # Conditional permissions
    permission_condition = models.TextField(blank=True, help_text="Python expression for conditional access")
    apply_user_permissions = models.BooleanField(default=True)

    # Field-level permissions
    read_only_fields = models.JSONField(default=list, blank=True)
    hidden_fields = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['doctype', 'role']
        ordering = ['doctype', 'role']

    def __str__(self):
        return f"{self.doctype.name} - {self.role.name}"


class DocumentVersion(models.Model):
    """
    Tracks all changes to documents for audit trail.
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()

    data_snapshot = models.JSONField(help_text="Complete data at this version")
    changes = models.JSONField(help_text="What changed from previous version")

    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = ['document', 'version_number']
        indexes = [
            models.Index(fields=['document', '-version_number']),
        ]

    def __str__(self):
        return f"{self.document} v{self.version_number}"


class Workflow(models.Model):
    """
    Defines workflows for doctypes (state machines).
    Innovation: Visual workflow designer support.
    """
    name = models.CharField(max_length=255, unique=True)
    doctype = models.ForeignKey(Doctype, on_delete=models.CASCADE, related_name='workflows')
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    workflow_data = models.JSONField(help_text="Workflow definition with states and transitions")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.doctype.name})"


class WorkflowState(models.Model):
    """
    States in a workflow.
    """
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='states')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    is_initial = models.BooleanField(default=False)
    is_final = models.BooleanField(default=False)
    is_success = models.BooleanField(default=False)

    color = models.CharField(max_length=7, default='#3498db')
    position_x = models.IntegerField(default=0, help_text="X position in visual designer")
    position_y = models.IntegerField(default=0, help_text="Y position in visual designer")

    class Meta:
        unique_together = ['workflow', 'name']

    def __str__(self):
        return f"{self.workflow.name}: {self.name}"


class WorkflowTransition(models.Model):
    """
    Transitions between workflow states.
    """
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name='transitions')
    from_state = models.ForeignKey(WorkflowState, on_delete=models.CASCADE, related_name='transitions_from')
    to_state = models.ForeignKey(WorkflowState, on_delete=models.CASCADE, related_name='transitions_to')

    label = models.CharField(max_length=255)
    condition = models.TextField(blank=True, help_text="Python expression for conditional transition")

    allowed_roles = models.ManyToManyField(Group, blank=True)
    require_comment = models.BooleanField(default=False)

    # Actions on transition
    actions = models.JSONField(default=list, help_text="Actions to execute on transition")

    class Meta:
        unique_together = ['workflow', 'from_state', 'to_state']

    def __str__(self):
        return f"{self.from_state.name} → {self.to_state.name}"


class DocumentWorkflowState(models.Model):
    """
    Tracks workflow state for documents.
    """
    document = models.OneToOneField(Document, on_delete=models.CASCADE, related_name='workflow_state')
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE)
    current_state = models.ForeignKey(WorkflowState, on_delete=models.CASCADE)

    state_changed_at = models.DateTimeField(auto_now=True)
    state_changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['workflow', 'current_state']),
        ]

    def __str__(self):
        return f"{self.document} - {self.current_state.name}"


class NamingSeries(models.Model):
    """
    Manages auto-numbering for documents.
    """
    doctype = models.ForeignKey(Doctype, on_delete=models.CASCADE, related_name='naming_series')
    series_name = models.CharField(max_length=255)
    prefix = models.CharField(max_length=100)
    current_value = models.IntegerField(default=0)
    padding = models.IntegerField(default=4, help_text="Number of digits")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['doctype', 'series_name']
        ordering = ['doctype', 'series_name']

    def __str__(self):
        return f"{self.doctype.name}: {self.series_name}"

    def get_next_value(self):
        """Get the next number in this series"""
        self.current_value += 1
        self.save()
        return f"{self.prefix}{str(self.current_value).zfill(self.padding)}"


class DoctypeHook(models.Model):
    """
    Event hooks for doctypes.
    Innovation: Webhooks + Python hooks in one system.
    """
    HOOK_TYPES = [
        ('before_insert', 'Before Insert'),
        ('after_insert', 'After Insert'),
        ('before_save', 'Before Save'),
        ('after_save', 'After Save'),
        ('before_submit', 'Before Submit'),
        ('after_submit', 'After Submit'),
        ('before_delete', 'Before Delete'),
        ('after_delete', 'After Delete'),
        ('on_change', 'On Field Change'),
    ]

    ACTION_TYPES = [
        ('python', 'Python Code'),
        ('webhook', 'Webhook'),
        ('email', 'Send Email'),
        ('notification', 'System Notification'),
    ]

    doctype = models.ForeignKey(Doctype, on_delete=models.CASCADE, related_name='hooks')
    hook_type = models.CharField(max_length=50, choices=HOOK_TYPES)
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)

    # For Python hooks
    python_code = models.TextField(blank=True, help_text="Python code to execute")

    # For webhooks
    webhook_url = models.URLField(blank=True)
    webhook_headers = models.JSONField(default=dict, blank=True)

    # For email
    email_template = models.TextField(blank=True)
    email_recipients = models.JSONField(default=list, blank=True)

    # Conditions
    condition = models.TextField(blank=True, help_text="When to trigger this hook")

    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['doctype', 'hook_type', 'order']

    def __str__(self):
        return f"{self.doctype.name} - {self.hook_type}"


class CustomField(models.Model):
    """
    Add custom fields to existing doctypes at runtime.
    Innovation: No schema migration needed.
    """
    doctype = models.ForeignKey(Doctype, on_delete=models.CASCADE, related_name='custom_fields')
    fieldname = models.CharField(max_length=255)
    label = models.CharField(max_length=255)
    fieldtype = models.CharField(max_length=50)

    options = models.JSONField(default=dict, help_text="Field-specific options")
    default_value = models.TextField(blank=True)

    insert_after = models.CharField(max_length=255, blank=True, help_text="Field to insert after")
    is_required = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    is_readonly = models.BooleanField(default=False)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['doctype', 'fieldname']
        ordering = ['doctype', 'insert_after']

    def __str__(self):
        return f"{self.doctype.name}.{self.fieldname}"


class Report(models.Model):
    """
    Custom reports and dashboards.
    Innovation: Query builder + SQL + Python.
    """
    REPORT_TYPES = [
        ('query', 'Query Builder'),
        ('sql', 'SQL Query'),
        ('python', 'Python Script'),
    ]

    name = models.CharField(max_length=255, unique=True)
    doctype = models.ForeignKey(Doctype, on_delete=models.CASCADE, related_name='reports')
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)

    description = models.TextField(blank=True)
    query = models.TextField(help_text="Query definition")

    columns = models.JSONField(default=list, help_text="Column definitions")
    filters = models.JSONField(default=list, help_text="Available filters")

    is_public = models.BooleanField(default=False)
    allowed_roles = models.ManyToManyField(Group, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
