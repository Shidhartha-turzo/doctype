# Project: Doctype Engine

Django REST framework for dynamic, data-driven applications with comprehensive security.

## Token-saving rules

- Do NOT read entire .md files unless the task specifically requires full content.
- Use `Grep` to find relevant sections first, then `Read` with `offset`/`limit` to read only those sections.
- When updating docs, read only the portion being changed (use offset/limit).
- Prefer `Grep` with `-C` context lines over full file reads for understanding content.
- When multiple .md files need the same change (e.g. credential fix), use `Grep` to find exact lines, then `Edit` directly — no need to read the whole file.

## Project structure

- 14 documentation files in project root (see README.md "Additional Documentation" for the list)
- Apps: `core/`, `authentication/`, `doctypes/`, `doctype/` (settings)
- Database: SQLite (dev), PostgreSQL (prod)
- Python 3.10-3.13 (3.14 not supported)

## Engine modules (`doctypes/`)

Feature logic lives in dedicated stateless service modules; views/serializers are thin and call into them:

- `workflow_engine.py` — `WorkflowService`: state transitions, role checks, submit/cancel, transition log.
- `permissions.py` — `has_doctype_permission` / `get_field_restrictions` / `HasDoctypePermission`. **Secure-by-default**: a doctype with no `DoctypePermission` rows is superuser-only.
- `hook_engine.py` — `HookService`: fires `DoctypeHook`s across the document lifecycle (insert/save/delete/submit) from the serializer + HTML views + WorkflowService.
- `report_engine.py` — `ReportService`: query-builder / sandboxed-python / superuser-only SELECT-only SQL; JSON + CSV.
- `search_engine.py` — `SearchService`: structured multi-field search (operators, AND/OR, sort, pagination) + global search.
- `import_export.py` — CSV export / template / import with per-row validation.
- `print_engine.py` — `PrintService`: HTML print + optional PDF (xhtml2pdf, optional dep).
- `child_tables.py` — `validate_table`: embedded-row `table` field validation (shared by API + HTML).

## Key conventions

- **Sandboxed eval**: untrusted expressions (workflow/hook/permission conditions, python reports/hooks) use `eval` with `{'__builtins__': {}}` + `_SafeDocProxy`; the hook/report path also **rejects `__`** to block escape chains. Never add a raw `exec`/unrestricted `eval`.
- **Child tables**: a `table` field stores rows embedded in `data[field]` (list of dicts); columns defined in `field['columns']`. No separate child Document records.
- **Many-to-many**: a `multiselect` field *with* `link_doctype` = M2M document link (names in `data`, mirrored to ordered `DocumentLinkMultiple`); *without* it = static multi-value.
- **Attachment limits** are runtime-configurable via `SystemSettings` (admin), not just `settings.py`.
- **URL ordering** (`doctypes/urls.py`): literal API routes first; slug-scoped routes (`<doctype_slug>/...`) live in the end section so they don't shadow literal paths. DRF reserves the `format` query param — use `output` instead.
- Verify changes with `venv/bin/python manage.py check` and a `manage.py shell -c` smoke test (set `settings.ALLOWED_HOSTS=['*']` when using the test client).

## Default credentials

- `spoofman` / `admin123!` (superuser)
- `admin` / `admin123` (superuser)
