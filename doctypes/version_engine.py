"""
Document Version Management Engine

Handles automatic versioning, diff calculation, and version restoration.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from difflib import unified_diff

from .engine_models import DocumentVersion
from .models import Document

logger = logging.getLogger(__name__)


class VersionEngine:
    """
    Version management engine for documents
    """

    def __init__(self, document: Document):
        """
        Initialize version engine for a document

        Args:
            document: Document instance
        """
        self.document = document

    def create_version(self, user=None, comment: str = '') -> DocumentVersion:
        """
        Create a new version of the document

        Args:
            user: User creating the version
            comment: Optional comment describing the change

        Returns:
            DocumentVersion instance
        """
        # Get current version number
        latest_version = DocumentVersion.objects.filter(
            document=self.document
        ).order_by('-version_number').first()

        new_version_number = (latest_version.version_number + 1) if latest_version else 1

        # Calculate changes from previous version
        changes = self._calculate_changes(
            latest_version.data_snapshot if latest_version else {},
            self.document.data
        )

        # Create version
        version = DocumentVersion.objects.create(
            document=self.document,
            version_number=new_version_number,
            data_snapshot=self.document.data.copy(),
            changes=changes,
            changed_by=user,
            comment=comment
        )

        # Update document version number
        self.document.version_number = new_version_number
        self.document.save(update_fields=['version_number'])

        logger.info(
            f"Created version {new_version_number} for document {self.document.id}"
        )

        return version

    def get_versions(self, limit: Optional[int] = None) -> List[DocumentVersion]:
        """
        Get all versions of the document

        Args:
            limit: Optional limit on number of versions

        Returns:
            List of DocumentVersion instances
        """
        queryset = DocumentVersion.objects.filter(
            document=self.document
        ).order_by('-version_number')

        if limit:
            queryset = queryset[:limit]

        return list(queryset)

    def get_version(self, version_number: int) -> Optional[DocumentVersion]:
        """
        Get a specific version

        Args:
            version_number: Version number to retrieve

        Returns:
            DocumentVersion instance or None
        """
        try:
            return DocumentVersion.objects.get(
                document=self.document,
                version_number=version_number
            )
        except DocumentVersion.DoesNotExist:
            return None

    def compare_versions(
        self,
        version1_number: int,
        version2_number: int
    ) -> Dict[str, Any]:
        """
        Compare two versions and return differences

        Args:
            version1_number: First version number
            version2_number: Second version number

        Returns:
            Dict with comparison results
        """
        version1 = self.get_version(version1_number)
        version2 = self.get_version(version2_number)

        if not version1 or not version2:
            raise ValueError("One or both versions not found")

        diff = self._calculate_changes(
            version1.data_snapshot,
            version2.data_snapshot
        )

        return {
            'version1': {
                'number': version1.version_number,
                'changed_by': version1.changed_by.email if version1.changed_by else None,
                'changed_at': version1.changed_at.isoformat(),
                'comment': version1.comment
            },
            'version2': {
                'number': version2.version_number,
                'changed_by': version2.changed_by.email if version2.changed_by else None,
                'changed_at': version2.changed_at.isoformat(),
                'comment': version2.comment
            },
            'diff': diff,
            'has_changes': bool(diff['added'] or diff['modified'] or diff['removed'])
        }

    @transaction.atomic
    def restore_version(
        self,
        version_number: int,
        user=None,
        comment: str = ''
    ) -> DocumentVersion:
        """
        Restore document to a specific version

        Creates a new version with the restored data.

        Args:
            version_number: Version to restore to
            user: User performing the restoration
            comment: Optional comment

        Returns:
            New DocumentVersion instance
        """
        version_to_restore = self.get_version(version_number)

        if not version_to_restore:
            raise ValueError(f"Version {version_number} not found")

        # Update document data to restored version
        self.document.data = version_to_restore.data_snapshot.copy()
        self.document.modified_by = user
        self.document.save()

        # Create new version for the restoration
        restore_comment = comment or f"Restored to version {version_number}"
        new_version = self.create_version(user=user, comment=restore_comment)

        logger.info(
            f"Restored document {self.document.id} to version {version_number}, "
            f"created version {new_version.version_number}"
        )

        return new_version

    def get_diff_text(
        self,
        version1_number: int,
        version2_number: int,
        field_name: Optional[str] = None
    ) -> str:
        """
        Get unified diff text between two versions

        Args:
            version1_number: First version number
            version2_number: Second version number
            field_name: Optional specific field to diff

        Returns:
            Unified diff text
        """
        version1 = self.get_version(version1_number)
        version2 = self.get_version(version2_number)

        if not version1 or not version2:
            return "Version not found"

        # Get data to compare
        data1 = version1.data_snapshot
        data2 = version2.data_snapshot

        if field_name:
            # Compare specific field
            value1 = json.dumps(data1.get(field_name), indent=2, default=str)
            value2 = json.dumps(data2.get(field_name), indent=2, default=str)
            label1 = f"v{version1_number}/{field_name}"
            label2 = f"v{version2_number}/{field_name}"
        else:
            # Compare entire document
            value1 = json.dumps(data1, indent=2, sort_keys=True, default=str)
            value2 = json.dumps(data2, indent=2, sort_keys=True, default=str)
            label1 = f"Version {version1_number}"
            label2 = f"Version {version2_number}"

        # Generate unified diff
        diff = unified_diff(
            value1.splitlines(keepends=True),
            value2.splitlines(keepends=True),
            fromfile=label1,
            tofile=label2,
            lineterm=''
        )

        return ''.join(diff)

    def _calculate_changes(
        self,
        old_data: Dict,
        new_data: Dict
    ) -> Dict[str, Any]:
        """
        Calculate changes between two data dictionaries

        Returns:
            Dict with added, modified, and removed fields
        """
        changes = {
            'added': {},
            'modified': {},
            'removed': {}
        }

        # Find added and modified fields
        for key, new_value in new_data.items():
            if key not in old_data:
                changes['added'][key] = new_value
            elif old_data[key] != new_value:
                changes['modified'][key] = {
                    'old': old_data[key],
                    'new': new_value
                }

        # Find removed fields
        for key, old_value in old_data.items():
            if key not in new_data:
                changes['removed'][key] = old_value

        return changes

    def get_version_history(self) -> List[Dict]:
        """
        Get formatted version history

        Returns:
            List of version info dictionaries
        """
        versions = self.get_versions()
        history = []

        for version in versions:
            history.append({
                'version_number': version.version_number,
                'changed_by': version.changed_by.email if version.changed_by else 'System',
                'changed_at': version.changed_at.isoformat(),
                'comment': version.comment,
                'changes_summary': self._format_changes_summary(version.changes),
                'is_current': version.version_number == self.document.version_number
            })

        return history

    def _format_changes_summary(self, changes: Dict) -> str:
        """Format changes into human-readable summary"""
        parts = []

        if changes.get('added'):
            count = len(changes['added'])
            parts.append(f"{count} field{'s' if count != 1 else ''} added")

        if changes.get('modified'):
            count = len(changes['modified'])
            parts.append(f"{count} field{'s' if count != 1 else ''} modified")

        if changes.get('removed'):
            count = len(changes['removed'])
            parts.append(f"{count} field{'s' if count != 1 else ''} removed")

        return ', '.join(parts) if parts else 'No changes'


# Convenience functions

def create_version(document: Document, user=None, comment: str = '') -> DocumentVersion:
    """
    Create a version for a document

    Usage:
        from doctypes.version_engine import create_version
        create_version(document, user=request.user, comment="Updated pricing")
    """
    engine = VersionEngine(document)
    return engine.create_version(user, comment)


def get_versions(document: Document, limit: Optional[int] = None) -> List[DocumentVersion]:
    """Get all versions of a document"""
    engine = VersionEngine(document)
    return engine.get_versions(limit)


def restore_version(
    document: Document,
    version_number: int,
    user=None,
    comment: str = ''
) -> DocumentVersion:
    """Restore document to a specific version"""
    engine = VersionEngine(document)
    return engine.restore_version(version_number, user, comment)


def compare_versions(
    document: Document,
    version1_number: int,
    version2_number: int
) -> Dict:
    """Compare two versions of a document"""
    engine = VersionEngine(document)
    return engine.compare_versions(version1_number, version2_number)
