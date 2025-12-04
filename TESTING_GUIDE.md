# Doctype Engine - Testing Guide

**Purpose**: Enable all developers to easily write and run tests
**Status**: Comprehensive testing framework ready
**Last Updated**: 2025-12-03

---

## Quick Start

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest authentication/tests/test_models.py
```

### Run Specific Test Class
```bash
pytest authentication/tests/test_models.py::TestUserModel
```

### Run Specific Test
```bash
pytest authentication/tests/test_models.py::TestUserModel::test_create_user_with_email
```

### Run with Verbose Output
```bash
pytest -v
```

### Run with Coverage Report
```bash
pytest --cov=. --cov-report=html
```

---

## Test Structure

### Directory Organization
```
doctype/
├── authentication/
│   └── tests/
│       ├── __init__.py
│       ├── test_models.py       # Model unit tests
│       └── test_api.py          # API endpoint tests
├── core/
│   └── test_api.py              # Core API tests
├── doctypes/
│   └── tests/                   # Doctype tests (create as needed)
└── pytest.ini                   # pytest configuration
```

---

## Writing Tests

### Test File Naming
- Files: `test_*.py` or `*_test.py`
- Classes: `Test*`
- Functions: `test_*`

### Example: Model Test
```python
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
class TestUserModel:
    """Test User model functionality"""

    def test_create_user(self):
        """Test creating a user"""
        user = User.objects.create_user(
            email='test@example.com',
            password='Test123!@#'
        )

        assert user.email == 'test@example.com'
        assert user.check_password('Test123!@#')
        assert user.is_active
```

### Example: API Test
```python
import pytest
from rest_framework.test import APIClient
from rest_framework import status

@pytest.fixture
def api_client():
    return APIClient()

@pytest.mark.django_db
class TestLoginAPI:
    """Test login endpoint"""

    def test_login_success(self, api_client):
        """Test successful login"""
        # Create test user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_user(
            email='test@example.com',
            password='Test123!@#'
        )

        # Test login
        response = api_client.post('/auth/login/', {
            'username': 'test@example.com',
            'password': 'Test123!@#'
        })

        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.data
```

---

## Fixtures

### Common Fixtures Available

#### api_client
```python
def test_my_api(api_client):
    """api_client is available as fixture"""
    response = api_client.get('/api/endpoint/')
    assert response.status_code == 200
```

#### test_user
```python
def test_with_user(test_user):
    """test_user fixture provides authenticated user"""
    assert test_user.email == 'test@example.com'
```

#### admin_user
```python
def test_with_admin(admin_user):
    """admin_user fixture provides superuser"""
    assert admin_user.is_superuser
```

### Creating Custom Fixtures

```python
# In conftest.py or test file
import pytest

@pytest.fixture
def sample_document(db):
    """Create a sample document"""
    from doctypes.models import Doctype, Document

    doctype = Doctype.objects.create(
        name='TestDoc',
        slug='testdoc'
    )

    document = Document.objects.create(
        doctype=doctype,
        title='Test Document'
    )

    return document
```

---

## Test Categories

### 1. Model Tests
Test model creation, validation, and methods

```python
@pytest.mark.django_db
class TestMyModel:
    def test_create(self):
        """Test model creation"""
        pass

    def test_validation(self):
        """Test model validation"""
        pass

    def test_methods(self):
        """Test model methods"""
        pass
```

### 2. API Tests
Test API endpoints, authentication, and responses

```python
@pytest.mark.django_db
class TestMyAPI:
    def test_get(self, api_client):
        """Test GET endpoint"""
        response = api_client.get('/api/endpoint/')
        assert response.status_code == 200

    def test_post(self, api_client):
        """Test POST endpoint"""
        response = api_client.post('/api/endpoint/', {
            'field': 'value'
        })
        assert response.status_code == 201

    def test_authentication_required(self, api_client):
        """Test that endpoint requires authentication"""
        response = api_client.get('/api/protected/')
        assert response.status_code == 401
