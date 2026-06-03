"""
Doctype-level permission enforcement (role-based access control).

Secure-by-default: a user is granted an action on a doctype only when one of
their groups has a ``DoctypePermission`` row that grants it. Superusers always
pass. A doctype with no matching granting rows is accessible to superusers
only.

This module is the single source of truth shared by both the DRF API views and
the server-rendered HTML views, so the two surfaces can never drift apart.
"""
import logging

from rest_framework.permissions import BasePermission

from .engine_models import DoctypePermission
from .workflow_engine import _SafeDocProxy

logger = logging.getLogger(__name__)

# Map an abstract action name to the boolean field on DoctypePermission.
# Only actions backed by a real model field are listed here.
_ACTION_FIELD = {
    'create': 'can_create',
    'read': 'can_read',
    'write': 'can_write',
    'delete': 'can_delete',
    'submit': 'can_submit',
    'cancel': 'can_cancel',
    'export': 'can_export',
    'import': 'can_import',
}


def _granting_rows(user, doctype):
    """Permission rows for this doctype that apply to the user's groups."""
    return DoctypePermission.objects.filter(
        doctype=doctype,
        role__in=user.groups.all(),
    )


def _evaluate_condition(condition_str, user, document):
    """
    Safely evaluate a permission condition. Returns False on any error.

    Mirrors WorkflowService._evaluate_condition: no builtins, document fields
    exposed via _SafeDocProxy as ``doc``, plus the requesting ``user``.
    """
    try:
        safe_ns = {
            'doc': _SafeDocProxy(document),
            'user': user,
            'True': True,
            'False': False,
            'None': None,
        }
        return bool(eval(condition_str, {'__builtins__': {}}, safe_ns))
    except Exception as e:
        logger.warning(f"Permission condition failed for '{condition_str}': {e}")
        return False


def has_doctype_permission(user, doctype, action, document=None):
    """
    Return True if ``user`` may perform ``action`` on ``doctype``.

    Secure-by-default: with no granting row the result is False (superusers
    excepted). When a granting row defines a ``permission_condition`` and a
    ``document`` is supplied, the condition must also evaluate truthy.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    field = _ACTION_FIELD.get(action)
    if field is None:
        logger.warning(f"Unknown doctype permission action: {action!r}")
        return False

    for row in _granting_rows(user, doctype):
        if not getattr(row, field, False):
            continue
        if row.permission_condition and document is not None:
            if not _evaluate_condition(row.permission_condition, user, document):
                continue
        return True
    return False


def get_field_restrictions(user, doctype):
    """
    Return ``(hidden_fields, read_only_fields)`` as sets for the user.

    Restrictions are intersected across the user's granting roles: a field is
    hidden/read-only only when *every* applicable role restricts it, so adding
    a more privileged role widens visibility rather than narrowing it.
    Superusers and users with no granting rows get empty sets.
    """
    if not user or not user.is_authenticated or user.is_superuser:
        return set(), set()

    rows = list(_granting_rows(user, doctype))
    if not rows:
        return set(), set()

    hidden = None
    readonly = None
    for row in rows:
        h = set(row.hidden_fields or [])
        r = set(row.read_only_fields or [])
        hidden = h if hidden is None else (hidden & h)
        readonly = r if readonly is None else (readonly & r)
    return hidden or set(), readonly or set()


class HasDoctypePermission(BasePermission):
    """
    DRF permission class for the DoctypeViewSet ``records`` action.

    Maps the HTTP method to a doctype action (GET -> read, POST -> create) and
    checks it against the doctype resolved from the view. Other viewset actions
    keep their existing IsAuthenticated guard.
    """
    message = 'You do not have permission to perform this action on this doctype.'

    def has_permission(self, request, view):
        if getattr(view, 'action', None) != 'records':
            return True
        doctype = view.get_object()
        action = 'create' if request.method == 'POST' else 'read'
        return has_doctype_permission(request.user, doctype, action)
