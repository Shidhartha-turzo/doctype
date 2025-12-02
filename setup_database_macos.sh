#!/bin/bash

# Doctype Engine - PostgreSQL Database Setup Script (macOS)
# Simplified version for macOS using Homebrew PostgreSQL

set -e  # Exit on error

echo "=========================================="
echo "Doctype Engine - Database Setup (macOS)"
echo "=========================================="
echo ""

# Load environment variables if .env exists
if [ -f .env ]; then
    echo "Loading database configuration from .env..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set default values
DB_NAME="${DB_NAME:-doctype_db}"
DB_USER="${DB_USER:-doctype_user}"
DB_PASSWORD="${DB_PASSWORD:-doctype_password}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

echo "Database Configuration:"
echo "  Name: $DB_NAME"
echo "  User: $DB_USER"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "Installing PostgreSQL via Homebrew..."
    brew install postgresql@16
    brew services start postgresql@16
    echo "Waiting for PostgreSQL to start..."
    sleep 3
fi

# Check if PostgreSQL is running
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" &> /dev/null; then
    echo "Starting PostgreSQL..."
    brew services start postgresql@16
    sleep 3
fi

echo "Creating database and user..."
echo ""

# Create user and database (macOS Homebrew doesn't need sudo)
psql postgres <<EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
        RAISE NOTICE 'User $DB_USER created';
    ELSE
        RAISE NOTICE 'User $DB_USER already exists';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- Connect to the new database and grant schema permissions
\c $DB_NAME
GRANT ALL ON SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Database created successfully!"
    echo ""
    echo "Connection string: postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
    echo ""
    echo "Next steps:"
    echo "  1. Activate virtual environment: source .venv/bin/activate"
    echo "  2. Install dependencies: pip install -r requirements.txt"
    echo "  3. Run migrations: python manage.py migrate"
    echo "  4. Create superuser: python manage.py createsuperuser"
    echo "  5. Start server: python manage.py runserver"
    echo ""
else
    echo ""
    echo "✗ Failed to create database!"
    echo "Please check the error messages above."
    exit 1
fi
