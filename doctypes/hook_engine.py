"""
Doctype hook execution engine.

Fires ``DoctypeHook`` rows during the document lifecycle (insert / save /
delete / submit). Mirrors the structure of WorkflowService and reuses its
``_SafeDocProxy`` for safe expression evaluation.

Security posture:
- ``webhook`` and ``email`` actions are fully executed.
- ``python`` actions are evaluated as a *single sandboxed expression* with no
  builtins and no access to dunder attributes (``__`` is rejected, which blocks
  the classic ``().__class__.__subclasses__()`` eval-escape chain). Imports,
  statements, and I/O are therefore impossible. If the expression returns a
  dict, its keys are merged into ``document.data`` — this is the supported way
  to compute field values in ``before_*`` hooks (e.g. totals).
- ``notification`` actions are a no-op: there is no notification backend yet.

A ``before_*`` hook that raises aborts the whole operation (HookError);
``after_*`` hook failures are logged but never block the save.
"""
import logging

import requests as http_requests

from .engine_models import DoctypeHook
from .workflow_engine import _SafeDocProxy

logger = logging.getLogger(__name__)


class HookError(Exception):
    """Raised when a before_* hook fails, aborting the operation."""
    pass


def _is_safe_expression(code):
    """Reject expressions that could escape the eval sandbox."""
    return '__' not in code


def _safe_eval(code, document, user):
    """
    Evaluate a single expression with no builtins and a restricted namespace.
    Raises ValueError if the expression is not sandbox-safe.
    """
    if not _is_safe_expression(code):
        raise ValueError("Expression may not contain '__'.")
    namespace = {
        'doc': _SafeDocProxy(document),
        'user': user,
        'True': True,
        'False': False,
        'None': None,
    }
    return eval(code, {'__builtins__': {}}, namespace)


class HookService:
    """Stateless service that runs doctype hooks for a document."""

    @classmethod
    def _hooks_for(cls, doctype, hook_type):
        return DoctypeHook.objects.filter(
            doctype=doctype, hook_type=hook_type, is_active=True
        ).order_by('order')

    @classmethod
    def run_hooks(cls, document, hook_type, user=None):
        """
        Run every active hook of ``hook_type`` for the document's doctype.

        For ``before_*`` hooks a failure raises HookError (the caller must not
        proceed with the save). For ``after_*`` hooks failures are logged only.
        Returns the (possibly mutated) document.
        """
        is_before = hook_type.startswith('before_')
        for hook in cls._hooks_for(document.doctype, hook_type):
            if hook.condition and hook.condition.strip():
                try:
                    if not bool(_safe_eval(hook.condition, document, user)):
                        continue
                except Exception as e:
                    logger.warning(
                        f"Hook {hook.id} condition failed ({hook.condition!r}): {e}"
                    )
                    continue
            try:
                cls._execute(hook, document, user)
            except Exception as e:
                logger.error(
                    f"Hook {hook.id} ({hook.hook_type}/{hook.action_type}) "
                    f"failed: {e}"
                )
                if is_before:
                    raise HookError(f"{hook.hook_type} hook failed: {e}")
        return document

    @classmethod
    def save_with_hooks(cls, document, user=None, is_new=None):
        """Run before/after insert+save hooks around document.save()."""
        if is_new is None:
            is_new = document._state.adding
        if is_new:
            cls.run_hooks(document, 'before_insert', user)
        cls.run_hooks(document, 'before_save', user)
        document.save()
        if is_new:
            cls.run_hooks(document, 'after_insert', user)
        cls.run_hooks(document, 'after_save', user)
        return document

    @classmethod
    def delete_with_hooks(cls, document, user=None):
        """Run before/after delete hooks around document.delete()."""
        cls.run_hooks(document, 'before_delete', user)
        document.delete()
        cls.run_hooks(document, 'after_delete', user)

    # --- Action dispatch ---

    @classmethod
    def _execute(cls, hook, document, user):
        action_type = hook.action_type
        if action_type == 'webhook':
            cls._execute_webhook(hook, document)
        elif action_type == 'email':
            cls._execute_email(hook, document, user)
        elif action_type == 'python':
            cls._execute_python(hook, document, user)
        elif action_type == 'notification':
            logger.info(
                f"Notification hook {hook.id} skipped: no notification backend."
            )
        else:
            logger.warning(f"Unknown hook action_type: {action_type!r}")

    @classmethod
    def _execute_python(cls, hook, document, user):
        """
        Evaluate the sandboxed expression. If it returns a dict, merge it into
        document.data (intended for before_* compute hooks).
        """
        code = (hook.python_code or '').strip()
        if not code:
            return
        result = _safe_eval(code, document, user)
        if isinstance(result, dict):
            if document.data is None:
                document.data = {}
            document.data.update(result)

    @classmethod
    def _execute_webhook(cls, hook, document):
        url = hook.webhook_url
        if not url:
            return
        payload = {
            'document_id': document.id,
            'document_name': document.name,
            'doctype': document.doctype.name,
            'data': document.data,
            'event': hook.hook_type,
        }
        resp = http_requests.post(
            url, json=payload, headers=hook.webhook_headers or {}, timeout=10
        )
        logger.info(f"Hook webhook {url} returned {resp.status_code}")

    @classmethod
    def _execute_email(cls, hook, document, user):
        recipients = hook.email_recipients or []
        if isinstance(recipients, str):
            recipients = [recipients]
        if not recipients:
            return
        subject = f"Document update: {document.name}"
        message = hook.email_template or (
            f"Document '{document.name}' ({document.doctype.name}) "
            f"triggered hook '{hook.hook_type}'."
        )
        from django.core.mail import send_mail
        send_mail(subject, message, None, recipients, fail_silently=True)
