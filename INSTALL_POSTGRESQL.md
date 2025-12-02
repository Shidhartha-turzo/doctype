# PostgreSQL Installation - Quick Start

## For macOS Users (Recommended)

Run this single command to set up everything:

```bash
./setup_database_macos.sh && \
cp .env.example .env && \
source .venv/bin/activate && \
pip install -r requirements.txt && \
python manage.py migrate && \
python manage.py createsuperuser
```

That's it! Then start the server:
```bash
python manage.py runserver
```

---

## What This Does

1. **Installs PostgreSQL** (if not already installed)
2. **Creates database** `doctype_db`
3. **Creates user** `doctype_user` with password `doctype_password`
4. **Grants permissions** for the user
5. **Sets up environment** variables
6. **Installs dependencies** including `psycopg2-binary`
7. **Creates database schema** (runs all migrations)
8. **Creates superuser** for admin access

---

## Verify It Works

```bash
# Check database connection
python manage.py dbshell

# Inside psql, run:
\dt                    # List all tables
SELECT * FROM doctypes_doctype LIMIT 5;  # Query doctypes
\q                     # Quit
```

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

---

## Why PostgreSQL?

✅ **Better for production** - Handles concurrent connections
✅ **JSON support** - Native JSONB for doctype schemas
✅ **Advanced features** - Full-text search, triggers, views
✅ **Scalability** - Handle millions of records
✅ **ACID compliance** - Data integrity guaranteed
✅ **Concurrent writes** - No database locking issues

---

## Troubleshooting

### PostgreSQL not installed?
```bash
brew install postgresql@16
brew services start postgresql@16
```

### Can't connect to database?
```bash
# Check if PostgreSQL is running
brew services list

# Start it if not running
brew services start postgresql@16
```

### Permission issues?
```bash
# Grant permissions manually
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE doctype_db TO doctype_user;"
psql doctype_db -c "GRANT ALL ON SCHEMA public TO doctype_user;"
```

### Want to start fresh?
```bash
# Drop and recreate database
psql postgres -c "DROP DATABASE IF EXISTS doctype_db;"
./setup_database_macos.sh
python manage.py migrate
```

---

## Full Documentation

See **POSTGRESQL_SETUP.md** for:
- Manual installation steps
- Production configuration
- Backup and restore
- Migration from SQLite
- Advanced troubleshooting

---

## Files Created

- `setup_database_macos.sh` - Automated setup for macOS
- `setup_database.sh` - Setup for Linux
- `.env.example` - Updated with PostgreSQL config
- `POSTGRESQL_SETUP.md` - Complete documentation
- `INSTALL_POSTGRESQL.md` - This quick start guide

---

## Next Steps

1. ✅ PostgreSQL is now installed
2. ✅ Database schema is created
3. 📝 Create your first doctype in admin
4. 🚀 Build your application!

Visit: http://127.0.0.1:8000/admin/
