"""
Pytest configuration for authentication tests
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Enable database access for all tests"""
    pass


@pytest.fixture
def test_user():
    """Create a test user"""
    return User.objects.create_user(
        email='test@example.com',
        password='Test123!@#',
        is_email_fixed=True,
        email_verified=True,
        onboarding_status='active'
    )


@pytest.fixture
def admin_user():
    """Create an admin user"""
    return User.objects.create_superuser(
        email='admin@example.com',
        password='Admin123!@#'
    )
