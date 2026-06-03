"""
Validation for ``table`` (child table) fields.

A table field embeds its rows directly in the parent document's data as a list
of dicts, keyed by column name. The field definition carries the column
sub-schema:

    {"name": "items", "type": "table", "columns": [
        {"name": "item", "type": "string", "required": true},
        {"name": "qty",  "type": "integer"},
        {"name": "rate", "type": "decimal"}
    ]}

``validate_table`` normalizes and type-checks the rows. It is shared by the API
serializer and the HTML form views so both enforce the same rules.
"""
import json
from decimal import Decimal, InvalidOperation


class ChildTableError(Exception):
    """Raised when a table field value is invalid (maps to HTTP 400)."""
    pass


def _convert_cell(column, raw):
    """Convert one cell value to its column type. Returns (value, error)."""
    if raw is None:
        return None, None
    raw_value = raw.strip() if isinstance(raw, str) else raw
    if raw_value == '' or raw_value is None:
        return None, None

    col_type = column.get('type', 'string')
    label = column.get('label', column['name'])
    try:
        if col_type == 'integer':
            return int(raw_value), None
        if col_type in ('decimal', 'currency', 'percent'):
            return str(Decimal(str(raw_value))), None
        if col_type == 'boolean':
            if isinstance(raw_value, bool):
                return raw_value, None
            return str(raw_value).lower() in ('true', '1', 'yes', 'on'), None
        if col_type == 'json':
            return (json.loads(raw_value) if isinstance(raw_value, str) else raw_value), None
        return str(raw_value), None
    except (ValueError, InvalidOperation, json.JSONDecodeError):
        return None, f"Invalid {col_type} value for column '{label}'"


def _row_is_blank(row):
    return not any(
        (str(v).strip() if v is not None else '') for v in row.values()
    )


def validate_table(field_config, value):
    """
    Normalize and validate a table field value.

    Accepts a list of row dicts or a JSON-encoded string of one. Returns the
    cleaned list of rows. Blank rows are dropped. Raises ChildTableError with a
    combined message if any row fails validation.
    """
    if value in (None, ''):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            raise ChildTableError(f"Table field '{field_config['name']}' must be valid JSON.")
    if not isinstance(value, list):
        raise ChildTableError(f"Table field '{field_config['name']}' must be a list of rows.")

    columns = field_config.get('columns', [])
    column_by_name = {c['name']: c for c in columns}

    cleaned = []
    errors = []
    for index, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            errors.append(f"Row {index} must be an object")
            continue
        if _row_is_blank(row):
            continue

        clean_row = {}
        for col_name, cell in row.items():
            column = column_by_name.get(col_name)
            if not column:
                continue  # ignore values for unknown columns
            converted, error = _convert_cell(column, cell)
            if error:
                errors.append(f"Row {index}: {error}")
            elif converted is not None:
                clean_row[col_name] = converted

        for column in columns:
            if column.get('required') and clean_row.get(column['name']) in (None, ''):
                errors.append(f"Row {index}: {column.get('label', column['name'])} is required")

        cleaned.append(clean_row)

    if errors:
        raise ChildTableError('; '.join(errors))
    return cleaned
