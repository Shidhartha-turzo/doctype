"""
Django management command to list available backups
"""

from django.core.management.base import BaseCommand
from core.backup_utils import BackupManager
from datetime import datetime


class Command(BaseCommand):
    help = 'List available database backups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tags',
            type=str,
            help='Filter by tags (comma-separated)'
        )

        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='Limit number of results (default: 20)'
        )

        parser.add_argument(
            '--all',
            action='store_true',
            help='Show all backups (ignore limit)'
        )

    def handle(self, *args, **options):
        tags_str = options.get('tags', '')
        limit = None if options.get('all') else options.get('limit', 20)

        # Parse tags
        tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else None

        try:
            manager = BackupManager()
            backups = manager.list_backups(tags=tags, limit=limit)

            if not backups:
                self.stdout.write('No backups found.')
                return

            self.stdout.write(f'\nFound {len(backups)} backup(s):\n')

            for i, backup in enumerate(backups, 1):
                # Parse datetime
                try:
                    dt = datetime.fromisoformat(backup['datetime'])
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = backup.get('datetime', 'Unknown')

                self.stdout.write(f'{i}. {backup["filename"]}')
                self.stdout.write(f'   Name: {backup.get("name", "N/A")}')
                self.stdout.write(f'   Date: {date_str}')
                self.stdout.write(f'   Size: {backup.get("size_mb", "N/A")} MB')

                if backup.get('description'):
                    self.stdout.write(f'   Description: {backup["description"]}')

                if backup.get('tags'):
                    tags_display = ', '.join(backup['tags'])
                    self.stdout.write(f'   Tags: {tags_display}')

                self.stdout.write('')

            # Show backup directory
            self.stdout.write(f'Backup directory: {manager.backup_dir}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error listing backups: {str(e)}'))