```

### 3. Integration Tests
Test multiple components working together

```python
@pytest.mark.django_db
class TestCompleteFlow:
    def test_signup_to_login(self, api_client):
        """Test complete signup and login flow"""
        # Create user
        user = User.objects.create_user(
            email='flow@example.com',
            password='Test123!@#'
        )

        # Login
        response = api_client.post('/auth/login/', {
            'username': 'flow@example.com',
            'password': 'Test123!@#'
        })

        assert response.status_code == 200
        assert 'access_token' in response.data
```

### 4. Security Tests
Test authentication, authorization, and security features

```python
@pytest.mark.django_db
class TestSecurity:
    def test_password_hashing(self):
        """Test passwords are hashed"""
        user = User.objects.create_user(
            email='secure@example.com',
            password='Test123!@#'
        )

        assert user.password != 'Test123!@#'
        assert user.check_password('Test123!@#')

    def test_unauthorized_access(self, api_client):
        """Test unauthorized users can't access protected endpoints"""
        response = api_client.get('/api/protected/')
        assert response.status_code == 401
```

---

## Pytest Markers

### Database Access
```python
@pytest.mark.django_db
def test_needs_database():
    """This test needs database access"""
    pass
```

### Skip Tests
```python
@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass
```

### Expected Failure
```python
@pytest.mark.xfail
def test_known_bug():
    """This test is expected to fail"""
    pass
```

### Parameterized Tests
```python
@pytest.mark.parametrize('email,expected', [
    ('test@example.com', True),
    ('invalid@', False),
    ('no-at-sign.com', False),
])
def test_email_validation(email, expected):
    """Test email validation with multiple inputs"""
    result = validate_email(email)
    assert result == expected
```

---

## Best Practices

### 1. Test Naming
```python
# Good
def test_user_creation_with_valid_email():
    """Test that user can be created with valid email"""
    pass

# Bad
def test1():
    pass
```

### 2. One Assert Per Test (when possible)
```python
# Good
def test_user_email(user):
    assert user.email == 'test@example.com'

def test_user_is_active(user):
    assert user.is_active

# Acceptable when testing related state
def test_user_creation():
    user = User.objects.create_user(email='test@example.com')
    assert user.email == 'test@example.com'
    assert user.is_active
```

### 3. Use Fixtures for Setup
```python
# Good
@pytest.fixture
def user():
    return User.objects.create_user(email='test@example.com')

def test_user_email(user):
    assert user.email == 'test@example.com'

# Bad
def test_user_email():
    user = User.objects.create_user(email='test@example.com')
    assert user.email == 'test@example.com'
```

### 4. Test Both Success and Failure Cases
```python
def test_login_success(api_client, test_user):
    """Test successful login"""
    response = api_client.post('/auth/login/', {
        'username': 'test@example.com',
        'password': 'Test123!@#'
    })
    assert response.status_code == 200

def test_login_invalid_password(api_client, test_user):
    """Test login with invalid password"""
    response = api_client.post('/auth/login/', {
        'username': 'test@example.com',
        'password': 'WrongPassword'
    })
    assert response.status_code == 400
```

### 5. Clear Test Documentation
```python
def test_email_verification():
    """
    Test email verification flow:
    1. Create user with unverified email
    2. Generate verification token
    3. Verify email with token
    4. Check user status updated
    """
    pass
```

---

## Running Tests in CI/CD

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.14

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-django pytest-cov

    - name: Run tests
      run: pytest --cov=. --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## Test Coverage

### Generate Coverage Report
```bash
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

### Coverage by App
```bash
pytest --cov=authentication --cov-report=term
pytest --cov=core --cov-report=term
pytest --cov=doctypes --cov-report=term
```

### Minimum Coverage Requirement
```bash
pytest --cov=. --cov-fail-under=80
```

---

## Debugging Tests

### Run with Print Statements
```bash
pytest -s
```

### Run with Debugger
```python
def test_something():
    import pdb; pdb.set_trace()
    # Test code here
```

### Show Local Variables on Failure
```bash
pytest -l
```

### Stop on First Failure
```bash
pytest -x
```

### Show Full Diff on Assertion Failure
```bash
pytest -vv
```

---

## Common Test Patterns

