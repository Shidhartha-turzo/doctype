"""
Report execution engine.

Runs ``Report`` definitions and returns ``{columns, rows, count}``, plus CSV
export. Three report types are supported:

- ``query``  – safe query builder over ``Document.data`` (filters + columns).
- ``python`` – a single sandboxed expression (no builtins, ``__`` rejected)
  that must return a list of row dicts.
- ``sql``    – raw read-only SQL, **superuser only**, restricted to a single
  ``SELECT`` with a word-boundary keyword blocklist.

Access control: a non-superuser may run a report only when it is public, owned
by them, or shared with one of their roles — *and* they hold ``read``
permission on the underlying doctype, so reports cannot bypass doctype RBAC.
"""
import csv
import io
import json
import logging
import re

from .engine_models import Report
from .models import Document
from .permissions import has_doctype_permission
from .workflow_engine import _SafeDocProxy

logger = logging.getLogger(__name__)

# Document attributes exposed as columns/filters in addition to data fields.
_META_FIELDS = {'name', 'docstatus', 'created_at', 'updated_at', 'version_number'}

# Filter operator -> Django lookup.
_LOOKUPS = {
    'eq': 'exact',
    'contains': 'icontains',
    'gt': 'gt',
    'gte': 'gte',
    'lt': 'lt',
    'lte': 'lte',
    'in': 'in',
}

_SQL_FORBIDDEN = re.compile(
    r'\b(insert|update|delete|drop|alter|create|grant|revoke|truncate|'
    r'attach|detach|pragma|replace|vacuum|reindex)\b',
    re.IGNORECASE,
)


class ReportError(Exception):
    """Base error for report execution (maps to HTTP 400)."""
    pass


class ReportPermissionError(ReportError):
    """Raised when a user may not run a report (maps to HTTP 403)."""
    pass


def _resolve_columns(report):
    """Return [{fieldname, label}] from report.columns, or all schema fields."""
    resolved = []
    for c in report.columns or []:
        if isinstance(c, str):
            resolved.append({'fieldname': c, 'label': c})
        elif isinstance(c, dict):
            fn = c.get('fieldname') or c.get('field') or c.get('name')
            if fn:
                resolved.append({'fieldname': fn, 'label': c.get('label', fn)})
    if not resolved:
        for f in (report.doctype.schema or {}).get('fields', []):
            resolved.append({'fieldname': f['name'], 'label': f.get('label', f['name'])})
    return resolved


def _cell(document, fieldname):
    """Read a column value from a Document (meta attribute or data field)."""
    if fieldname == 'created_by':
        return document.created_by.username if document.created_by else None
    if fieldname in _META_FIELDS:
        value = getattr(document, fieldname, None)
        return value if isinstance(value, (int, float, bool)) or value is None else str(value)
    return (document.data or {}).get(fieldname)


def _filter_key(field, lookup):
    base = field if (field in _META_FIELDS or field == 'created_by') else f'data__{field}'
    return f'{base}__{lookup}'


def _apply_filters(queryset, filters):
    for f in filters or []:
        field = f.get('field') or f.get('fieldname')
        if not field:
            continue
        op = f.get('op', 'eq')
        value = f.get('value')
        if op == 'ne':
            queryset = queryset.exclude(**{_filter_key(field, 'exact'): value})
            continue
        lookup = _LOOKUPS.get(op)
        if lookup is None:
            raise ReportError(f"Unsupported filter operator: {op!r}")
        queryset = queryset.filter(**{_filter_key(field, lookup): value})
    return queryset


