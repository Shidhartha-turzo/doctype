"""
Advanced document search.

Structured multi-field filtering over Document.data (and a few meta fields)
with a range of operators, AND/OR matching, optional free-text query, safe
sorting, and pagination. Results respect the caller's field restrictions
(hidden fields are stripped) so search cannot leak data the RBAC layer hides.

Also provides a cross-doctype global search limited to doctypes the user may
read.
"""
import logging

from django.core.paginator import Paginator
from django.db.models import Q

from .models import Doctype, Document
from .permissions import get_field_restrictions, has_doctype_permission

logger = logging.getLogger(__name__)

_META_FIELDS = {'name', 'docstatus', 'created_at', 'updated_at', 'version_number'}
_OPERATORS = {
    'eq', 'ne', 'contains', 'not_contains', 'starts_with', 'ends_with',
    'gt', 'gte', 'lt', 'lte', 'in', 'is_empty', 'is_not_empty',
}
_MAX_PAGE_SIZE = 500


class SearchError(Exception):
    """Raised for malformed search requests (maps to HTTP 400)."""
    pass


def _base_key(field):
    """ORM lookup base for a field — meta attribute or JSON data key."""
    if field in _META_FIELDS or field == 'created_by':
        return field
    return f'data__{field}'


def _q_for(field, op, value):
    base = _base_key(field)
    if op == 'eq':
        return Q(**{base: value})
    if op == 'ne':
        return ~Q(**{base: value})
    if op == 'contains':
        return Q(**{f'{base}__icontains': value})
    if op == 'not_contains':
        return ~Q(**{f'{base}__icontains': value})
    if op == 'starts_with':
        return Q(**{f'{base}__istartswith': value})
    if op == 'ends_with':
        return Q(**{f'{base}__iendswith': value})
    if op in ('gt', 'gte', 'lt', 'lte'):
        return Q(**{f'{base}__{op}': value})
    if op == 'in':
        if not isinstance(value, (list, tuple)):
            raise SearchError("Operator 'in' requires a list value.")
        return Q(**{f'{base}__in': list(value)})
    if op == 'is_empty':
        return Q(**{base: ''}) | Q(**{f'{base}__isnull': True})
    if op == 'is_not_empty':
        return ~(Q(**{base: ''}) | Q(**{f'{base}__isnull': True}))
    raise SearchError(f'Unsupported operator: {op!r}')


class SearchService:
    """Stateless service for advanced and global document search."""

    @classmethod
    def search(cls, doctype, user, filters=None, match='all', query=None,
               sort=None, page=1, page_size=50):
        queryset = Document.objects.filter(doctype=doctype, is_deleted=False)

        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(data__icontains=query))

        q_objects = []
        for f in filters or []:
            field = f.get('field')
            if not field:
                continue
            op = f.get('op', 'eq')
            if op not in _OPERATORS:
                raise SearchError(f'Unsupported operator: {op!r}')
            q_objects.append(_q_for(field, op, f.get('value')))

        if q_objects:
            combined = q_objects[0]
            for q in q_objects[1:]:
                combined = (combined & q) if match == 'all' else (combined | q)
            queryset = queryset.filter(combined)

        queryset = queryset.order_by(cls._safe_sort(doctype, sort) or '-created_at')

        try:
            page_size = max(1, min(int(page_size), _MAX_PAGE_SIZE))
        except (TypeError, ValueError):
            page_size = 50
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        hidden, _ = get_field_restrictions(user, doctype)
        results = [cls._serialize(d, hidden) for d in page_obj.object_list]
        return {
            'count': paginator.count,
            'page': page_obj.number,
            'num_pages': paginator.num_pages,
            'page_size': page_size,
            'results': results,
        }

    @classmethod
    def _safe_sort(cls, doctype, sort):
        """Map a user-supplied sort field to a safe order_by, or None."""
        if not sort:
            return None
        descending = sort.startswith('-')
        field = sort.lstrip('-')
        schema_fields = {f['name'] for f in (doctype.schema or {}).get('fields', [])}
        if field not in _META_FIELDS and field != 'created_by' and field not in schema_fields:
            return None
        return ('-' if descending else '') + _base_key(field)

    @classmethod
    def _serialize(cls, document, hidden):
        data = {k: v for k, v in (document.data or {}).items() if k not in hidden}
        return {
            'id': document.id,
            'name': document.name,
            'docstatus': document.docstatus,
            'data': data,
            'created_at': document.created_at.isoformat() if document.created_at else None,
        }

    @classmethod
    def global_search(cls, user, query, limit_per_doctype=10):
        """Search a term across the name/data of every doctype the user can read."""
        query = (query or '').strip()
        if not query:
            raise SearchError("Query parameter 'q' is required.")

        groups = []
        for doctype in Doctype.objects.filter(is_active=True):
            if not has_doctype_permission(user, doctype, 'read'):
                continue
            matches = Document.objects.filter(
                doctype=doctype, is_deleted=False
            ).filter(Q(name__icontains=query) | Q(data__icontains=query))[:limit_per_doctype]
            items = [{'id': d.id, 'name': d.name} for d in matches]
            if items:
                groups.append({
                    'doctype': doctype.slug,
                    'doctype_name': doctype.name,
                    'matches': items,
                })
        return {'query': query, 'results': groups}
