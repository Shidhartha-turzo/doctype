"""
Django signals for hooking into document lifecycle

Integrates hook execution engine with Django's signal system
to automatically execute hooks on document operations.
"""

import logging
from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.db import transaction

from .models import Document
from .hook_engine import (
    HookEngine, HookExecutionError,
    execute_before_insert_hooks,
    execute_after_insert_hooks,
    execute_before_save_hooks,
    execute_after_save_hooks,
    execute_before_delete_hooks,
    execute_after_delete_hooks,
    execute_on_change_hooks
)
from .version_engine import create_version

logger = logging.getLogger(__name__)


# Track old document data for on_change detection
_document_old_data = {}


@receiver(pre_save, sender=Document)
def document_pre_save(sender, instance, **kwargs):
    """
    Execute before_save or before_insert hooks

    Runs before document is saved to database.
    Can modify document data or prevent save by raising exception.
    """
    global _document_old_data

    # Check if this is an insert or update
    is_new = instance.pk is None

    try:
        if is_new:
            # Execute before_insert hooks
            logger.debug(f"Executing before_insert hooks for {instance.doctype.name}")
            execute_before_insert_hooks(instance, user=getattr(instance, '_current_user', None))
        else:
            # Load old data for on_change detection
            try:
                old_instance = Document.objects.get(pk=instance.pk)
                _document_old_data[instance.pk] = old_instance.data.copy()
            except Document.DoesNotExist:
                _document_old_data[instance.pk] = {}

            # Execute before_save hooks
            logger.debug(f"Executing before_save hooks for {instance.doctype.name} #{instance.pk}")
            execute_before_save_hooks(instance, user=getattr(instance, '_current_user', None))

    except HookExecutionError as e:
        logger.error(f"Hook execution prevented save: {str(e)}")
        raise  # Re-raise to prevent save


@receiver(post_save, sender=Document)
def document_post_save(sender, instance, created, **kwargs):
    """
    Execute after_save or after_insert hooks

    Runs after document is saved to database.
    Also triggers on_change hooks if data changed.
    """
    global _document_old_data

    try:
        if created:
            # Execute after_insert hooks
            logger.debug(f"Executing after_insert hooks for {instance.doctype.name} #{instance.pk}")
            execute_after_insert_hooks(instance, user=getattr(instance, '_current_user', None))
        else:
            # Execute after_save hooks
            logger.debug(f"Executing after_save hooks for {instance.doctype.name} #{instance.pk}")
            execute_after_save_hooks(instance, user=getattr(instance, '_current_user', None))

            # Check for data changes and execute on_change hooks
            old_data = _document_old_data.get(instance.pk, {})
            if old_data and old_data != instance.data:
                logger.debug(f"Executing on_change hooks for {instance.doctype.name} #{instance.pk}")
                execute_on_change_hooks(
                    instance,
                    old_data,
                    user=getattr(instance, '_current_user', None)
                )

            # Clean up old data tracking
            if instance.pk in _document_old_data:
                del _document_old_data[instance.pk]

        # Create version automatically (after hooks)
        if not getattr(instance, '_skip_version_creation', False):
            try:
                create_version(
                    instance,
                    user=getattr(instance, '_current_user', None),
                    comment=getattr(instance, '_version_comment', '')
                )
                logger.debug(f"Created version for document {instance.doctype.name} #{instance.pk}")
            except Exception as e:
                logger.error(f"Error creating version: {str(e)}")

    except Exception as e:
        # Log error but don't prevent save completion
        logger.error(f"Error executing post-save hooks: {str(e)}")


@receiver(pre_delete, sender=Document)
def document_pre_delete(sender, instance, **kwargs):
    """
    Execute before_delete hooks

    Runs before document is deleted from database.
    Can prevent deletion by raising exception.
    """
    try:
        logger.debug(f"Executing before_delete hooks for {instance.doctype.name} #{instance.pk}")
        execute_before_delete_hooks(instance, user=getattr(instance, '_current_user', None))

    except HookExecutionError as e:
        logger.error(f"Hook execution prevented delete: {str(e)}")
        raise  # Re-raise to prevent delete


@receiver(post_delete, sender=Document)
def document_post_delete(sender, instance, **kwargs):
    """
    Execute after_delete hooks

    Runs after document is deleted from database.
    """
    try:
        logger.debug(f"Executing after_delete hooks for {instance.doctype.name} (was #{instance.pk})")
        execute_after_delete_hooks(instance, user=getattr(instance, '_current_user', None))

    except Exception as e:
        # Log error but don't fail deletion
        logger.error(f"Error executing post-delete hooks: {str(e)}")


# Helper function to attach user to document for hook execution
def set_document_user(document: Document, user):
    """
    Attach user to document instance for hook execution

    Usage:
        document = Document(...)
        set_document_user(document, request.user)
        document.save()  # Hooks will have access to user
    """
    document._current_user = user
