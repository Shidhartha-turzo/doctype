"""
Unit tests for authentication models
Tests User model, UserEmailSettings, OAuth, MFA, and related models
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from authentication.models import (
    UserEmailSettings, OnboardingInvitation, OAuthProvider,
    MFADevice, PasswordResetToken, MagicLink, UserSession
)

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Test custom User model with email as primary key"""

    def test_create_user_with_email(self):
        """Test creating a user with email as primary key"""
        user = User.objects.create_user(
            email='test@example.com',
            password='Test123!@#'
        )
        assert user.email == 'test@example.com'
        assert user.check_password('Test123!@#')
        assert user.is_active
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_superuser(self):
        """Test creating a superuser"""
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='Admin123!@#'
        )
        assert user.email == 'admin@example.com'
        assert user.is_staff
        assert user.is_superuser
        assert user.is_email_fixed
        assert user.email_verified
        assert user.onboarding_status == 'active'

    def test_username_auto_generated(self):
        """Test that username is auto-generated from email"""
        user = User.objects.create_user(
            email='john.doe@example.com',
            password='Test123!@#'
        )
        assert user.username == 'john.doe'

    def test_duplicate_username_handling(self):
        """Test that duplicate usernames are handled with counter"""
        user1 = User.objects.create_user(
            email='john@example.com',
            password='Test123!@#'
        )
        user2 = User.objects.create_user(
            email='john@another.com',
            password='Test123!@#'
        )
        assert user1.username == 'john'
        assert user2.username == 'john1'

    def test_email_verification_token_generation(self):
        """Test email verification token generation"""
        user = User.objects.create_user(
            email='verify@example.com',
            password='Test123!@#'
        )
        token = user.generate_email_verification_token()
        assert token is not None
        assert len(token) > 0
        assert user.email_verification_token == token
        assert user.email_verification_sent_at is not None

    def test_email_verification_success(self):
        """Test successful email verification"""
        user = User.objects.create_user(
            email='verify@example.com',
            password='Test123!@#',
            onboarding_status='pending'
        )
        token = user.generate_email_verification_token()

        result = user.verify_email(token)

        assert result is True
        assert user.email_verified
        assert user.is_email_fixed
        assert user.onboarding_status == 'active'
        assert user.email_verification_token is None

    def test_email_verification_invalid_token(self):
        """Test email verification with invalid token"""
        user = User.objects.create_user(
            email='verify@example.com',
            password='Test123!@#'
        )
        user.generate_email_verification_token()

        result = user.verify_email('wrong_token')

        assert result is False
        assert not user.email_verified

    def test_email_verification_expired_token(self):
        """Test email verification with expired token"""
        user = User.objects.create_user(
            email='verify@example.com',
            password='Test123!@#'
        )
        token = user.generate_email_verification_token()

        # Set sent time to 4 days ago (beyond 72 hour expiry)
        user.email_verification_sent_at = timezone.now() - timedelta(days=4)
        user.save()

        result = user.verify_email(token)

        assert result is False
        assert not user.email_verified

    def test_can_receive_emails(self):
        """Test email sending permission logic"""
        user = User.objects.create_user(
            email='notify@example.com',
            password='Test123!@#',
            is_email_fixed=True,
            is_active=True
        )

        # Create email settings
        settings = UserEmailSettings.objects.create(
            user=user,
            notifications_enabled=True,
            email_bounce_status='none'
        )

        assert user.can_receive_emails()

    def test_mfa_activation(self):
        """Test MFA activation and deactivation"""
        user = User.objects.create_user(
            email='mfa@example.com',
            password='Test123!@#'
        )

        assert not user.mfa_enabled

        user.activate_mfa()
        assert user.mfa_enabled

        user.deactivate_mfa()
        assert not user.mfa_enabled