class ReportService:
    """Stateless service for running reports."""

    @classmethod
    def user_can_access(cls, report, user):
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        # Raw SQL is superuser-only, full stop.
        if report.report_type == 'sql':
            return False

        if report.created_by_id == user.id or report.is_public:
            report_level = True
        else:
            allowed = set(report.allowed_roles.values_list('id', flat=True))
            user_groups = set(user.groups.values_list('id', flat=True))
            report_level = bool(allowed and (user_groups & allowed))
        if not report_level:
            return False
        # Reports must not bypass doctype-level RBAC.
        return has_doctype_permission(user, report.doctype, 'read')

    @classmethod
    def list_for_user(cls, user):
        return [
            r for r in Report.objects.select_related('doctype').all()
            if cls.user_can_access(r, user)
        ]

    @classmethod
    def run(cls, report, user, runtime_filters=None):
        if not cls.user_can_access(report, user):
            raise ReportPermissionError('You do not have permission to run this report.')
        if report.report_type == 'query':
            return cls._run_query(report, runtime_filters)
        if report.report_type == 'sql':
            return cls._run_sql(report, user)
        if report.report_type == 'python':
            return cls._run_python(report)
        raise ReportError(f'Unknown report type: {report.report_type!r}')

    @classmethod
    def _run_query(cls, report, runtime_filters=None):
        static_filters = []
        if report.query and report.query.strip():
            try:
                parsed = json.loads(report.query)
                if isinstance(parsed, dict):
                    static_filters = parsed.get('filters', [])
            except json.JSONDecodeError:
                pass  # query field is optional for the builder; ignore non-JSON

        queryset = Document.objects.filter(
            doctype=report.doctype, is_deleted=False
        ).order_by('-created_at')
        queryset = _apply_filters(queryset, list(static_filters) + list(runtime_filters or []))

        columns = _resolve_columns(report)
        rows = [
            {c['fieldname']: _cell(doc, c['fieldname']) for c in columns}
            for doc in queryset
        ]
        return {'columns': columns, 'rows': rows, 'count': len(rows)}

    @classmethod
    def _run_sql(cls, report, user):
        if not (user and user.is_superuser):
            raise ReportPermissionError('SQL reports may only be run by superusers.')
        sql = (report.query or '').strip().rstrip(';').strip()
        if not sql:
            raise ReportError('SQL report has no query.')
        if ';' in sql:
            raise ReportError('Only a single statement is allowed.')
        if not sql.lower().startswith('select'):
            raise ReportError('Only SELECT statements are allowed.')
        if '--' in sql or '/*' in sql:
            raise ReportError('SQL comments are not allowed.')
        if _SQL_FORBIDDEN.search(sql):
            raise ReportError('Query contains a forbidden keyword.')

        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(sql)
            col_names = [d[0] for d in cursor.description]
            rows = [dict(zip(col_names, r)) for r in cursor.fetchall()]
        columns = [{'fieldname': c, 'label': c} for c in col_names]
        return {'columns': columns, 'rows': rows, 'count': len(rows)}

    @classmethod
    def _run_python(cls, report):
        code = (report.query or '').strip()
        if not code:
            raise ReportError('Python report has no script.')
        if '__' in code:
            raise ReportError("Script may not contain '__'.")

        documents = [
            _SafeDocProxy(d) for d in Document.objects.filter(
                doctype=report.doctype, is_deleted=False
            ).order_by('-created_at')
        ]
        namespace = {
            'docs': documents,
            'len': len, 'sum': sum, 'sorted': sorted,
            'min': min, 'max': max, 'round': round,
            'True': True, 'False': False, 'None': None,
        }
        try:
            result = eval(code, {'__builtins__': {}}, namespace)
        except Exception as e:
            raise ReportError(f'Script error: {e}')
        if not isinstance(result, list):
            raise ReportError('Python report must return a list of row dicts.')

        rows = [r for r in result if isinstance(r, dict)]
        if report.columns:
            columns = _resolve_columns(report)
        elif rows:
            columns = [{'fieldname': k, 'label': k} for k in rows[0].keys()]
        else:
            columns = []
        return {'columns': columns, 'rows': rows, 'count': len(rows)}

    @staticmethod
    def to_csv(result):
        buffer = io.StringIO()
        fieldnames = [c['fieldname'] for c in result['columns']]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction='ignore')
        # Header row uses human labels.
        writer.writerow({c['fieldname']: c['label'] for c in result['columns']})
        for row in result['rows']:
            writer.writerow(row)
        return buffer.getvalue()
