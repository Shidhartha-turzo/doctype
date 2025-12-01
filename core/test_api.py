import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status


@pytest.fixture
def api_client():
    """Fixture to provide an API client"""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Fixture to create a test user"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )


@pytest.mark.django_db
class TestHealthCheck:
    """Tests for the health check endpoint"""

    def test_health_check(self, api_client):
        """Test that health check returns 200"""
        response = api_client.get('/api/health/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'healthy'


@pytest.mark.django_db
class TestUserAPI:
    """Tests for the User API endpoints"""

    def test_user_list_requires_authentication(self, api_client):
        """Test that user list requires authentication"""
        response = api_client.get('/api/users/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_list_authenticated(self, api_client, test_user):
        """Test that authenticated users can view user list"""
        api_client.force_authenticate(user=test_user)
        response = api_client.get('/api/users/')
        assert response.status_code == status.HTTP_200_OK

    def test_user_detail_authenticated(self, api_client, test_user):
        """Test that authenticated users can view user details"""
        api_client.force_authenticate(user=test_user)
        response = api_client.get(f'/api/users/{test_user.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['username'] == 'testuser'


@pytest.mark.django_db
class TestJWTAuthentication:
    """Tests for JWT authentication"""

    def test_obtain_token(self, api_client, test_user):
        """Test obtaining JWT token"""
        response = api_client.post('/api/token/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_obtain_token_invalid_credentials(self, api_client):
        """Test obtaining token with invalid credentials"""
        response = api_client.post('/api/token/', {
            'username': 'wronguser',
            'password': 'wrongpass'
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
