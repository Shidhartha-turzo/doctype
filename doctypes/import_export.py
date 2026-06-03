"""
CSV import/export for documents.

Export and the import template use the schema field *names* as column headers
so the two round-trip. Import validates each row against the schema, collects
per-row errors without aborting the whole file, and creates documents through
the normal HookService + workflow pipeline so imported rows behave exactly like
documents created via the API/UI.

CSV only (stdlib) — no Excel dependency, consistent with the reports engine.
"""
import csv
import io
import json
import logging
from decimal import Decimal, InvalidOperation

from .models import Document

logger = logging.getLogger(__name__)


class ImportExportError(Exception):
    """Raised for unrecoverable import/export problems (e.g. bad file)."""
    pass


def _schema_fields(doctype):
    return (doctype.schema or {}).get('fields', [])


def _headers(doctype):
    return ['name'] + [f['name'] for f in _schema_fields(doctype)]


def export_csv(doctype):
    """Return all of a doctype's documents as a CSV string."""
    fields = _schema_fields(doctype)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_headers(doctype), extrasaction='ignore')
    writer.writeheader()
    documents = Document.objects.filter(doctype=doctype, is_deleted=False).order_by('-created_at')
    for document in documents:
        data = document.data or {}
        row = {'name': document.name}
        for f in fields:
            value = data.get(f['name'], '')
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            row[f['name']] = value
        writer.writerow(row)
    return buffer.getvalue()


def import_template(doctype):
    """Return an empty CSV (header row only) for filling in and importing."""
    buffer = io.StringIO()
    csv.writer(buffer).writerow(_headers(doctype))
    return buffer.getvalue()


def _convert_value(field, raw):
    """Convert a raw CSV string to a typed value. Returns (value, error)."""
    raw = (raw or '').strip()
    if raw == '':
        return None, None
    field_type = field.get('type', 'string')
    label = field.get('label', field['name'])
    try:
        if field_type == 'integer':
            return int(raw), None
        if field_type == 'decimal':
            return str(Decimal(raw)), None
        if field_type == 'boolean':
            return raw.lower() in ('true', '1', 'yes', 'on'), None
        if field_type == 'json':
            return json.loads(raw), None
        # string / text / select / date / link are stored as-is
        return raw, None
    except (ValueError, InvalidOperation, json.JSONDecodeError):
        return None, f"Invalid {field_type} value for '{label}'"


def import_csv(doctype, uploaded_file, user):
    """
    Import documents from an uploaded CSV file.

    Returns {created, total, errors} where errors is a list of
    {row, errors:[...]} for rows that failed. Successful rows are committed even
    if other rows fail (partial import).
    """
    from .hook_engine import HookService, HookError
    from .workflow_engine import WorkflowService, WorkflowError

    try:
        raw = uploaded_file.read()
        text = raw.decode('utf-8-sig', errors='replace') if isinstance(raw, bytes) else raw
    except Exception as e:
        raise ImportExportError(f'Could not read file: {e}')

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ImportExportError('CSV file is empty or has no header row.')

    fields = _schema_fields(doctype)
    field_by_name = {f['name']: f for f in fields}

    created = 0
    errors = []
    # Data rows start at line 2 (line 1 is the header).
    for line_number, row in enumerate(reader, start=2):
        data = {}
        row_errors = []
        for column, raw_value in row.items():
            field = field_by_name.get(column)
            if not field:
                continue  # ignore unknown columns and the 'name' column
            value, error = _convert_value(field, raw_value)
            if error:
                row_errors.append(error)
            elif value is not None:
                data[field['name']] = value

        for f in fields:
            if f.get('required') and data.get(f['name']) in (None, ''):
                row_errors.append(f"{f.get('label', f['name'])} is required")

        if row_errors:
            errors.append({'row': line_number, 'errors': row_errors})
            continue

        name = (row.get('name') or '').strip()
        if not name:
            name = str(data.get(fields[0]['name'])) if fields else 'NEW'

        document = Document(doctype=doctype, name=str(name), data=data, created_by=user)
        try:
            HookService.save_with_hooks(document, user=user, is_new=True)
        except HookError as e:
            errors.append({'row': line_number, 'errors': [f'Hook aborted: {e}']})
            continue

        try:
            WorkflowService.initialize_workflow(document, user=user)
        except WorkflowError as e:
            logger.warning(f'Workflow init failed for imported row {line_number}: {e}')

        created += 1

    return {'created': created, 'total': created + len(errors), 'errors': errors}
