"""
Utility for creating Django models dynamically at runtime based on Doctype schemas.
"""
from django.db import models, connection
from django.apps import apps
from django.core.management.color import no_style
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


# Cache for dynamically created models
_dynamic_models_cache = {}


def get_field_class(field_type, field_config):
    """Convert schema field type to Django field class"""
    field_map = {
        'string': models.CharField,
        'text': models.TextField,
        'integer': models.IntegerField,
        'decimal': models.DecimalField,
        'boolean': models.BooleanField,
        'date': models.DateField,
        'datetime': models.DateTimeField,
        'json': models.JSONField,
    }

    field_class = field_map.get(field_type)
    if not field_class:
        raise ValueError(f"Unsupported field type: {field_type}")

    # Build field kwargs from config
    kwargs = {}

    if 'required' in field_config:
        kwargs['null'] = not field_config['required']
        kwargs['blank'] = not field_config['required']

    if 'default' in field_config:
        kwargs['default'] = field_config['default']

    if 'max_length' in field_config and field_type == 'string':
        kwargs['max_length'] = field_config['max_length']
    elif field_type == 'string' and 'max_length' not in kwargs:
        kwargs['max_length'] = 255

    if 'unique' in field_config:
        kwargs['unique'] = field_config['unique']

    if 'max_digits' in field_config and field_type == 'decimal':
        kwargs['max_digits'] = field_config['max_digits']

    if 'decimal_places' in field_config and field_type == 'decimal':
        kwargs['decimal_places'] = field_config['decimal_places']

    if 'help_text' in field_config:
        kwargs['help_text'] = field_config['help_text']

    return field_class(**kwargs)


def create_dynamic_model(doctype):
    """
    Create a Django model class dynamically based on the doctype schema.

    Args:
        doctype: Doctype instance with schema definition

    Returns:
        Django model class
    """
    cache_key = f"{doctype.slug}_v{doctype.version}"

    # Return cached model if it exists
    if cache_key in _dynamic_models_cache:
        return _dynamic_models_cache[cache_key]

    # Base fields that all dynamic models have
    attrs = {
        '__module__': 'doctypes.models',
        'doctype_id': models.IntegerField(db_index=True),
        'data': models.JSONField(default=dict, help_text="Additional unstructured data"),
        'created_at': models.DateTimeField(auto_now_add=True),
        'updated_at': models.DateTimeField(auto_now=True),
    }

    # Add custom fields from schema
    schema = doctype.schema
    for field_config in schema.get('fields', []):
        field_name = field_config['name']
        field_type = field_config['type']
        attrs[field_name] = get_field_class(field_type, field_config)

    # Meta class
    class Meta:
        app_label = 'doctypes'
        db_table = doctype.get_table_name()

    attrs['Meta'] = Meta
    attrs['__str__'] = lambda self: f"{doctype.name} #{self.pk}"

    # Create the model class
    model_name = doctype.get_model_class_name()
    model = type(model_name, (models.Model,), attrs)

    # Cache the model
    _dynamic_models_cache[cache_key] = model

    return model


def get_dynamic_model(doctype_slug):
    """Get a dynamic model by doctype slug"""
    from .models import Doctype

    try:
        doctype = Doctype.objects.get(slug=doctype_slug, is_active=True)
        return create_dynamic_model(doctype)
    except Doctype.DoesNotExist:
        raise ValueError(f"Doctype '{doctype_slug}' not found")


def create_table_for_doctype(doctype):
    """Create database table for the dynamic model"""
    model = create_dynamic_model(doctype)

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(model)

    return model


def drop_table_for_doctype(doctype):
    """Drop database table for the dynamic model"""
    model = create_dynamic_model(doctype)

    with connection.schema_editor() as schema_editor:
        schema_editor.delete_model(model)

    # Remove from cache
    cache_key = f"{doctype.slug}_v{doctype.version}"
    if cache_key in _dynamic_models_cache:
        del _dynamic_models_cache[cache_key]


def table_exists(table_name):
    """Check if a table exists in the database"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            );
        """, [table_name])
        return cursor.fetchone()[0]
