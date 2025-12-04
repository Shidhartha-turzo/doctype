# Database Backup Guide

Complete guide for database backup and restore operations in critical situations.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Management Commands](#management-commands)
3. [Critical Situations](#critical-situations)
4. [Python API](#python-api)
5. [Backup Strategy](#backup-strategy)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Create a Backup
```bash
# Simple backup with automatic naming
python manage.py createbackup

# Named backup with description
python manage.py createbackup --name "before_feature_x" --description "Before adding feature X"

# Backup with tags for organization
python manage.py createbackup --name "production_snapshot" --tags "production,daily"
```

### List Backups
```bash
# List all recent backups
python manage.py listbackups

# List all backups (no limit)
python manage.py listbackups --all

# Filter by tags
python manage.py listbackups --tags "migration,production"
```

### Restore a Backup
```bash
# IMPORTANT: Requires --confirm flag for safety
python manage.py restorebackup backup_20231203_120000.json.gz --confirm

# Skip safety backup before restore (not recommended)
python manage.py restorebackup backup_20231203_120000.json.gz --confirm --no-safety-backup
```

---

## Management Commands

### 1. createbackup

Create a database backup.

**Usage:**
```bash
python manage.py createbackup [options]
```

**Options:**
- `--name NAME` - Custom name for backup (defaults to timestamp)
- `--description DESC` - Description of this backup
- `--no-compress` - Skip compression (faster but larger files)
- `--tags TAGS` - Comma-separated tags (e.g., "migration,production")

**Examples:**
```bash
# Before migration
python manage.py createbackup --name "pre_migration_v2" --tags "migration"

# Daily production backup
python manage.py createbackup --name "daily_backup" --tags "production,daily"

# Quick uncompressed backup
python manage.py createbackup --no-compress
```

---

### 2. restorebackup

Restore database from a backup.

**Usage:**
```bash
python manage.py restorebackup BACKUP_FILENAME --confirm
```

**Options:**
- `BACKUP_FILENAME` - Name of backup file (required)
- `--confirm` - Required flag to confirm restoration
- `--no-safety-backup` - Skip creating safety backup before restore

**Examples:**
```bash
# Restore from specific backup
python manage.py restorebackup backup_20231203_120000.json.gz --confirm

# Restore without safety backup (faster but riskier)
python manage.py restorebackup backup_20231203_120000.json.gz --confirm --no-safety-backup
```

**Safety Features:**
- Automatically creates a safety backup before restoring (unless --no-safety-backup)
- Requires explicit --confirm flag to prevent accidents
- Shows backup information before restoring

---

### 3. listbackups

List available backups.

**Usage:**
```bash
python manage.py listbackups [options]
```

**Options:**
- `--tags TAGS` - Filter by tags (comma-separated)
- `--limit N` - Limit results (default: 20)
- `--all` - Show all backups (ignore limit)

**Examples:**
```bash
# List 20 most recent backups
python manage.py listbackups

# List all migration backups
python manage.py listbackups --tags "migration" --all

# List 5 most recent production backups
python manage.py listbackups --tags "production" --limit 5
```

---

### 4. cleanbackups

Clean up old backups or delete specific backup.

**Usage:**
```bash
python manage.py cleanbackups [options]
```

**Options:**
- `--keep-days N` - Keep backups from last N days (default: 30)
- `--keep-count N` - Keep at least N most recent backups (default: 10)
- `--delete FILENAME` - Delete specific backup by filename

**Examples:**
```bash
# Clean up backups older than 30 days (keeps at least 10 most recent)
python manage.py cleanbackups

# Keep only 7 days of backups
python manage.py cleanbackups --keep-days 7 --keep-count 5

# Delete specific backup
python manage.py cleanbackups --delete backup_20231201_120000.json.gz
```

---

### 5. safemigrate

Run migrations with automatic backup.

**Usage:**
```bash
python manage.py safemigrate [app_label] [migration_name] [options]
```

**Options:**
- `--skip-backup` - Skip automatic backup
- `--backup-name NAME` - Custom name for pre-migration backup
- All standard `migrate` command options

**Examples:**
```bash
# Safe migration with auto-backup
python manage.py safemigrate

# Safe migration for specific app
python manage.py safemigrate authentication

# Safe migration to specific migration
python manage.py safemigrate authentication 0003_add_mfa

# Skip backup (not recommended for production)
python manage.py safemigrate --skip-backup

# Custom backup name
python manage.py safemigrate --backup-name "before_auth_changes"
```

**How it Works:**
1. Automatically creates a backup before migration
2. Tags backup as "migration", "auto", "safety"
3. Runs the migration
4. On failure, shows command to restore from backup

---

## Critical Situations

### Before Database Migration

**Always create a backup before migrations:**

```bash
# Option 1: Use safemigrate (recommended)
python manage.py safemigrate

# Option 2: Manual backup + migrate
python manage.py createbackup --name "pre_migrate" --tags "migration"
python manage.py migrate
```

### Before Major Code Changes

```bash
# Create snapshot before deploying major features
python manage.py createbackup --name "before_feature_x" --description "Before deploying feature X" --tags "deployment,feature"
```

### Before Data Import/Cleanup

```bash
# Backup before bulk operations
python manage.py createbackup --name "before_data_cleanup" --tags "data-ops"

# ... perform data operations ...

# If something went wrong, restore
python manage.py restorebackup backup_20231203_120000.json.gz --confirm
```

### Production Deployment

```bash
# Create tagged production backup
python manage.py createbackup --name "production_$(date +%Y%m%d)" --tags "production,deployment"
```

### Emergency Restore

```bash
# List available backups
python manage.py listbackups --tags "production"

# Restore from most recent production backup
python manage.py restorebackup backup_20231203_120000.json.gz --confirm
```

---

## Python API

You can use the backup utilities directly in Python code.

### Quick Functions

```python
from core.backup_utils import create_backup, restore_backup, list_backups

# Create backup
backup_info = create_backup(
    name='my_backup',
    description='Backup before risky operation',
    tags=['critical', 'manual']
)
print(f"Backup created: {backup_info['filename']}")

# List backups
backups = list_backups(tags=['migration'], limit=10)
for backup in backups:
    print(f"{backup['filename']} - {backup['size_mb']} MB")

# Restore backup (use with caution!)
restore_backup('backup_20231203_120000.json.gz', confirm=True)
```

### Advanced Usage with BackupManager

```python
from core.backup_utils import BackupManager

# Initialize manager
manager = BackupManager()

# Create backup with custom settings
metadata = manager.create_backup(
    name='critical_backup',
    description='Before major refactoring',
    compress=True,
    tags=['refactoring', 'critical']
)

# Get backup info
backup_info = manager.get_backup_info('backup_20231203_120000.json.gz')
if backup_info:
    print(f"Size: {backup_info['size_mb']} MB")
    print(f"Tags: {backup_info['tags']}")

# Clean up old backups
deleted = manager.cleanup_old_backups(keep_days=30, keep_count=10)
print(f"Deleted {deleted} old backups")

# Delete specific backup
manager.delete_backup('old_backup.json.gz')
```

### In Django Views/Signals

```python
from django.db.models.signals import pre_save
from django.dispatch import receiver
from core.backup_utils import create_backup

@receiver(pre_save, sender=CriticalModel)
def backup_before_critical_change(sender, instance, **kwargs):
    """Auto-backup before changing critical data"""
    if instance.pk:  # Only on updates
        create_backup(
            name=f'before_critical_update_{instance.pk}',
            tags=['auto', 'critical'],
            description=f'Auto backup before updating {sender.__name__} {instance.pk}'
        )
```

---

## Backup Strategy

### Recommended Backup Schedule

**Development:**
- Before each migration
- Before major code changes
- Manual backups when testing risky operations

**Staging:**
- Daily automated backups
- Before each deployment
- Before data imports/migrations

**Production:**
- Multiple daily backups (e.g., every 6 hours)
- Before every deployment
- Before and after migrations
- Monthly archival backups

### Backup Retention Policy

**Example Policy:**
```python
# Daily cleanup (run as cron job)
# Keeps: Last 10 backups + anything from last 30 days
python manage.py cleanbackups --keep-days 30 --keep-count 10
```

**Recommended Retention:**
- Development: 7 days, keep 5 backups
- Staging: 30 days, keep 10 backups
- Production: 90 days, keep 20 backups

### Automated Backups

**Using Cron (Linux/Mac):**

```bash
# Edit crontab
crontab -e

# Add backup jobs
# Daily backup at 2 AM
0 2 * * * cd /path/to/doctype && source .venv/bin/activate && python manage.py createbackup --tags "daily,auto"

# Weekly cleanup on Sunday at 3 AM
0 3 * * 0 cd /path/to/doctype && source .venv/bin/activate && python manage.py cleanbackups --keep-days 30
```

**Using Django Management Command in Celery:**

```python
# tasks.py
from celery import shared_task
from core.backup_utils import create_backup, BackupManager

@shared_task
def create_daily_backup():
    """Create daily automated backup"""
    create_backup(
        name=f'daily_auto_{datetime.now().strftime("%Y%m%d")}',
        tags=['daily', 'auto', 'production']
    )

@shared_task
def cleanup_old_backups():
    """Clean up old backups weekly"""
    manager = BackupManager()
    manager.cleanup_old_backups(keep_days=30, keep_count=10)
```

---

## Best Practices

### 1. Always Backup Before Risky Operations

**Risky operations include:**
- Database migrations
- Bulk data updates/deletes
- Schema changes
- Production deployments
- Data imports from external sources

```bash
# Good practice
python manage.py createbackup --name "before_bulk_delete" --tags "safety"
python manage.py custom_cleanup_command
```

### 2. Use Descriptive Names and Tags

```bash
# Good - descriptive
python manage.py createbackup --name "before_auth_migration" --tags "migration,auth" --description "Before adding MFA support"

# Bad - not descriptive
python manage.py createbackup
```

### 3. Verify Backups Regularly

```bash
# List recent backups to verify they exist
python manage.py listbackups --limit 5

# Check backup size (should not be 0)
ls -lh backups/
```

### 4. Test Restore Process

**In development environment:**
```bash
# Create test backup
python manage.py createbackup --name "test_restore"

# Make some changes
python manage.py shell
>>> from authentication.models import User
>>> User.objects.create_user(email='test@test.com', password='test')
>>> exit()

# Restore and verify
python manage.py restorebackup backup_test_restore_*.json.gz --confirm
```

### 5. Use safemigrate in Production

```bash
# Instead of regular migrate
python manage.py safemigrate

# This automatically creates backup before migration
```

### 6. Tag Backups Appropriately

**Recommended tags:**
- `production` - Production environment backups
- `staging` - Staging environment backups
- `migration` - Before database migrations
- `deployment` - Before code deployments
- `manual` - Manually created backups
- `auto` - Automatically created backups
- `daily` - Daily scheduled backups
- `weekly` - Weekly scheduled backups
- `safety` - Safety/emergency backups
- `critical` - Critical operation backups

### 7. Monitor Backup Storage

```bash
# Check backup directory size
du -sh backups/

# Count backups
ls backups/*.json.gz | wc -l
```

### 8. Secure Backup Files

```bash
# Set appropriate permissions
chmod 600 backups/*.json.gz
chmod 700 backups/

# Backup directory should be in .gitignore
echo "backups/" >> .gitignore
```

---

## Troubleshooting

### Backup Failed: Permission Denied

**Problem:** Cannot write to backup directory

**Solution:**
```bash
# Create backup directory with correct permissions
mkdir -p backups
chmod 755 backups
```

### Restore Failed: Database Locked

**Problem:** Database is locked during restore

**Solution:**
```bash
# Stop application server first
# Kill background shells if running
python manage.py restorebackup backup.json.gz --confirm
```

### Backup Too Large

**Problem:** Backup files are very large

**Solutions:**
```bash
# 1. Ensure compression is enabled (default)
python manage.py createbackup  # Automatically compresses

# 2. Clean up old data before backup
python manage.py clearsessions  # Remove old sessions
python manage.py flushexpiredtokens  # Remove expired tokens

# 3. Exclude specific apps if needed (manual)
python manage.py dumpdata --exclude auth.permission --exclude contenttypes > backup.json
```

### Can't Find Backup File

**Problem:** Backup file not showing in list

**Solution:**
```bash
# Check backup directory
ls -la backups/

# Rebuild metadata (if corrupted)
python manage.py listbackups --all

# Check specific file exists
python manage.py listbackups | grep "backup_name"
```

### Restore Doesn't Include Recent Data

**Problem:** Restored data is older than expected

**Explanation:** Backups are snapshots from when they were created. Check backup creation time:

```bash
python manage.py listbackups
# Look at the "Date" column
```

### Out of Disk Space

**Problem:** Cannot create backup due to disk space

**Solutions:**
```bash
# 1. Clean up old backups
python manage.py cleanbackups --keep-days 7 --keep-count 3

# 2. Check disk usage
df -h

# 3. Delete specific old backups
python manage.py cleanbackups --delete old_backup.json.gz
```

---

## Backup File Locations

**Default backup directory:**
```
/Users/spoofing/Documents/DT/doctype/backups/
```

**Backup file naming:**
```
backup_{name}_{timestamp}.json.gz
```

**Metadata file:**
```
backups/backup_metadata.json
```

**Example files:**
```
backups/
├── backup_daily_20231203_020000.json.gz
├── backup_pre_migrate_20231203_100000.json.gz
├── backup_production_20231203_140000.json.gz
└── backup_metadata.json
```

---

## Emergency Recovery Checklist

If something goes wrong:

1. **Stop the application**
   ```bash
   # Kill runserver or gunicorn
   pkill -f "python manage.py runserver"
   ```

2. **List available backups**
   ```bash
   python manage.py listbackups --all
   ```

3. **Identify the correct backup**
   - Look for the most recent backup before the problem
   - Check tags and description
   - Note the filename

4. **Restore from backup**
   ```bash
   python manage.py restorebackup BACKUP_FILENAME --confirm
   ```

5. **Verify restoration**
   ```bash
   python manage.py shell
   >>> from authentication.models import User
   >>> User.objects.count()
   >>> # Verify data looks correct
   ```

6. **Restart application**
   ```bash
   python manage.py runserver
   ```

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Deploy with Backup

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Create Pre-Deployment Backup
        run: |
          python manage.py createbackup \
            --name "pre_deploy_${{ github.sha }}" \
            --tags "deployment,auto,ci" \
            --description "Backup before deployment of commit ${{ github.sha }}"

      - name: Run Safe Migration
        run: |
          python manage.py safemigrate

      - name: Deploy Application
        run: |
          # Your deployment steps here
          echo "Deploying..."

      - name: Cleanup Old Backups
        if: success()
        run: |
          python manage.py cleanbackups --keep-days 30 --keep-count 20
```

---

## Summary

**Key Commands:**
```bash
# Create backup
python manage.py createbackup --name "my_backup" --tags "migration"

# List backups
python manage.py listbackups

# Restore backup
python manage.py restorebackup FILENAME --confirm

# Safe migration
python manage.py safemigrate

# Cleanup
python manage.py cleanbackups
```

**Remember:**
- Always backup before risky operations
- Test your restore process regularly
- Use descriptive names and tags
- Monitor backup storage
- Automate regular backups

---

**Last Updated:** 2025-12-03
**Version:** 1.0
