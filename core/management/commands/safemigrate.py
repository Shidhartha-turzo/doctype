"""
Django management command for safe migrations with automatic backup

This command automatically creates a backup before running migrations,
providing a safety net for critical database changes.
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from core.backup_utils import BackupManager


class Command(BaseCommand):
    help = 'Run migrations with automatic backup (safe migration)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-backup',
            action='store_true',
            help='Skip automatic backup before migration'
        )

        parser.add_argument(
            '--backup-name',
            type=str,
            help='Custom name for the pre-migration backup'
        )

        # Pass through common migrate arguments
        parser.add_argument(
            'app_label',
            nargs='?',
            help='App label of an application to synchronize the state.'
        )

        parser.add_argument(
            'migration_name',
            nargs='?',
            help='Database state will be brought to the state after that migration.'
        )

        parser.add_argument(
            '--noinput',
            '--no-input',
            action='store_false',
            dest='interactive',
            help='Tells Django to NOT prompt the user for input of any kind.'
        )

        parser.add_argument(
            '--database',
            default='default',
            help='Nominates a database to synchronize. Defaults to the "default" database.'
        )

        parser.add_argument(
            '--fake',
            action='store_true',
            help='Mark migrations as run without actually running them.'
        )

        parser.add_argument(
            '--fake-initial',
            action='store_true',
            help='Detect if tables already exist and fake-apply initial migrations if so.'
        )

        parser.add_argument(
            '--plan',
            action='store_true',
            help='Shows a list of the migration actions that will be performed.'
        )

        parser.add_argument(
            '--run-syncdb',
            action='store_true',
            help='Creates tables for apps without migrations.'
        )

    def handle(self, *args, **options):
        skip_backup = options.get('skip_backup', False)
        backup_name = options.get('backup_name')

        # Create backup before migration (unless skipped)
        if not skip_backup:
            try:
                self.stdout.write(self.style.WARNING(
                    '\n=== Creating Safety Backup Before Migration ==='
                ))

                manager = BackupManager()

                # Generate backup name
                if not backup_name:
                    app_label = options.get('app_label')
                    migration_name = options.get('migration_name')

                    if app_label and migration_name:
                        backup_name = f'pre_migrate_{app_label}_{migration_name}'
                    elif app_label:
                        backup_name = f'pre_migrate_{app_label}'
                    else:
                        backup_name = 'pre_migrate_all'

                # Create backup
                metadata = manager.create_backup(
                    name=backup_name,
                    description='Automatic backup before migration',
                    tags=['migration', 'auto', 'safety']
                )

                self.stdout.write(self.style.SUCCESS(
                    f'Backup created: {metadata["filename"]} ({metadata["size_mb"]} MB)'
                ))
                self.stdout.write('')

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'WARNING: Backup failed: {str(e)}'
                ))
                self.stdout.write(self.style.ERROR(
                    'Migration aborted for safety. Use --skip-backup to proceed anyway.'
                ))
                return

        # Run migration
        self.stdout.write(self.style.WARNING(
            '=== Running Migration ==='
        ))

        # Build migrate command arguments
        migrate_args = []
        if options.get('app_label'):
            migrate_args.append(options['app_label'])
        if options.get('migration_name'):
            migrate_args.append(options['migration_name'])

        migrate_options = {
            'interactive': options.get('interactive', True),
            'database': options.get('database', 'default'),
            'fake': options.get('fake', False),
            'fake_initial': options.get('fake_initial', False),
            'plan': options.get('plan', False),
            'run_syncdb': options.get('run_syncdb', False),
            'verbosity': options.get('verbosity', 1),
        }

        try:
            call_command('migrate', *migrate_args, **migrate_options)

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                '=== Migration Completed Successfully ==='
            ))

            if not skip_backup:
                self.stdout.write(
                    f'Safety backup available: {metadata["filename"]}'
                )

        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR(
                f'=== Migration Failed: {str(e)} ==='
            ))

            if not skip_backup:
                self.stdout.write(self.style.WARNING(
                    f'\nYou can restore from backup: {metadata["filename"]}'
                ))
                self.stdout.write(
                    f'  python manage.py restorebackup {metadata["filename"]} --confirm'
                )

            raise
