# PostgreSQL Setup Guide

This guide explains how to set up PostgreSQL for the Doctype Engine.

## Quick Start (macOS)

```bash
# 1. Run the automated setup script
./setup_database_macos.sh

# 2. Copy environment file
cp .env.example .env

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install/upgrade dependencies
pip install -r requirements.txt

# 5. Run migrations to create schema
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Start server
python manage.py runserver
```

Done! Your application is now running with PostgreSQL.

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

Create or update `.env` file:
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

This creates all the database tables and schema:
```bash
python manage.py migrate
```

You should see output like:
```
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, core, doctypes, sessions
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  Applying admin.0001_initial... OK
  ...
```

### 6. Create Initial Data

Create a superuser:
```bash
python manage.py createsuperuser
```

### 7. Verify Setup

Check that you can connect to the database:
```bash
python manage.py dbshell
```

This should open a PostgreSQL prompt. Type `\dt` to see all tables, then `\q` to quit.

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
Ensure PostgreSQL is running:
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
Grant schema permissions:
```bash
psql doctype_db -c "GRANT ALL ON SCHEMA public TO doctype_user;"
psql doctype_db -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO doctype_user;"
```

### Database Already Exists

If you need to recreate the database:
```bash
# WARNING: This deletes all data!
psql postgres -c "DROP DATABASE IF EXISTS doctype_db;"
psql postgres -c "CREATE DATABASE doctype_db OWNER doctype_user;"
```

Then run migrations again:
```bash
python manage.py migrate
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

## Production Considerations

### 1. Use Strong Passwords

Generate a secure password:
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

In `settings.py`:
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
# Install PgBouncer
apt install pgbouncer

# Configure in settings.py
DATABASES = {
    'default': {
        ...
        'CONN_MAX_AGE': 600,  # Keep connections open for 10 minutes
    }
}
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

## Next Steps

- [x] PostgreSQL installed and running
- [x] Database and user created
- [x] Migrations applied
- [x] Superuser created
- [ ] Create your first doctype
- [ ] Set up production server (Gunicorn/Nginx)
- [ ] Configure backups
- [ ] Set up monitoring

For more help, see the main README.md or visit the documentation.
