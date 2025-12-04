"""
Django management command to restore database from backup
"""

from django.core.management.base import BaseCommand, CommandError
from core.backup_utils import BackupManager


class Command(BaseCommand):
    help = 'Restore database from a backup'

    def add_arguments(self, parser):
        parser.add_argument(
            'backup_filename',
            type=str,
            help='Backup file to restore from'
        )

        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm restoration (required for safety)'
        )

        parser.add_argument(
            '--no-safety-backup',
            action='store_true',
            help='Skip creating a safety backup before restore'
        )

    def handle(self, *args, **options):
        backup_filename = options['backup_filename']
        confirm = options.get('confirm', False)
        create_safety_backup = not options.get('no_safety_backup', False)

        if not confirm:
            self.stdout.write(self.style.ERROR(
                '\nERROR: Restoration requires explicit confirmation!'
            ))
            self.stdout.write(
                'This will DELETE all current data and replace it with the backup.'
            )
            self.stdout.write('\nTo proceed, add --confirm flag:')
            self.stdout.write(
                f'  python manage.py restorebackup {backup_filename} --confirm'
            )
            return

        try:
            manager = BackupManager()

            # Show backup info
            backup_info = manager.get_backup_info(backup_filename)
            if backup_info:
                self.stdout.write('\nBackup Information:')
                self.stdout.write(f'  Name: {backup_info.get("name", "N/A")}')
                self.stdout.write(f'  Date: {backup_info.get("datetime", "N/A")}')
                self.stdout.write(f'  Size: {backup_info.get("size_mb", "N/A")} MB')
                if backup_info.get('description'):
                    self.stdout.write(f'  Description: {backup_info["description"]}')
                if backup_info.get('tags'):
                    self.stdout.write(f'  Tags: {", ".join(backup_info["tags"])}')
                self.stdout.write('')

            self.stdout.write(self.style.WARNING(
                'WARNING: This will DELETE all current data!'
            ))

            if create_safety_backup:
                self.stdout.write('Creating safety backup before restore...')

            self.stdout.write(f'Restoring from: {backup_filename}')

            # Perform restoration
            manager.restore_backup(
                backup_filename,
                confirm=True,
                create_backup_before_restore=create_safety_backup
            )

            self.stdout.write(self.style.SUCCESS(
                f'\nDatabase restored successfully from {backup_filename}!'
            ))

        except FileNotFoundError:
            raise CommandError(f'Backup file not found: {backup_filename}')
        except Exception as e:
            raise CommandError(f'Restore failed: {str(e)}')
