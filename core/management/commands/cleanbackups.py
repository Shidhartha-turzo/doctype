"""
Django management command to clean up old backups
"""

from django.core.management.base import BaseCommand, CommandError
from core.backup_utils import BackupManager


class Command(BaseCommand):
    help = 'Clean up old database backups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-days',
            type=int,
            default=30,
            help='Keep backups from last N days (default: 30)'
        )

        parser.add_argument(
            '--keep-count',
            type=int,
            default=10,
            help='Keep at least N most recent backups (default: 10)'
        )

        parser.add_argument(
            '--delete',
            type=str,
            help='Delete a specific backup by filename'
        )

    def handle(self, *args, **options):
        keep_days = options.get('keep_days', 30)
        keep_count = options.get('keep_count', 10)
        delete_specific = options.get('delete')

        try:
            manager = BackupManager()

            if delete_specific:
                # Delete specific backup
                self.stdout.write(f'Deleting backup: {delete_specific}')

                # Show backup info first
                backup_info = manager.get_backup_info(delete_specific)
                if backup_info:
                    self.stdout.write(f'  Name: {backup_info.get("name", "N/A")}')
                    self.stdout.write(f'  Date: {backup_info.get("datetime", "N/A")}')
                    self.stdout.write(f'  Size: {backup_info.get("size_mb", "N/A")} MB')

                manager.delete_backup(delete_specific)
                self.stdout.write(self.style.SUCCESS(
                    f'Backup deleted: {delete_specific}'
                ))

            else:
                # Clean up old backups
                self.stdout.write(
                    f'Cleaning up backups older than {keep_days} days...'
                )
                self.stdout.write(
                    f'Keeping at least {keep_count} most recent backups'
                )

                deleted_count = manager.cleanup_old_backups(
                    keep_days=keep_days,
                    keep_count=keep_count
                )

                if deleted_count > 0:
                    self.stdout.write(self.style.SUCCESS(
                        f'\nDeleted {deleted_count} old backup(s)'
                    ))
                else:
                    self.stdout.write('No old backups to delete')

        except FileNotFoundError as e:
            raise CommandError(str(e))
        except Exception as e:
            raise CommandError(f'Cleanup failed: {str(e)}')
