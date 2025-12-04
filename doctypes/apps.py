from django.apps import AppConfig


class DoctypesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'doctypes'

    def ready(self):
        """Import signals when app is ready"""
        import doctypes.signals  # noqa
