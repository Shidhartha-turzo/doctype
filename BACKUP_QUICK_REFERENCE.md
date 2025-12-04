# Database Backup - Quick Reference

## Most Common Commands

### Create a Backup
```bash
# Quick backup (automatic naming)
python manage.py createbackup

# Named backup with description
python manage.py createbackup --name "before_migration" --description "Before adding MFA" --tags "migration"
```

### List Backups
```bash
# List recent backups
python manage.py listbackups

# List all backups
python manage.py listbackups --all

# Filter by tag
python manage.py listbackups --tags "production"
```

### Restore a Backup
```bash
# REQUIRES --confirm FLAG
python manage.py restorebackup FILENAME --confirm
```

### Safe Migration (Recommended)
```bash
# Automatically creates backup before migration
python manage.py safemigrate
```

### Cleanup Old Backups
```bash
# Keep last 30 days and at least 10 backups
python manage.py cleanbackups

# Delete specific backup
python manage.py cleanbackups --delete FILENAME
```

---

## Critical Situations

### Before Database Migration
```bash
# Option 1: Safe migration (auto-backup + migrate)
python manage.py safemigrate

# Option 2: Manual
python manage.py createbackup --name "pre_migrate" --tags "migration"
python manage.py migrate
```

### Before Production Deployment
```bash
python manage.py createbackup --name "production_$(date +%Y%m%d)" --tags "production,deployment"
```

### Emergency Restore
```bash
# 1. List available backups
python manage.py listbackups --tags "production"

# 2. Restore from backup (CAUTION: Deletes current data!)
python manage.py restorebackup FILENAME --confirm
```

### Before Data Import/Cleanup
```bash
# Create safety backup
python manage.py createbackup --name "before_cleanup" --tags "safety"

# ... perform operations ...

# If needed, restore
python manage.py restorebackup FILENAME --confirm
```

---

## Python API Quick Examples

```python
from core.backup_utils import create_backup, list_backups, restore_backup

# Create backup
backup = create_backup(name='my_backup', tags=['manual'])
print(f"Created: {backup['filename']}")

# List backups
backups = list_backups(tags=['production'], limit=5)

# Restore (use with extreme caution!)
restore_backup('backup_file.json.gz', confirm=True)
```

---

## Backup Tags Reference

Common tags to use:
- `production` - Production backups
- `staging` - Staging backups
- `migration` - Before migrations
- `deployment` - Before deployments
- `manual` - Manually created
- `auto` - Auto-created
- `daily` - Daily backups
- `weekly` - Weekly backups
- `safety` - Safety/emergency backups

---

## Important Notes

1. Backups are stored in: `/path/to/project/backups/`
2. Backups are compressed by default (.gz)
3. Restore ALWAYS requires `--confirm` flag
4. Restore automatically creates a safety backup first
5. Use `safemigrate` instead of `migrate` for automatic backups

---

## Files Created

- `core/backup_utils.py` - Backup utility module
- `core/management/commands/createbackup.py` - Create backup command
- `core/management/commands/restorebackup.py` - Restore backup command
- `core/management/commands/listbackups.py` - List backups command
- `core/management/commands/cleanbackups.py` - Cleanup backups command
- `core/management/commands/safemigrate.py` - Safe migration command
- `BACKUP_GUIDE.md` - Complete documentation
- `BACKUP_QUICK_REFERENCE.md` - This quick reference

---

For complete documentation, see **BACKUP_GUIDE.md**
