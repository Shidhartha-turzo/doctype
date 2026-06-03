import logging

import requests as http_requests
from django.db import transaction
from django.utils import timezone

from .engine_models import (
    DocumentWorkflowState,
    Workflow,
    WorkflowTransitionLog,
)
from .models import Document

logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """Base exception for workflow operations."""
    pass


class _SafeDocProxy:
    """
    Proxy for safe condition evaluation.
    Allows attribute access to document.data fields
    and a few standard document attributes.
    """

    def __init__(self, document):
        self._document = document
        self._data = document.data or {}

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        if name == 'docstatus':
            return self._document.docstatus
        if name == 'name':
            return self._document.name
        if name == 'id':
            return self._document.id
        return None


class WorkflowService:
    """
    Stateless service class for all workflow operations.
    """

    @classmethod
    def get_active_workflow(cls, doctype):
        """Get the active workflow for a doctype, or None."""
        return Workflow.objects.filter(
            doctype=doctype, is_active=True
        ).first()

    @classmethod
    def initialize_workflow(cls, document, user=None):
        """
        Called after document creation. If the doctype has an active
        workflow, creates a DocumentWorkflowState at the initial state.
        Returns DocumentWorkflowState or None.
        """
        workflow = cls.get_active_workflow(document.doctype)
        if not workflow:
            return None

        initial_state = workflow.states.filter(is_initial=True).first()
        if not initial_state:
            raise WorkflowError(
                f"Workflow '{workflow.name}' has no initial state defined."
            )

        dws = DocumentWorkflowState.objects.create(
            document=document,
            workflow=workflow,
            current_state=initial_state,
            state_changed_by=user,
        )

        WorkflowTransitionLog.objects.create(
            document=document,
            workflow=workflow,
            from_state=None,
            to_state=initial_state,
            transition=None,
            performed_by=user,
            comment='Workflow initialized',
        )

        return dws

    @classmethod
    def get_document_workflow_state(cls, document):
        """Returns the DocumentWorkflowState for a document, or None."""
        try:
            return document.workflow_state
        except DocumentWorkflowState.DoesNotExist:
            return None

    @classmethod
    def get_available_transitions(cls, document, user):
        """
        Returns WorkflowTransition objects the user can take right now.
        Checks current state, user roles, and conditions.
        """
        dws = cls.get_document_workflow_state(document)
        if not dws:
            return []

        user_group_ids = set(user.groups.values_list('id', flat=True))

        transitions = dws.workflow.transitions.filter(
            from_state=dws.current_state,
        ).prefetch_related('allowed_roles')

        available = []
        for t in transitions:
            allowed_role_ids = set(
                t.allowed_roles.values_list('id', flat=True)
            )
            if allowed_role_ids and not (user_group_ids & allowed_role_ids):
                if not user.is_superuser:
                    continue

            if t.condition and t.condition.strip():
                if not cls._evaluate_condition(t.condition, document):
                    continue

            available.append(t)

        return available

    @classmethod
    def perform_transition(cls, document, transition_id, user, comment=''):
        """
        Execute a transition on a document. Validates everything,
        updates state atomically, logs, and fires actions.
        """
        with transaction.atomic():
            try:
                dws = DocumentWorkflowState.objects.select_for_update().get(
                    document=document
                )
            except DocumentWorkflowState.DoesNotExist:
                raise WorkflowError('Document has no active workflow.')

            try:
                transition = dws.workflow.transitions.get(id=transition_id)
            except Exception:
                raise WorkflowError('Transition not found.')

            if transition.from_state_id != dws.current_state_id:
                raise WorkflowError(
                    f"Cannot apply '{transition.label}': document is in "
                    f"state '{dws.current_state.name}', but transition "
                    f"requires '{transition.from_state.name}'."
                )

            # Role check
            allowed_role_ids = set(
                transition.allowed_roles.values_list('id', flat=True)
            )
            if allowed_role_ids:
                user_group_ids = set(
                    user.groups.values_list('id', flat=True)
                )
                if not (user_group_ids & allowed_role_ids) and not user.is_superuser:
                    raise WorkflowError(
                        'You do not have permission for this transition.'
                    )

            # Condition check
            if transition.condition and transition.condition.strip():
                if not cls._evaluate_condition(transition.condition, document):
                    raise WorkflowError('Transition condition not met.')

            # Comment check
            if transition.require_comment and not comment.strip():
                raise WorkflowError(
                    'A comment is required for this transition.'
                )

            old_state = dws.current_state
            dws.current_state = transition.to_state
            dws.state_changed_by = user
            dws.save()

            WorkflowTransitionLog.objects.create(
                document=document,
                workflow=dws.workflow,
                from_state=old_state,
                to_state=transition.to_state,
                transition=transition,
                performed_by=user,
                comment=comment,
            )

        # Execute actions outside transaction
        cls._execute_actions(transition.actions, document, transition, user)

        # Refresh to get updated state
        dws.refresh_from_db()
        return dws

    @classmethod
    def get_transition_history(cls, document):
        """Returns WorkflowTransitionLog queryset for a document."""
        return WorkflowTransitionLog.objects.filter(
            document=document
        ).select_related(
            'from_state', 'to_state', 'transition', 'performed_by'
        ).order_by('-performed_at')

    @classmethod
    def can_edit_document(cls, document):
        """
        Check if a document can be edited based on its workflow state.
        Returns (allowed: bool, reason: str).
        """
        if document.docstatus == 2:
            return (False, 'Cancelled documents cannot be edited.')

        dws = cls.get_document_workflow_state(document)
        if not dws:
            return (True, '')

        if dws.current_state.is_final:
            return (
                False,
                f'Document is in final state "{dws.current_state.name}" and cannot be edited.',
            )

        return (True, '')

    # --- Submit / Cancel ---

    @classmethod
    def submit_document(cls, document, user):
        """Submit a document (docstatus 0 -> 1)."""
        if not document.doctype.is_submittable:
            raise WorkflowError('This doctype is not submittable.')
        if document.docstatus != 0:
            raise WorkflowError('Only draft documents can be submitted.')

        from .hook_engine import HookService

        HookService.run_hooks(document, 'before_submit', user)
        document.docstatus = 1
        document.submitted_by = user
        document.submitted_at = timezone.now()
        document.save()
        HookService.run_hooks(document, 'after_submit', user)
        return document

    @classmethod
    def cancel_document(cls, document, user):
        """Cancel a submitted document (docstatus 1 -> 2)."""
        if not document.doctype.is_submittable:
            raise WorkflowError('This doctype is not submittable.')
        if document.docstatus != 1:
            raise WorkflowError('Only submitted documents can be cancelled.')

        document.docstatus = 2
        document.save()
        return document

    # --- Private helpers ---

    @classmethod
    def _evaluate_condition(cls, condition_str, document):
        """
        Safely evaluate a condition string against document data.
        Uses _SafeDocProxy with no builtins. Returns False on error.
        """
        try:
            safe_ns = {
                'doc': _SafeDocProxy(document),
                'True': True,
                'False': False,
                'None': None,
            }
            result = eval(condition_str, {'__builtins__': {}}, safe_ns)
            return bool(result)
        except Exception as e:
            logger.warning(
                f"Condition evaluation failed for '{condition_str}': {e}"
            )
            return False

    @classmethod
    def _execute_actions(cls, actions, document, transition, user):
        """Execute transition actions (webhook, email). Skips python."""
        if not actions:
            return

        for action in actions:
            action_type = action.get('type', '')
            try:
                if action_type == 'webhook':
                    cls._execute_webhook(action, document)
                elif action_type == 'email':
                    cls._execute_email(action, document, transition, user)
                elif action_type == 'python':
                    logger.info('Skipping python action for security.')
                else:
                    logger.warning(f'Unknown action type: {action_type}')
            except Exception as e:
                logger.error(f'Action execution failed ({action_type}): {e}')

    @classmethod
    def _execute_webhook(cls, action, document):
        """POST to webhook URL with document data."""
        url = action.get('url', '')
        if not url:
            return

        headers = action.get('headers', {})
        payload = {
            'document_id': document.id,
            'document_name': document.name,
            'doctype': document.doctype.name,
            'data': document.data,
            'event': 'workflow_transition',
        }

        try:
            resp = http_requests.post(url, json=payload, headers=headers, timeout=10)
            logger.info(f'Webhook {url} returned {resp.status_code}')
        except http_requests.RequestException as e:
            logger.error(f'Webhook failed: {e}')

    @classmethod
    def _execute_email(cls, action, document, transition, user):
        """Send email notification via EmailService."""
        from core.email_service import EmailService

        recipients = action.get('to', [])
        if isinstance(recipients, str):
            recipients = [recipients]
        if not recipients:
            return

        subject = action.get(
            'subject',
            f"Workflow update: {document.name} - {transition.label}"
        )
        message = action.get(
            'template',
            f"Document '{document.name}' has been moved to "
            f"state '{transition.to_state.name}' "
            f"by {user.get_full_name() or user.username}."
        )

        try:
            from django.core.mail import send_mail as django_send_mail
            django_send_mail(
                subject, message, None, recipients, fail_silently=True
            )
        except Exception as e:
            logger.error(f'Email action failed: {e}')
