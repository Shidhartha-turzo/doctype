"""
Hook Execution Engine

Executes hooks at various points in the document lifecycle.
Supports Python code, webhooks, emails, and notifications.
"""

import logging
import traceback
import requests
from typing import Optional, List, Dict, Any
from django.core.mail import send_mail
from django.conf import settings
from django.template import Context, Template
from django.utils import timezone

from .engine_models import DoctypeHook, Document

logger = logging.getLogger(__name__)


class HookException(Exception):
    """Base exception for hook errors"""
    pass


class HookExecutionError(HookException):
    """Raised when hook execution fails"""
    pass


class HookEngine:
    """
    Hook execution engine for document lifecycle events
    """

    def __init__(self, document: Document, user=None):
        """
        Initialize hook engine for a document

        Args:
            document: Document instance
            user: User performing the action
        """
        self.document = document
        self.user = user
        self.doctype = document.doctype

    def execute_hooks(self, hook_type: str, old_data: Optional[Dict] = None) -> List[Dict]:
        """
        Execute all hooks for a given hook type

        Args:
            hook_type: Type of hook (before_save, after_insert, etc.)
            old_data: Previous document data (for on_change detection)

        Returns:
            List of execution results

        Raises:
            HookExecutionError: If a critical hook fails
        """
        hooks = DoctypeHook.objects.filter(
            doctype=self.doctype,
            hook_type=hook_type,
            is_active=True
        ).order_by('order')

        results = []

        for hook in hooks:
            try:
                # Check condition if specified
                if hook.condition and not self._evaluate_condition(hook.condition):
                    logger.debug(f"Hook {hook.id} condition not met, skipping")
                    continue

                # Execute hook based on action type
                result = self._execute_hook(hook, old_data)
                results.append({
                    'hook_id': hook.id,
                    'hook_type': hook_type,
                    'action_type': hook.action_type,
                    'success': True,
                    'result': result
                })

                logger.info(
                    f"Hook executed successfully: {hook_type} - {hook.action_type} "
                    f"for document {self.document.id}"
                )

            except Exception as e:
                error_msg = f"Hook execution failed: {str(e)}"
                error_trace = traceback.format_exc()
                logger.error(f"{error_msg}\n{error_trace}")

                results.append({
                    'hook_id': hook.id,
                    'hook_type': hook_type,
                    'action_type': hook.action_type,
                    'success': False,
                    'error': error_msg,
                    'traceback': error_trace
                })

                # Log hook failure
                self._log_hook_failure(hook, error_msg, error_trace)

                # Re-raise for before_* hooks to prevent the operation
                if hook_type.startswith('before_'):
                    raise HookExecutionError(
                        f"Critical hook failed: {error_msg}"
                    )

        return results

    def _execute_hook(self, hook: DoctypeHook, old_data: Optional[Dict] = None) -> Any:
        """Execute a single hook based on its action type"""
        if hook.action_type == 'python':
            return self._execute_python_hook(hook)
        elif hook.action_type == 'webhook':
            return self._execute_webhook_hook(hook)
        elif hook.action_type == 'email':
            return self._execute_email_hook(hook)
        elif hook.action_type == 'notification':
            return self._execute_notification_hook(hook)
        else:
            raise HookException(f"Unknown action type: {hook.action_type}")

    def _execute_python_hook(self, hook: DoctypeHook) -> Dict:
        """
        Execute Python code hook

        Creates a safe execution environment with access to:
        - document: The document instance
        - data: document.data dictionary
        - user: The current user
        - old_data: Previous data (for on_change hooks)
        """
        if not hook.python_code:
            return {'status': 'skipped', 'reason': 'No Python code specified'}

        # Create execution context
        context = {
            'document': self.document,
            'data': self.document.data,
            'user': self.user,
            'logger': logger,
            # Add safe built-ins
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'set': set,
            'sum': sum,
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
        }

        try:
            # Execute the Python code
            exec(hook.python_code, {"__builtins__": {}}, context)

            # Check if document data was modified
            if context.get('data') != self.document.data:
                self.document.data = context['data']
                # Note: Actual save happens in calling code

            return {
                'status': 'success',
                'modified': context.get('data') != self.document.data
            }

        except Exception as e:
            raise HookExecutionError(f"Python hook execution failed: {str(e)}")

    def _execute_webhook_hook(self, hook: DoctypeHook) -> Dict:
        """
        Execute webhook HTTP call

        Sends POST request to webhook URL with document data
        """
        if not hook.webhook_url:
            return {'status': 'skipped', 'reason': 'No webhook URL specified'}

        # Prepare payload
        payload = {
            'event': hook.hook_type,
            'doctype': self.doctype.name,
            'document': {
                'id': self.document.id,
                'data': self.document.data,
                'created_at': self.document.created_at.isoformat() if hasattr(self.document, 'created_at') else None,
                'updated_at': self.document.updated_at.isoformat() if hasattr(self.document, 'updated_at') else None,
            },
            'user': self.user.email if self.user else None,
            'timestamp': timezone.now().isoformat()
        }

        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Doctype-Engine-Webhook/1.0',
            **hook.webhook_headers
        }

        try:
            # Make HTTP request with timeout
            response = requests.post(
                hook.webhook_url,
                json=payload,
                headers=headers,
                timeout=30  # 30 second timeout
            )

            return {
                'status': 'success',
                'status_code': response.status_code,
                'response': response.text[:500]  # Limit response size
            }

        except requests.RequestException as e:
            raise HookExecutionError(f"Webhook request failed: {str(e)}")

    def _execute_email_hook(self, hook: DoctypeHook) -> Dict:
        """
        Execute email trigger

        Sends email using Django's email backend
        """
        if not hook.email_template or not hook.email_recipients:
            return {'status': 'skipped', 'reason': 'Email template or recipients missing'}

        # Render email template
        context = Context({
            'document': self.document,
            'data': self.document.data,
            'doctype': self.doctype,
            'user': self.user,
        })

        try:
            template = Template(hook.email_template)
            email_body = template.render(context)

            # Send email to all recipients
            sent_count = 0
            for recipient in hook.email_recipients:
                try:
                    send_mail(
                        subject=f"[{self.doctype.name}] Document Update",
                        message=email_body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient],
                        fail_silently=False
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Failed to send email to {recipient}: {str(e)}")

            return {
                'status': 'success',
                'sent_count': sent_count,
                'total_recipients': len(hook.email_recipients)
            }

        except Exception as e:
            raise HookExecutionError(f"Email hook execution failed: {str(e)}")

    def _execute_notification_hook(self, hook: DoctypeHook) -> Dict:
        """
        Execute system notification

        Creates in-app notification for users
        """
        # TODO: Implement notification system
        logger.info(f"Notification hook triggered for document {self.document.id}")

        return {
            'status': 'success',
            'message': 'Notification created (placeholder)'
        }

    def _evaluate_condition(self, condition: str) -> bool:
        """
        Evaluate hook condition

        Args:
            condition: Python expression to evaluate

        Returns:
            True if condition is met, False otherwise
        """
        context = {
            'document': self.document,
            'data': self.document.data,
            'user': self.user,
        }

        try:
            result = eval(condition, {"__builtins__": {}}, context)
            return bool(result)
        except Exception as e:
            logger.error(f"Condition evaluation failed: {str(e)}")
            return False

    def _log_hook_failure(self, hook: DoctypeHook, error: str, traceback: str):
        """Log hook failure for debugging and monitoring"""
        # Store in document data for audit trail
        if 'hook_failures' not in self.document.data:
            self.document.data['hook_failures'] = []

        self.document.data['hook_failures'].append({
            'hook_id': hook.id,
            'hook_type': hook.hook_type,
            'action_type': hook.action_type,
            'error': error,
            'timestamp': timezone.now().isoformat()
        })

        # Limit history to last 10 failures
        if len(self.document.data['hook_failures']) > 10:
            self.document.data['hook_failures'] = self.document.data['hook_failures'][-10:]


