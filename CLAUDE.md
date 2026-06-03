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

## Default credentials

- `spoofman` / `admin123!` (superuser)
- `admin` / `admin123` (superuser)
