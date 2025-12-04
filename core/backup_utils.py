"""
Database Backup Utilities

Provides comprehensive backup and restore functionality for critical situations.
Supports automatic backups, manual backups, and restoration.
"""

import os
import shutil
import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from django.conf import settings
from django.core.management import call_command
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class BackupManager:
    """Manages database backups and restoration"""

    def __init__(self, backup_dir: Optional[str] = None):
        """
        Initialize backup manager

        Args:
            backup_dir: Custom backup directory (defaults to project_root/backups)
        """
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = Path(settings.BASE_DIR) / 'backups'

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Metadata file
        self.metadata_file = self.backup_dir / 'backup_metadata.json'

    def create_backup(
        self,
        name: Optional[str] = None,
        description: str = '',
        compress: bool = True,
        tags: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Create a database backup

        Args:
            name: Custom backup name (defaults to timestamp)
            description: Description of this backup
            compress: Whether to compress the backup
            tags: List of tags (e.g., ['migration', 'production'])

        Returns:
            Dict with backup information (filename, path, size, etc.)
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if not name:
            name = f'backup_{timestamp}'

        # Clean name (remove spaces and special chars)
        clean_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in name)

        # Create backup filename
        backup_filename = f'{clean_name}_{timestamp}.json'
        if compress:
            backup_filename += '.gz'

        backup_path = self.backup_dir / backup_filename

        try:
            logger.info(f'Creating backup: {backup_filename}')

            # Create the backup using Django's dumpdata
            if compress:
                # Create temporary uncompressed file
                temp_path = self.backup_dir / f'temp_{timestamp}.json'
                with open(temp_path, 'w') as f:
                    call_command('dumpdata', stdout=f, indent=2)

                # Compress it
                with open(temp_path, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

                # Remove temp file
                temp_path.unlink()
            else:
                with open(backup_path, 'w') as f:
                    call_command('dumpdata', stdout=f, indent=2)

            # Get file size
            file_size = backup_path.stat().st_size

            # Create metadata
            metadata = {
                'filename': backup_filename,
                'path': str(backup_path),
                'timestamp': timestamp,
                'datetime': datetime.now().isoformat(),
                'name': clean_name,
                'description': description,
                'compressed': compress,
                'size_bytes': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'tags': tags or [],
                'database': str(connection.settings_dict['NAME']),
                'django_version': settings.DJANGO_VERSION if hasattr(settings, 'DJANGO_VERSION') else 'unknown'
            }

            # Save metadata
            self._save_backup_metadata(metadata)

            logger.info(f'Backup created successfully: {backup_filename} ({metadata["size_mb"]} MB)')

            return metadata

        except Exception as e:
            logger.error(f'Backup failed: {str(e)}')
            # Clean up partial backup if exists
            if backup_path.exists():
                backup_path.unlink()
            raise

    def restore_backup(
        self,
        backup_filename: str,
        confirm: bool = False,
        create_backup_before_restore: bool = True
    ) -> bool:
        """
        Restore database from a backup

        Args:
            backup_filename: Name of the backup file to restore
            confirm: Must be True to actually restore (safety check)
            create_backup_before_restore: Create a backup before restoring

        Returns:
            True if successful
        """
        if not confirm:
            raise ValueError(
                "Must set confirm=True to restore. This will overwrite current database!"
            )

        backup_path = self.backup_dir / backup_filename

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_filename}")

        try:
            # Create safety backup before restore
            if create_backup_before_restore:
                logger.info('Creating safety backup before restore...')
                self.create_backup(
                    name='pre_restore_safety',
                    description=f'Auto-backup before restoring {backup_filename}',
                    tags=['safety', 'auto']
                )

            logger.info(f'Restoring from backup: {backup_filename}')

            # Flush current database
            logger.info('Flushing current database...')
            call_command('flush', interactive=False, verbosity=0)

            # Restore from backup
            if backup_filename.endswith('.gz'):
                # Decompress and load
                with gzip.open(backup_path, 'rb') as f:
                    call_command('loaddata', '-', stdin=f)
            else:
                # Load directly
                call_command('loaddata', str(backup_path))

            logger.info(f'Database restored successfully from {backup_filename}')
            return True

        except Exception as e:
            logger.error(f'Restore failed: {str(e)}')
            raise

    def list_backups(
        self,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None,
        sort_by: str = 'datetime'
    ) -> List[Dict]:
        """
        List available backups

        Args:
            tags: Filter by tags
            limit: Limit number of results
            sort_by: Sort by field ('datetime', 'size', 'name')

        Returns:
            List of backup metadata dicts
        """
        metadata = self._load_all_metadata()

        # Filter by tags if specified
        if tags:
            metadata = [
                m for m in metadata
                if any(tag in m.get('tags', []) for tag in tags)
            ]

        # Sort
        reverse = True  # Newest first by default
        if sort_by == 'datetime':
            metadata.sort(key=lambda x: x.get('datetime', ''), reverse=reverse)
        elif sort_by == 'size':
            metadata.sort(key=lambda x: x.get('size_bytes', 0), reverse=reverse)
        elif sort_by == 'name':
            metadata.sort(key=lambda x: x.get('name', ''), reverse=False)

        # Limit results
        if limit:
            metadata = metadata[:limit]

        return metadata

    def delete_backup(self, backup_filename: str) -> bool:
        """
        Delete a backup file

        Args:
            backup_filename: Name of backup to delete

        Returns:
            True if successful
        """
        backup_path = self.backup_dir / backup_filename

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_filename}")

        try:
            # Remove file
            backup_path.unlink()

            # Remove from metadata
            self._remove_backup_metadata(backup_filename)

            logger.info(f'Backup deleted: {backup_filename}')
            return True

        except Exception as e:
            logger.error(f'Failed to delete backup: {str(e)}')
            raise

    def cleanup_old_backups(self, keep_days: int = 30, keep_count: int = 10) -> int:
        """
        Clean up old backups

        Args:
            keep_days: Keep backups from last N days
            keep_count: Keep at least N most recent backups

        Returns:
            Number of backups deleted
        """
        all_backups = self.list_backups(sort_by='datetime')

        if len(all_backups) <= keep_count:
            return 0  # Keep at least keep_count backups

        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0

        # Keep the most recent keep_count backups
        backups_to_consider = all_backups[keep_count:]

        for backup in backups_to_consider:
            backup_date = datetime.fromisoformat(backup['datetime'])
            if backup_date < cutoff_date:
                try:
                    self.delete_backup(backup['filename'])
                    deleted_count += 1
                except Exception as e:
                    logger.error(f'Failed to delete old backup {backup["filename"]}: {str(e)}')

        logger.info(f'Cleaned up {deleted_count} old backups')
        return deleted_count

    def get_backup_info(self, backup_filename: str) -> Optional[Dict]:
        """Get metadata for a specific backup"""
        all_metadata = self._load_all_metadata()
        for metadata in all_metadata:
            if metadata['filename'] == backup_filename:
                return metadata
        return None

    def _save_backup_metadata(self, metadata: Dict):
        """Save backup metadata to index file"""
        all_metadata = self._load_all_metadata()
        all_metadata.append(metadata)

        with open(self.metadata_file, 'w') as f:
            json.dump(all_metadata, f, indent=2)

    def _remove_backup_metadata(self, backup_filename: str):
        """Remove backup metadata from index file"""
        all_metadata = self._load_all_metadata()
        all_metadata = [m for m in all_metadata if m['filename'] != backup_filename]

        with open(self.metadata_file, 'w') as f:
            json.dump(all_metadata, f, indent=2)

    def _load_all_metadata(self) -> List[Dict]:
        """Load all backup metadata"""
        if not self.metadata_file.exists():
            return []

        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning('Corrupted metadata file, returning empty list')
            return []


# Convenience functions for quick access

def create_backup(
    name: Optional[str] = None,
    description: str = '',
    tags: Optional[List[str]] = None
) -> Dict[str, str]:
    """
    Quick function to create a backup

    Usage:
        from core.backup_utils import create_backup
        create_backup(name='before_migration', tags=['migration'])
    """
    manager = BackupManager()
    return manager.create_backup(name=name, description=description, tags=tags)


def restore_backup(backup_filename: str, confirm: bool = False) -> bool:
    """
    Quick function to restore a backup

    Usage:
        from core.backup_utils import restore_backup
        restore_backup('backup_20231203_120000.json.gz', confirm=True)
    """
    manager = BackupManager()
    return manager.restore_backup(backup_filename, confirm=confirm)


def list_backups(tags: Optional[List[str]] = None, limit: int = 20) -> List[Dict]:
    """
    Quick function to list backups

    Usage:
        from core.backup_utils import list_backups
        backups = list_backups(tags=['migration'], limit=10)
    """
    manager = BackupManager()
    return manager.list_backups(tags=tags, limit=limit)
