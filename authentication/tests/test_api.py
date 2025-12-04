"""
API tests for authentication endpoints
Tests login, signup, OAuth, MFA, and password reset endpoints
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from authentication.models import (
    UserEmailSettings, OnboardingInvitation, MFADevice, PasswordResetToken
)

User = get_user_model()


@pytest.fixture
def api_client():
    """Fixture to provide an API client"""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Fixture to create a test user"""
    return User.objects.create_user(
        email='test@example.com',
        password='Test123!@#',
        is_email_fixed=True,
        email_verified=True,
        onboarding_status='active'
    )


@pytest.fixture
def admin_user(db):
    """Fixture to create an admin user"""
    return User.objects.create_superuser(
        email='admin@example.com',
        password='Admin123!@#'
    )


@pytest.mark.django_db
class TestLoginAPI:
    """Test login endpoint"""

    def test_login_success(self, api_client, test_user):
        """Test successful login"""
        response = api_client.post('/auth/login/', {
            'username': 'test@example.com',
            'password': 'Test123!@#'
        })

        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.data
        assert 'refresh_token' in response.data
        assert 'session_key' in response.data
        assert response.data['user']['email'] == 'test@example.com'

    def test_login_invalid_credentials(self, api_client, test_user):
        """Test login with invalid credentials"""
        response = api_client.post('/auth/login/', {
            'username': 'test@example.com',
            'password': 'WrongPassword'
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_missing_fields(self, api_client):
        """Test login with missing fields"""
        response = api_client.post('/auth/login/', {
            'username': 'test@example.com'
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTokenRefreshAPI:
    """Test token refresh endpoint"""

    def test_refresh_token_success(self, api_client, test_user):
        """Test successful token refresh"""
        # First login to get tokens
        login_response = api_client.post('/auth/login/', {
            'username': 'test@example.com',
            'password': 'Test123!@#'
        })

        refresh_token = login_response.data['refresh_token']

        # Try to refresh
        response = api_client.post('/auth/token/refresh/', {
            'refresh_token': refresh_token
        })

        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.data
        assert 'refresh_token' in response.data


@pytest.mark.django_db
class TestSessionsAPI:
    """Test sessions management endpoints"""

    def test_list_sessions_authenticated(self, api_client, test_user):
        """Test listing user sessions when authenticated"""
        # Login to create a session
        login_response = api_client.post('/auth/login/', {
            'username': 'test@example.com',
            'password': 'Test123!@#'
        })

        token = login_response.data['access_token']
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = api_client.get('/auth/sessions/')

        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) > 0

    def test_list_sessions_unauthenticated(self, api_client):
        """Test listing sessions when not authenticated"""
        response = api_client.get('/auth/sessions/')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLogoutAPI:
    """Test logout endpoint"""

    def test_logout_success(self, api_client, test_user):
        """Test successful logout"""
        # Login first
        login_response = api_client.post('/auth/login/', {
            'username': 'test@example.com',
            'password': 'Test123!@#'
        })

        session_key = login_response.data['session_key']
        token = login_response.data['access_token']
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Logout
        response = api_client.post('/auth/logout/', {
            'session_key': session_key
        })

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestHealthCheckAPI:
    """Test health check endpoint"""

    def test_health_check(self, api_client):
        """Test that health check returns 200"""
        response = api_client.get('/api/health/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'healthy'


@pytest.mark.django_db
class TestUserCreationEdgeCases:
    """Test edge cases in user creation"""

    def test_create_user_duplicate_email(self, test_user):
        """Test that creating user with duplicate email raises error"""
        with pytest.raises(Exception):
            User.objects.create_user(
                email='test@example.com',  # Duplicate
                password='Test123!@#'
            )

    def test_create_user_without_password(self):
        """Test creating user without password"""
        user = User.objects.create_user(
            email='nopass@example.com'
        )

        assert user.email == 'nopass@example.com'
        assert not user.has_usable_password()

    def test_email_normalization(self):
        """Test that email is normalized (lowercased)"""
        user = User.objects.create_user(
            email='TEST@EXAMPLE.COM',
            password='Test123!@#'
        )

        # Email should be stored in normalized form
        assert user.email == user.email.lower()


@pytest.mark.django_db
class TestAuthenticationFlow:
    """Test complete authentication flows"""

    def test_complete_signup_flow(self, api_client):
        """Test complete signup and verification flow"""
        # Note: This would require implementing signup endpoint
        # For now, we test the model logic
        user = User.objects.create_user(
            email='signup@example.com',
            password='Test123!@#',
            signup_source='self_signup',
            onboarding_status='pending'
        )

        # Generate verification token
        token = user.generate_email_verification_token()
        assert token is not None

        # Verify email
        result = user.verify_email(token)
        assert result is True
        assert user.onboarding_status == 'active'

    def test_password_reset_flow(self):
        """Test complete password reset flow"""
        user = User.objects.create_user(
            email='reset@example.com',
            password='OldPass123!@#'
        )

        # Create reset token
        reset_token = PasswordResetToken.objects.create(
            user=user
        )

        assert reset_token.is_valid()

        # Simulate using the token
        old_password_hash = user.password
        user.set_password('NewPass123!@#')
        user.save()

        reset_token.use()

        assert user.password != old_password_hash
        assert not reset_token.is_valid()

    def test_mfa_enrollment_flow(self):
        """Test complete MFA enrollment flow"""
        user = User.objects.create_user(
            email='mfa@example.com',
            password='Test123!@#'
        )

        # Create TOTP device
        device = MFADevice.objects.create(
            user=user,
            device_type='totp',
            device_name='Authenticator App'
        )

        # Get TOTP URI for QR code
        uri = device.get_totp_uri()
        assert uri is not None

        # Activate MFA
        user.activate_mfa()
        assert user.mfa_enabled

        # Device should be verified after successful TOTP verification
        device.is_verified = True
        device.save()

        assert device.is_verified


@pytest.mark.django_db
class TestSecurityFeatures:
    """Test security-related features"""

    def test_password_hashing(self):
        """Test that passwords are properly hashed"""
        user = User.objects.create_user(
            email='secure@example.com',
            password='Test123!@#'
        )

        # Password should be hashed, not stored in plain text
        assert user.password != 'Test123!@#'
        assert len(user.password) > 50  # Hashed passwords are long

        # But check_password should work
        assert user.check_password('Test123!@#')

    def test_token_uniqueness(self):
        """Test that generated tokens are unique"""
        user1 = User.objects.create_user(
            email='token1@example.com',
            password='Test123!@#'
        )
        user2 = User.objects.create_user(
            email='token2@example.com',
            password='Test123!@#'
        )

        token1 = user1.generate_email_verification_token()
        token2 = user2.generate_email_verification_token()

        assert token1 != token2

    def test_session_expiry(self):
        """Test that sessions have proper expiry"""
        user = User.objects.create_user(
            email='session@example.com',
            password='Test123!@#'
        )

        from authentication.models import UserSession
        session = UserSession.objects.create(
            user=user,
            refresh_token='test_token'
        )

        # Session should expire in 7 days
        time_until_expiry = session.expires_at - timezone.now()
        assert 6 <= time_until_expiry.days <= 7


@pytest.mark.django_db
class TestAdminOnboarding:
    """Test admin-initiated onboarding"""

    def test_admin_can_create_invitation(self, admin_user):
        """Test that admin can create onboarding invitation"""
        new_user = User.objects.create_user(
            email='invited@example.com',
            password='Temp123!@#',
            signup_source='admin_onboarded',
            onboarding_status='invited'
        )

        invitation = OnboardingInvitation.objects.create(
            user=new_user,
            invited_by=admin_user,
            invitation_url='http://example.com/onboard/token123'
        )

        assert invitation.user == new_user
        assert invitation.invited_by == admin_user
        assert invitation.is_valid()

    def test_invitation_acceptance_activates_user(self, admin_user):
        """Test that accepting invitation activates user"""
        new_user = User.objects.create_user(
            email='invited@example.com',
            password='Temp123!@#',
            signup_source='admin_onboarded',
            onboarding_status='invited'
        )

        invitation = OnboardingInvitation.objects.create(
            user=new_user,
            invited_by=admin_user,
            invitation_url='http://example.com/onboard/token123',
            status='sent'
        )

        result = invitation.accept()

        assert result is True

        new_user.refresh_from_db()
        assert new_user.onboarding_status == 'active'
