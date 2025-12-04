"""
Workflow Execution Engine

Handles workflow state transitions, permissions, validations, and actions.
"""

from typing import Optional, List, Dict, Any
from django.db import transaction
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
import logging

from .engine_models import (
    Workflow, WorkflowState, WorkflowTransition,
    DocumentWorkflowState, Document
)
from core.email_service import EmailService

logger = logging.getLogger(__name__)


class WorkflowException(Exception):
    """Base exception for workflow errors"""
    pass


class WorkflowTransitionDenied(PermissionDenied):
    """Raised when a workflow transition is not allowed"""
    pass


class WorkflowEngine:
    """
    Workflow execution engine that handles state transitions,
    permissions, validations, and notifications.
    """

    def __init__(self, document: Document, user=None):
        """
        Initialize workflow engine for a document

        Args:
            document: Document instance
            user: User performing the action
        """
        self.document = document
        self.user = user
        self.email_service = EmailService()

    def get_workflow(self) -> Optional[Workflow]:
        """Get active workflow for the document's doctype"""
        try:
            return Workflow.objects.get(
                doctype=self.document.doctype,
                is_active=True
            )
        except Workflow.DoesNotExist:
            return None
        except Workflow.MultipleObjectsReturned:
            # Return the first active workflow
            return Workflow.objects.filter(
                doctype=self.document.doctype,
                is_active=True
            ).first()

    def get_current_state(self) -> Optional[WorkflowState]:
        """Get current workflow state for the document"""
        try:
            doc_state = DocumentWorkflowState.objects.get(document=self.document)
            return doc_state.current_state
        except DocumentWorkflowState.DoesNotExist:
            return None

    def initialize_workflow(self) -> DocumentWorkflowState:
        """
        Initialize workflow for a document by setting it to initial state

        Returns:
            DocumentWorkflowState instance

        Raises:
            WorkflowException: If workflow or initial state not found
        """
        workflow = self.get_workflow()
        if not workflow:
            raise WorkflowException(
                f"No active workflow found for doctype {self.document.doctype.name}"
            )

        # Get initial state
        initial_state = workflow.states.filter(is_initial=True).first()
        if not initial_state:
            raise WorkflowException(
                f"No initial state defined for workflow {workflow.name}"
            )

        # Create or update document workflow state
        doc_state, created = DocumentWorkflowState.objects.update_or_create(
            document=self.document,
            defaults={
                'workflow': workflow,
                'current_state': initial_state,
                'state_changed_by': self.user,
                'state_changed_at': timezone.now()
            }
        )

        logger.info(
            f"Initialized workflow for document {self.document.id} "
            f"to state {initial_state.name}"
        )

        return doc_state

    def get_available_transitions(self) -> List[WorkflowTransition]:
        """
        Get available transitions from current state for the user

        Returns:
            List of WorkflowTransition objects
        """
        current_state = self.get_current_state()
        if not current_state:
            return []

        # Get all transitions from current state
        transitions = WorkflowTransition.objects.filter(
            from_state=current_state
        ).prefetch_related('allowed_roles')

        # Filter by user permissions
        if self.user and not self.user.is_superuser:
            user_groups = self.user.groups.all()
            transitions = [
                t for t in transitions
                if not t.allowed_roles.exists() or
                any(role in user_groups for role in t.allowed_roles.all())
            ]

        return list(transitions)

    def can_transition(self, transition: WorkflowTransition) -> tuple[bool, Optional[str]]:
        """
        Check if user can perform a transition

        Args:
            transition: WorkflowTransition to check

        Returns:
            Tuple of (can_transition, reason_if_not)
        """
        # Check if transition is from current state
        current_state = self.get_current_state()
        if transition.from_state != current_state:
            return False, f"Document is in state '{current_state.name}', not '{transition.from_state.name}'"

        # Check user permissions
        if transition.allowed_roles.exists():
            if not self.user:
                return False, "User not authenticated"

            if not self.user.is_superuser:
                user_groups = self.user.groups.all()
                allowed = any(role in user_groups for role in transition.allowed_roles.all())
                if not allowed:
                    roles = ', '.join(str(r) for r in transition.allowed_roles.all())
                    return False, f"User does not have required role(s): {roles}"

        # Check condition if specified
        if transition.condition:
            try:
                # Create context for condition evaluation
                context = {
                    'document': self.document,
                    'user': self.user,
                    'data': self.document.data,
                }
                # Evaluate condition
                result = eval(transition.condition, {"__builtins__": {}}, context)
                if not result:
                    return False, "Transition condition not met"
            except Exception as e:
                logger.error(f"Error evaluating transition condition: {str(e)}")
                return False, f"Invalid transition condition: {str(e)}"

        return True, None

    @transaction.atomic
    def execute_transition(
        self,
        transition: WorkflowTransition,
        comment: Optional[str] = None,
        notify: bool = True
    ) -> DocumentWorkflowState:
        """
        Execute a workflow transition

        Args:
            transition: WorkflowTransition to execute
            comment: Optional comment for the transition
            notify: Whether to send email notifications

        Returns:
            Updated DocumentWorkflowState

        Raises:
            WorkflowTransitionDenied: If transition is not allowed
            ValidationError: If required comment is missing
        """
        # Check if transition is allowed
        can_transition, reason = self.can_transition(transition)
        if not can_transition:
            raise WorkflowTransitionDenied(reason)

        # Check for required comment
        if transition.require_comment and not comment:
            raise ValidationError("Comment is required for this transition")

        # Get current state for logging
        old_state = self.get_current_state()

        # Update document workflow state
        doc_state = DocumentWorkflowState.objects.get(document=self.document)
        doc_state.current_state = transition.to_state
        doc_state.state_changed_by = self.user
        doc_state.state_changed_at = timezone.now()
        doc_state.save()

        # Log the transition
        self._log_transition(old_state, transition.to_state, comment)

        # Execute transition actions
        self._execute_actions(transition.actions)

        # Send notifications
        if notify:
            self._send_notifications(old_state, transition.to_state, comment)

        logger.info(
            f"Document {self.document.id} transitioned from "
            f"'{old_state.name}' to '{transition.to_state.name}' by {self.user}"
        )

        return doc_state

    def _log_transition(
        self,
        from_state: WorkflowState,
        to_state: WorkflowState,
        comment: Optional[str]
    ):
        """Log workflow transition in document data"""
        # Add transition to document history
        if 'workflow_history' not in self.document.data:
            self.document.data['workflow_history'] = []

        self.document.data['workflow_history'].append({
            'from_state': from_state.name,
            'to_state': to_state.name,
            'changed_by': self.user.email if self.user else None,
            'changed_at': timezone.now().isoformat(),
            'comment': comment
        })

        self.document.save()

    def _execute_actions(self, actions: List[Dict[str, Any]]):
        """Execute actions defined in workflow transition"""
        if not actions:
            return

        for action in actions:
            action_type = action.get('type')

            if action_type == 'set_field':
                # Set field value
                field_name = action.get('field')
                value = action.get('value')
                if field_name and field_name in self.document.data:
                    self.document.data[field_name] = value
                    self.document.save()

            elif action_type == 'send_email':
                # Send email (handled by notifications)
                pass

            elif action_type == 'webhook':
                # Call webhook
                url = action.get('url')
                if url:
                    # TODO: Implement webhook call
                    logger.info(f"Webhook action: {url}")

            else:
                logger.warning(f"Unknown action type: {action_type}")

    def _send_notifications(
        self,
        from_state: WorkflowState,
        to_state: WorkflowState,
        comment: Optional[str]
    ):
        """Send email notifications on state change"""
        try:
            # Get notification recipients from document data
            recipients = []

            # Add document creator
            if hasattr(self.document, 'created_by') and self.document.created_by:
                recipients.append(self.document.created_by.email)

            # Add assigned users if field exists
            if 'assigned_to' in self.document.data:
                assigned_email = self.document.data.get('assigned_to')
                if assigned_email and assigned_email not in recipients:
                    recipients.append(assigned_email)

            # Add watchers if field exists
            if 'watchers' in self.document.data:
                watchers = self.document.data.get('watchers', [])
                for watcher in watchers:
                    if watcher not in recipients:
                        recipients.append(watcher)

            if not recipients:
                return

            # Prepare email context
            context = {
                'document': self.document,
                'doctype_name': self.document.doctype.name,
                'from_state': from_state.name,
                'to_state': to_state.name,
                'changed_by': self.user.email if self.user else 'System',
                'comment': comment,
                'document_url': f"{settings.SITE_URL}/doctypes/{self.document.doctype.slug}/{self.document.id}/"
            }

            # Render email
            subject = f"{self.document.doctype.name} - State Changed to {to_state.name}"
            html_message = render_to_string('doctypes/emails/workflow_notification.html', context)
            text_message = render_to_string('doctypes/emails/workflow_notification.txt', context)

            # Send email
            for recipient in recipients:
                try:
                    send_mail(
                        subject=subject,
                        message=text_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient],
                        html_message=html_message,
                        fail_silently=False
                    )
                    logger.info(f"Workflow notification sent to {recipient}")
                except Exception as e:
                    logger.error(f"Failed to send notification to {recipient}: {str(e)}")

        except Exception as e:
            logger.error(f"Error sending workflow notifications: {str(e)}")

    def get_workflow_history(self) -> List[Dict]:
        """Get workflow transition history for the document"""
        return self.document.data.get('workflow_history', [])

    def is_in_final_state(self) -> bool:
        """Check if document is in a final workflow state"""
        current_state = self.get_current_state()
        return current_state and current_state.is_final

    def is_in_success_state(self) -> bool:
        """Check if document is in a successful final state"""
        current_state = self.get_current_state()
        return current_state and current_state.is_success


# Convenience functions for quick access

def initialize_workflow(document: Document, user=None) -> DocumentWorkflowState:
    """Initialize workflow for a document"""
    engine = WorkflowEngine(document, user)
    return engine.initialize_workflow()


def get_available_transitions(document: Document, user=None) -> List[WorkflowTransition]:
    """Get available transitions for a document"""
    engine = WorkflowEngine(document, user)
    return engine.get_available_transitions()


def execute_transition(
    document: Document,
    transition: WorkflowTransition,
    user=None,
    comment: Optional[str] = None
) -> DocumentWorkflowState:
    """Execute a workflow transition"""
    engine = WorkflowEngine(document, user)
    return engine.execute_transition(transition, comment)


def get_current_state(document: Document) -> Optional[WorkflowState]:
    """Get current workflow state for a document"""
    engine = WorkflowEngine(document)
    return engine.get_current_state()
