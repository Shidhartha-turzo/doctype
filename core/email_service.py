"""
Email Service for Doctype Engine
Handles sending emails, document sharing, and email tracking
"""
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
from .security_models import SystemSettings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails with proper configuration and tracking"""

    @staticmethod
    def get_email_config():
        """Get email configuration from SystemSettings"""
        system_settings = SystemSettings.get_settings()

        if not system_settings.enable_email:
            raise ValueError("Email functionality is disabled in System Settings")

        return system_settings

    @staticmethod
    def configure_email_backend():
        """Configure Django email settings from SystemSettings"""
        system_settings = SystemSettings.get_settings()
        system_settings.configure_email_settings()

    @staticmethod
    def check_rate_limit(user, email_type='document_share'):
        """Check if user has exceeded email rate limit"""
        from doctypes.models import Document  # Avoid circular import

        system_settings = SystemSettings.get_settings()
        rate_limit = system_settings.email_rate_limit

        # Check emails sent in last hour
        one_hour_ago = timezone.now() - timedelta(hours=1)

        # This would need a proper EmailLog model - for now, return True
        # TODO: Implement proper email tracking
        return True

    @staticmethod
    def send_email(
        subject,
        message,
        recipient_list,
        from_email=None,
        html_message=None,
        fail_silently=False,
        attachments=None
    ):
        """
        Send email with proper configuration

        Args:
            subject: Email subject
            message: Plain text message
            recipient_list: List of recipient email addresses
            from_email: From email (uses SystemSettings if not provided)
            html_message: HTML version of message
            fail_silently: Whether to fail silently
            attachments: List of attachments (filename, content, mimetype)

        Returns:
            Number of emails sent successfully
        """
        try:
            # Configure email backend
            EmailService.configure_email_backend()
            system_settings = EmailService.get_email_config()

            # Use system from email if not provided
            if not from_email:
                from_email = f"{system_settings.email_from_name} <{system_settings.email_from_address}>"

            if html_message:
                # Send HTML email with text alternative
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=message,
                    from_email=from_email,
                    to=recipient_list
                )
                email.attach_alternative(html_message, "text/html")

                # Add attachments if provided
                if attachments:
                    for filename, content, mimetype in attachments:
                        email.attach(filename, content, mimetype)

                result = email.send(fail_silently=fail_silently)
            else:
                # Send plain text email
                result = send_mail(
                    subject=subject,
                    message=message,
                    from_email=from_email,
                    recipient_list=recipient_list,
                    fail_silently=fail_silently
                )

            logger.info(f"Email sent successfully to {recipient_list}")
            return result

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            if not fail_silently:
                raise
            return 0

    @staticmethod
    def send_document_share_email(document, recipient_email, sender, message=None, share_url=None):
        """
        Send document sharing email

        Args:
            document: Document instance to share
            recipient_email: Recipient's email address
            sender: User sharing the document
            message: Optional personal message
            share_url: URL to access the document

        Returns:
            Boolean indicating success
        """
        try:
            # Get document details
            doc_name = document.data.get('name', f"Document #{document.id}")
            doctype_name = document.doctype.name

            # Prepare email context
            context = {
                'document': document,
                'document_name': doc_name,
                'doctype_name': doctype_name,
                'sender_name': sender.get_full_name() or sender.username,
                'sender_email': sender.email,
                'recipient_email': recipient_email,
                'personal_message': message,
                'share_url': share_url or f"{settings.SITE_URL}/documents/{document.id}/",
                'site_name': 'Doctype Engine',
            }

            # Render email templates
            subject = f"{sender.get_full_name() or sender.username} shared a document with you: {doc_name}"

            # Render HTML template
            html_message = render_to_string('emails/document_share.html', context)

            # Render plain text template
            text_message = render_to_string('emails/document_share.txt', context)

            # Send email
            result = EmailService.send_email(
                subject=subject,
                message=text_message,
                recipient_list=[recipient_email],
                html_message=html_message
            )

            return result > 0

        except Exception as e:
            logger.error(f"Failed to send document share email: {str(e)}")
            return False

    @staticmethod
    def send_bulk_document_share(document, recipient_emails, sender, message=None):
        """
        Share document with multiple recipients

        Args:
            document: Document instance
            recipient_emails: List of recipient email addresses
            sender: User sharing the document
            message: Optional personal message

        Returns:
            Dict with success count and failed emails
        """
        results = {
            'success_count': 0,
            'failed_emails': [],
            'total': len(recipient_emails)
        }

        for email in recipient_emails:
            try:
                success = EmailService.send_document_share_email(
                    document=document,
                    recipient_email=email,
                    sender=sender,
                    message=message
                )
                if success:
                    results['success_count'] += 1
                else:
                    results['failed_emails'].append(email)
            except Exception as e:
                logger.error(f"Failed to send to {email}: {str(e)}")
                results['failed_emails'].append(email)

        return results

    @staticmethod
    def test_email_connection():
        """
        Test email connection and settings

        Returns:
            Dict with status and message
        """
        try:
            system_settings = EmailService.get_email_config()
            EmailService.configure_email_backend()

            # Try to send a test email
            from django.core.mail import get_connection
            connection = get_connection()
            connection.open()
            connection.close()

            return {
                'status': 'success',
                'message': 'Email connection successful',
                'config': {
                    'host': system_settings.email_host,
                    'port': system_settings.email_port,
                    'use_tls': system_settings.email_use_tls,
                    'from_email': system_settings.email_from_address
                }
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
