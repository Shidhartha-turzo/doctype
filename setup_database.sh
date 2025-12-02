#!/bin/bash

# Doctype Engine - PostgreSQL Database Setup Script
# This script creates the PostgreSQL database and user for the Doctype Engine

set -e  # Exit on error

echo "=========================================="
echo "Doctype Engine - Database Setup"
echo "=========================================="
echo ""

# Load environment variables if .env exists
if [ -f .env ]; then
    echo "Loading database configuration from .env..."
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Warning: .env file not found. Using default values."
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
    echo "Error: PostgreSQL is not installed!"
    echo ""
    echo "To install PostgreSQL:"
    echo "  macOS:   brew install postgresql@16"
    echo "  Ubuntu:  sudo apt install postgresql postgresql-contrib"
    echo "  CentOS:  sudo yum install postgresql-server postgresql-contrib"
    echo ""
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" &> /dev/null; then
    echo "Error: PostgreSQL is not running!"
    echo ""
    echo "To start PostgreSQL:"
    echo "  macOS:   brew services start postgresql@16"
    echo "  Ubuntu:  sudo systemctl start postgresql"
    echo ""
    exit 1
fi

echo "Creating database and user..."
echo ""

# Create database and user (using postgres superuser)
# For local development, this assumes you can connect as postgres without password
# For production, you may need to modify this

sudo -u postgres psql <<EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$DB_USER') THEN
        CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE $DB_NAME OWNER $DB_USER'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;

-- For PostgreSQL 15+, grant schema permissions
\c $DB_NAME
GRANT ALL ON SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Database created successfully!"
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
    echo ""
    echo "If you're on macOS and using Homebrew PostgreSQL:"
    echo "  Try running: psql postgres -c \"CREATE DATABASE $DB_NAME;\""
    echo "  Then: psql postgres -c \"CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';\""
    echo "  Then: psql postgres -c \"GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;\""
    echo ""
    exit 1
fi
