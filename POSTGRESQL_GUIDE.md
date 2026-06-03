# PostgreSQL Guide

This guide covers PostgreSQL setup for the Doctype Engine. Development uses SQLite by default; PostgreSQL is recommended for production.

## Quick Start (macOS)

Run this single command to set up everything:

```bash
./setup_database_macos.sh && \
cp .env.example .env && \
source .venv/bin/activate && \
pip install -r requirements.txt && \
python manage.py migrate && \
python manage.py createsuperuser
```

Then start the server:
```bash
python manage.py runserver
```

### What This Does

1. **Installs PostgreSQL** (if not already installed)
2. **Creates database** `doctype_db`
3. **Creates user** `doctype_user` with password `doctype_password`
4. **Grants permissions** for the user
5. **Sets up environment** variables
6. **Installs dependencies** including `psycopg2-binary`
7. **Creates database schema** (runs all migrations)
8. **Creates superuser** for admin access

### Verify It Works

```bash
python manage.py dbshell

# Inside psql:
\dt                    # List all tables
SELECT * FROM doctypes_doctype LIMIT 5;
\q                     # Quit
```

---

## Manual Setup

### 1. Install PostgreSQL

**macOS (Homebrew):**
```bash
brew install postgresql@16
brew services start postgresql@16
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**CentOS/RHEL:**
```bash
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. Create Database and User

**macOS (using current user):**
```bash
psql postgres -c "CREATE DATABASE doctype_db;"
psql postgres -c "CREATE USER doctype_user WITH PASSWORD 'doctype_password';"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE doctype_db TO doctype_user;"
psql doctype_db -c "GRANT ALL ON SCHEMA public TO doctype_user;"
```

**Linux (using postgres user):**
```bash
sudo -u postgres psql <<EOF
CREATE DATABASE doctype_db;
CREATE USER doctype_user WITH PASSWORD 'doctype_password';
GRANT ALL PRIVILEGES ON DATABASE doctype_db TO doctype_user;
\c doctype_db
GRANT ALL ON SCHEMA public TO doctype_user;
EOF
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set database credentials:
```
DB_NAME=doctype_db
DB_USER=doctype_user
DB_PASSWORD=doctype_password
DB_HOST=localhost
DB_PORT=5432
```

### 4. Install Python Dependencies

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Run Migrations

```bash
python manage.py migrate
```

### 6. Create Superuser

```bash
python manage.py createsuperuser
```

### 7. Verify Setup

```bash
python manage.py dbshell
```

Type `\dt` to see all tables, then `\q` to quit.

---

## What Changed from SQLite

### Before (SQLite):
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

### After (PostgreSQL):
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='doctype_db'),
        'USER': config('DB_USER', default='doctype_user'),
        'PASSWORD': config('DB_PASSWORD', default='doctype_password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}
```

### Why PostgreSQL?

- **Better for production** - Handles concurrent connections
- **JSON support** - Native JSONB for doctype schemas
- **Advanced features** - Full-text search, triggers, views
- **Scalability** - Handle millions of records
- **ACID compliance** - Data integrity guaranteed
- **Concurrent writes** - No database locking issues

---

## Database Schema

The migrations will automatically create:

### Core Tables
- **auth_user** - Django users
- **auth_group** - User groups
- **auth_permission** - Permissions

### Doctype Engine Tables
- **doctypes_module** - Module organization
- **doctypes_doctype** - Doctype definitions (metadata + JSON schema)
- **doctypes_document** - Document instances (data stored as JSON)

### Advanced Tables
- **doctypes_doctypepermission** - Role-based permissions
- **doctypes_documentversion** - Version history
- **doctypes_workflow** - Workflow definitions
- **doctypes_workflowstate** - Workflow states
- **doctypes_workflowtransition** - State transitions
- **doctypes_documentworkflowstate** - Document workflow tracking
- **doctypes_namingseries** - Auto-naming sequences
- **doctypes_doctypehook** - Pre/post hooks
- **doctypes_customfield** - Runtime field additions
- **doctypes_report** - Report definitions

### Security Tables
- **core_systemsettings** - System configuration
- **core_ipwhitelist** - IP whitelist
- **core_ipblacklist** - IP blacklist
- **core_apikey** - API key management
- **core_loginattempt** - Brute force tracking
- **core_requestlog** - Request logging

---

## Troubleshooting

### Connection Refused

**Error:**
```
django.db.utils.OperationalError: could not connect to server: Connection refused
```

**Solution:**
```bash
# macOS
brew services list
brew services start postgresql@16

# Linux
sudo systemctl status postgresql
sudo systemctl start postgresql
```

### Authentication Failed

**Error:**
```
FATAL: password authentication failed for user "doctype_user"
```

**Solution:**
Check your `.env` file has correct credentials. Reset password if needed:
```bash
psql postgres -c "ALTER USER doctype_user WITH PASSWORD 'new_password';"
```

### Permission Denied

**Error:**
```
permission denied for schema public
```

**Solution:**
```bash
psql doctype_db -c "GRANT ALL ON SCHEMA public TO doctype_user;"
psql doctype_db -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO doctype_user;"
```

### Database Already Exists

```bash
# WARNING: This deletes all data!
psql postgres -c "DROP DATABASE IF EXISTS doctype_db;"
psql postgres -c "CREATE DATABASE doctype_db OWNER doctype_user;"
python manage.py migrate
```

### PostgreSQL Not Installed?

```bash
brew install postgresql@16
brew services start postgresql@16
```

---

## Backup and Restore

### Backup

```bash
pg_dump -U doctype_user -h localhost doctype_db > backup.sql
```

### Restore

```bash
psql -U doctype_user -h localhost doctype_db < backup.sql
```

---

## Migrating from SQLite

If you have existing data in SQLite:

```bash
# 1. Backup SQLite data
python manage.py dumpdata > data_backup.json

# 2. Switch to PostgreSQL (update settings.py and .env)

# 3. Create PostgreSQL database
./setup_database_macos.sh

# 4. Run migrations
python manage.py migrate

# 5. Load data
python manage.py loaddata data_backup.json
```

---

## Production Considerations

### 1. Use Strong Passwords

```bash
openssl rand -base64 32
```

### 2. Configure pg_hba.conf

Edit `/etc/postgresql/16/main/pg_hba.conf` (path may vary):
```
# Local connections
local   all             all                                     peer
# IPv4 local connections
host    all             all             127.0.0.1/32            scram-sha-256
```

### 3. Enable SSL

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'doctype_db',
        'USER': 'doctype_user',
        'PASSWORD': 'secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'sslmode': 'require',
        }
    }
}
```

### 4. Connection Pooling

For production, consider using PgBouncer:
```bash
apt install pgbouncer
```

In `settings.py`:
```python
DATABASES = {
    'default': {
        ...
        'CONN_MAX_AGE': 600,  # Keep connections open for 10 minutes
    }
}
```

---

## Setup Scripts

- `setup_database_macos.sh` - Automated setup for macOS
- `setup_database.sh` - Setup for Linux
- `.env.example` - Template with PostgreSQL config