@pytest.mark.django_db
class TestUserEmailSettings:
    """Test UserEmailSettings model"""

    def test_create_email_settings(self):
        """Test creating email settings for a user"""
        user = User.objects.create_user(
            email='settings@example.com',
            password='Test123!@#'
        )

        settings = UserEmailSettings.objects.create(
            user=user,
            notifications_enabled=True,
            marketing_opt_in=False
        )

        assert settings.user == user
        assert settings.notifications_enabled
        assert not settings.marketing_opt_in
        assert settings.email_bounce_status == 'none'

    def test_record_email_sent(self):
        """Test recording email sent"""
        user = User.objects.create_user(
            email='track@example.com',
            password='Test123!@#'
        )
        settings = UserEmailSettings.objects.create(user=user)

        initial_count = settings.emails_sent_today
        settings.record_email_sent()

        assert settings.emails_sent_today == initial_count + 1
        assert settings.last_email_sent_at is not None

    def test_can_send_email_within_limit(self):
        """Test email sending limit check"""
        user = User.objects.create_user(
            email='limit@example.com',
            password='Test123!@#'
        )
        settings = UserEmailSettings.objects.create(
            user=user,
            daily_email_limit=10
        )

        for i in range(5):
            settings.record_email_sent()

        assert settings.can_send_email()

    def test_can_send_email_exceeds_limit(self):
        """Test email sending when limit exceeded"""
        user = User.objects.create_user(
            email='overlimit@example.com',
            password='Test123!@#'
        )
        settings = UserEmailSettings.objects.create(
            user=user,
            daily_email_limit=3,
            emails_sent_today=3,
            last_email_reset=timezone.now().date()
        )

        assert not settings.can_send_email()

    def test_record_bounce(self):
        """Test recording email bounce"""
        user = User.objects.create_user(
            email='bounce@example.com',
            password='Test123!@#'
        )
        settings = UserEmailSettings.objects.create(user=user)

        settings.record_bounce('soft_bounce')

        assert settings.bounce_count == 1
        assert settings.email_bounce_status == 'soft_bounce'
        assert settings.last_bounce_at is not None

    def test_hard_bounce_sets_status(self):
        """Test that hard bounce sets status immediately"""
        user = User.objects.create_user(
            email='hardbounce@example.com',
            password='Test123!@#'
        )
        settings = UserEmailSettings.objects.create(user=user)

        settings.record_bounce('hard_bounce')

        assert settings.email_bounce_status == 'hard_bounce'

    def test_multiple_soft_bounces_become_hard(self):
        """Test that 5 soft bounces become hard bounce"""
        user = User.objects.create_user(
            email='softbounce@example.com',
            password='Test123!@#'
        )
        settings = UserEmailSettings.objects.create(user=user)

        for i in range(5):
            settings.record_bounce('soft_bounce')

        assert settings.email_bounce_status == 'hard_bounce'
        assert settings.bounce_count == 5


@pytest.mark.django_db
class TestOnboardingInvitation:
    """Test OnboardingInvitation model"""

    def test_create_invitation(self):
        """Test creating an onboarding invitation"""
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='Admin123!@#'
        )
        user = User.objects.create_user(
            email='invited@example.com',
            password='Temp123!@#',
            signup_source='admin_onboarded',
            onboarding_status='invited'
        )

        invitation = OnboardingInvitation.objects.create(
            user=user,
            invited_by=admin,
            invitation_url='http://example.com/onboard/abc123'
        )

        assert invitation.user == user
        assert invitation.invited_by == admin
        assert invitation.status == 'pending'
        assert invitation.invitation_token is not None
        assert invitation.expires_at is not None

    def test_invitation_auto_generates_token(self):
        """Test that invitation auto-generates token"""
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='Admin123!@#'
        )
        user = User.objects.create_user(
            email='invited@example.com',
            password='Temp123!@#'
        )

        invitation = OnboardingInvitation.objects.create(
            user=user,
            invited_by=admin,
            invitation_url='http://example.com/onboard'
        )

        assert len(invitation.invitation_token) > 0

    def test_invitation_is_valid(self):
        """Test invitation validity check"""
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='Admin123!@#'
        )
        user = User.objects.create_user(
            email='invited@example.com',
            password='Temp123!@#'
        )

        invitation = OnboardingInvitation.objects.create(
            user=user,
            invited_by=admin,
            invitation_url='http://example.com/onboard',
            status='sent'
        )

        assert invitation.is_valid()

    def test_expired_invitation_not_valid(self):
        """Test that expired invitation is not valid"""
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='Admin123!@#'
        )
        user = User.objects.create_user(
            email='invited@example.com',
            password='Temp123!@#'
        )

        invitation = OnboardingInvitation.objects.create(
            user=user,
            invited_by=admin,
            invitation_url='http://example.com/onboard',
            expires_at=timezone.now() - timedelta(days=1)
        )

        assert not invitation.is_valid()

    def test_accept_invitation(self):
        """Test accepting an invitation"""
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='Admin123!@#'
        )
        user = User.objects.create_user(
            email='invited@example.com',
            password='Temp123!@#',
            onboarding_status='invited'
        )

        invitation = OnboardingInvitation.objects.create(
            user=user,
            invited_by=admin,
            invitation_url='http://example.com/onboard',
            status='sent'
        )

        result = invitation.accept()

        assert result is True
        assert invitation.status == 'accepted'
        assert invitation.accepted_at is not None

        user.refresh_from_db()
        assert user.onboarding_status == 'active'
        assert user.onboarding_completed_at is not None


