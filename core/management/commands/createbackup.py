"""
Django management command to create database backups
"""

from django.core.management.base import BaseCommand, CommandError
from core.backup_utils import BackupManager


class Command(BaseCommand):
    help = 'Create a database backup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            help='Custom name for the backup (defaults to timestamp)'
        )

        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='Description of this backup'
        )

        parser.add_argument(
            '--no-compress',
            action='store_true',
            help='Do not compress the backup'
        )

        parser.add_argument(
            '--tags',
            type=str,
            help='Comma-separated tags (e.g., "migration,production")'
        )

    def handle(self, *args, **options):
        name = options.get('name')
        description = options.get('description', '')
        compress = not options.get('no_compress', False)
        tags_str = options.get('tags', '')

        # Parse tags
        tags = [t.strip() for t in tags_str.split(',') if t.strip()] if tags_str else []

        try:
            self.stdout.write('Creating database backup...')

            manager = BackupManager()
            metadata = manager.create_backup(
                name=name,
                description=description,
                compress=compress,
                tags=tags
            )

            self.stdout.write(self.style.SUCCESS(
                f'\nBackup created successfully!'
            ))
            self.stdout.write(f'  Filename: {metadata["filename"]}')
            self.stdout.write(f'  Path: {metadata["path"]}')
            self.stdout.write(f'  Size: {metadata["size_mb"]} MB')
            if tags:
                self.stdout.write(f'  Tags: {", ".join(tags)}')
            if description:
                self.stdout.write(f'  Description: {description}')

        except Exception as e:
            raise CommandError(f'Backup failed: {str(e)}')