### Testing Exceptions
```python
def test_invalid_email_raises_error():
    """Test that invalid email raises ValidationError"""
    with pytest.raises(ValidationError):
        User.objects.create_user(email='invalid-email')
```

### Testing Authentication Required
```python
def test_requires_authentication(api_client):
    """Test endpoint requires authentication"""
    response = api_client.get('/api/protected/')
    assert response.status_code == 401

    # Login and retry
    user = User.objects.create_user(email='auth@example.com', password='pass')
    api_client.force_authenticate(user=user)

    response = api_client.get('/api/protected/')
    assert response.status_code == 200
```

### Testing Permissions
```python
def test_admin_only_endpoint(api_client, test_user, admin_user):
    """Test endpoint is admin-only"""
    # Regular user denied
    api_client.force_authenticate(user=test_user)
    response = api_client.get('/api/admin-only/')
    assert response.status_code == 403

    # Admin allowed
    api_client.force_authenticate(user=admin_user)
    response = api_client.get('/api/admin-only/')
    assert response.status_code == 200
```

### Testing Time-Dependent Code
```python
from django.utils import timezone
from datetime import timedelta

def test_token_expiry():
    """Test that token expires after 24 hours"""
    user = User.objects.create_user(email='test@example.com')
    token = PasswordResetToken.objects.create(
        user=user,
        expires_at=timezone.now() - timedelta(hours=25)
    )

    assert not token.is_valid()
```

---

## Test Data Management

### Using Factory Pattern
```python
@pytest.fixture
def user_factory():
    """Factory for creating test users"""
    def create_user(email=None, **kwargs):
        if email is None:
            email = f'user{User.objects.count()}@example.com'
        return User.objects.create_user(email=email, **kwargs)
    return create_user

def test_with_factory(user_factory):
    """Test using user factory"""
    user1 = user_factory()
    user2 = user_factory()

    assert user1.email != user2.email
```

### Test Database Cleanup
pytest-django automatically handles database cleanup between tests

---

## Performance Testing

### Measure Test Execution Time
```bash
pytest --durations=10  # Show 10 slowest tests
```

### Optimize Slow Tests
```python
# Use setUpTestData for class-level fixtures
@pytest.mark.django_db
class TestBulkOperations:
    @classmethod
    def setup_class(cls):
        """Run once for entire test class"""
        cls.users = [
            User.objects.create_user(f'user{i}@example.com')
            for i in range(100)
        ]
```

---

## Resources

### Documentation
- pytest: https://docs.pytest.org/
- pytest-django: https://pytest-django.readthedocs.io/
- Django Testing: https://docs.djangoproject.com/en/stable/topics/testing/
- DRF Testing: https://www.django-rest-framework.org/api-guide/testing/

### Current Test Coverage
```
authentication/tests/test_models.py  - 50+ tests for all auth models
authentication/tests/test_api.py     - 30+ tests for API endpoints
core/test_api.py                     - Basic API tests
```

---

## Quick Reference

### Essential Commands
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific app
pytest authentication/

# Run verbose
pytest -v

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Rerun failed tests
pytest --lf

# Run in parallel (requires pytest-xdist)
pytest -n auto
```

### Common Assertions
```python
assert value == expected
assert value != other
assert value is True
assert value is not None
assert len(list) == 5
assert 'key' in dictionary
assert value > 10
assert isinstance(obj, MyClass)
```

---

## Contributing Tests

### Before Submitting PR
1. Write tests for new features
2. Update existing tests if behavior changes
3. Ensure all tests pass: `pytest`
4. Check coverage: `pytest --cov=.`
5. Run linting: `flake8` (if configured)

### Test Checklist
- [ ] Tests pass locally
- [ ] Tests cover new functionality
- [ ] Tests include edge cases
- [ ] Tests have clear names and docstrings
- [ ] No commented-out test code
- [ ] Database fixtures cleaned up properly
- [ ] Authentication properly mocked

---

**Status**: Testing framework fully operational
**Coverage**: 80+ tests across authentication system
**Next**: Add tests for doctypes and core modules

---

Generated: 2025-12-03
Framework: pytest + pytest-django