@pytest.mark.django_db
class TestMFADevice:
    """Test MFADevice model"""

    def test_create_totp_device(self):
        """Test creating a TOTP MFA device"""
        user = User.objects.create_user(
            email='mfa@example.com',
            password='Test123!@#'
        )

        device = MFADevice.objects.create(
            user=user,
            device_type='totp',
            device_name='Authenticator App'
        )

        assert device.device_type == 'totp'
        assert device.totp_secret is not None
        assert len(device.totp_secret) > 0

    def test_get_totp_uri(self):
        """Test TOTP URI generation for QR code"""
        user = User.objects.create_user(
            email='mfa@example.com',
            password='Test123!@#'
        )

        device = MFADevice.objects.create(
            user=user,
            device_type='totp',
            device_name='Authenticator App'
        )

        uri = device.get_totp_uri()

        assert uri is not None
        assert 'otpauth://totp/' in uri
        assert 'mfa' in uri.lower()  # URL encoded version
        assert 'Doctype' in uri

    def test_generate_backup_codes(self):
        """Test backup code generation"""
        user = User.objects.create_user(
            email='backupgen@example.com',
            password='Test123!@#'
        )

        device = MFADevice.objects.create(
            user=user,
            device_type='backup_codes',
            device_name='Backup Codes'
        )

        assert len(device.backup_codes) == 10
        for code in device.backup_codes:
            assert len(code) == 8

    def test_use_backup_code_success(self):
        """Test using a valid backup code"""
        user = User.objects.create_user(
            email='backupuse@example.com',
            password='Test123!@#'
        )

        device = MFADevice.objects.create(
            user=user,
            device_type='backup_codes',
            device_name='Backup Codes'
        )

        code_to_use = device.backup_codes[0]
        result = device.use_backup_code(code_to_use)

        assert result is True
        assert code_to_use not in device.backup_codes
        assert device.use_count == 1

    def test_use_backup_code_invalid(self):
        """Test using an invalid backup code"""
        user = User.objects.create_user(
            email='backupinvalid@example.com',
            password='Test123!@#'
        )

        device = MFADevice.objects.create(
            user=user,
            device_type='backup_codes',
            device_name='Backup Codes'
        )

        result = device.use_backup_code('INVALID')

        assert result is False
        assert device.use_count == 0


@pytest.mark.django_db
class TestPasswordResetToken:
    """Test PasswordResetToken model"""

    def test_create_reset_token(self):
        """Test creating a password reset token"""
        user = User.objects.create_user(
            email='reset@example.com',
            password='Test123!@#'
        )

        token = PasswordResetToken.objects.create(
            user=user,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )

        assert token.user == user
        assert token.token is not None
        assert len(token.token) > 0
        assert token.expires_at is not None
        assert not token.is_used

    def test_token_is_valid(self):
        """Test that new token is valid"""
        user = User.objects.create_user(
            email='reset@example.com',
            password='Test123!@#'
        )

        token = PasswordResetToken.objects.create(user=user)

        assert token.is_valid()

    def test_used_token_not_valid(self):
        """Test that used token is not valid"""
        user = User.objects.create_user(
            email='reset@example.com',
            password='Test123!@#'
        )

        token = PasswordResetToken.objects.create(user=user)
        token.use()

        assert not token.is_valid()
        assert token.is_used
        assert token.used_at is not None

    def test_expired_token_not_valid(self):
        """Test that expired token is not valid"""
        user = User.objects.create_user(
            email='reset@example.com',
            password='Test123!@#'
        )

        token = PasswordResetToken.objects.create(
            user=user,
            expires_at=timezone.now() - timedelta(hours=1)
        )

        assert not token.is_valid()


@pytest.mark.django_db
class TestMagicLink:
    """Test MagicLink model"""

    def test_create_magic_link(self):
        """Test creating a magic link"""
        link = MagicLink.objects.create(
            email='magic@example.com'
        )

        assert link.email == 'magic@example.com'
        assert link.token is not None
        assert link.expires_at is not None
        assert link.is_active

    def test_magic_link_is_valid(self):
        """Test that new magic link is valid"""
        link = MagicLink.objects.create(email='magic@example.com')

        assert link.is_valid()

    def test_used_magic_link_not_valid(self):
        """Test that used magic link is not valid"""
        link = MagicLink.objects.create(email='magic@example.com')
        link.mark_as_used()

        assert not link.is_valid()
        assert not link.is_active
        assert link.used_at is not None


@pytest.mark.django_db
class TestUserSession:
    """Test UserSession model"""

    def test_create_session(self):
        """Test creating a user session"""
        user = User.objects.create_user(
            email='session@example.com',
            password='Test123!@#'
        )

        session = UserSession.objects.create(
            user=user,
            refresh_token='abc123',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0'
        )

        assert session.user == user
        assert session.session_key is not None
        assert session.expires_at is not None
        assert session.is_active

    def test_session_is_valid(self):
        """Test that new session is valid"""
        user = User.objects.create_user(
            email='session@example.com',
            password='Test123!@#'
        )

        session = UserSession.objects.create(
            user=user,
            refresh_token='abc123'
        )

        assert session.is_valid()

    def test_deactivated_session_not_valid(self):
        """Test that deactivated session is not valid"""
        user = User.objects.create_user(
            email='session@example.com',
            password='Test123!@#'
        )

        session = UserSession.objects.create(
            user=user,
            refresh_token='abc123'
        )
        session.deactivate()

        assert not session.is_valid()
        assert not session.is_active