# Convenience functions for common hook points

def execute_before_insert_hooks(document: Document, user=None) -> List[Dict]:
    """Execute before_insert hooks"""
    engine = HookEngine(document, user)
    return engine.execute_hooks('before_insert')


def execute_after_insert_hooks(document: Document, user=None) -> List[Dict]:
    """Execute after_insert hooks"""
    engine = HookEngine(document, user)
    return engine.execute_hooks('after_insert')


def execute_before_save_hooks(document: Document, user=None) -> List[Dict]:
    """Execute before_save hooks"""
    engine = HookEngine(document, user)
    return engine.execute_hooks('before_save')


def execute_after_save_hooks(document: Document, user=None) -> List[Dict]:
    """Execute after_save hooks"""
    engine = HookEngine(document, user)
    return engine.execute_hooks('after_save')


def execute_before_delete_hooks(document: Document, user=None) -> List[Dict]:
    """Execute before_delete hooks"""
    engine = HookEngine(document, user)
    return engine.execute_hooks('before_delete')


def execute_after_delete_hooks(document: Document, user=None) -> List[Dict]:
    """Execute after_delete hooks"""
    engine = HookEngine(document, user)
    return engine.execute_hooks('after_delete')


def execute_on_change_hooks(document: Document, old_data: Dict, user=None) -> List[Dict]:
    """Execute on_change hooks"""
    engine = HookEngine(document, user)
    return engine.execute_hooks('on_change', old_data)
