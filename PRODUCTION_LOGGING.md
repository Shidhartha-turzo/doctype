# Production Logging & Change Management

## Overview

This document describes the comprehensive logging and change management system designed for production environments. The system tracks user login history with IP addresses, device information, and maintains a detailed changelog for all major system changes.

## Features

### 1. User Login History Tracking
- Tracks all login attempts (successful and failed)
- Records IP addresses, user agents, device types
- Supports multiple login methods (password, magic link, API key, JWT, SSO)
- Session duration tracking
- Geographic information (optional)
- Complete audit trail of user access

### 2. Change Log System
- Tracks major system changes for production
- Impact assessment and rollback capabilities
- Approval workflow support
- Git integration (commit hash, branch tracking)
- Jira/ticket integration
- Testing and validation tracking

### 3. Security Compliance
- Essential for SOC 2, ISO 27001, GDPR compliance
- Complete audit trail for security incidents
- IP-based access monitoring
- Failed login tracking for security analysis
- Automated security logging

## Database Tables

### UserLoginHistory

**Purpose**: Track all user login attempts with comprehensive details

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| user | ForeignKey | User who logged in |
| username | CharField | Username (denormalized for speed) |
| login_type | CharField | Method used (password, magic_link, api_key, etc.) |
| success | Boolean | Whether login was successful |
| failure_reason | CharField | Reason for failed login |
| ip_address | GenericIPAddressField | IP address of login attempt |
| user_agent | TextField | Browser user agent string |
| device_type | CharField | desktop, mobile, tablet, bot, unknown |
| country | CharField | Country code (ISO 3166-1 alpha-2) |
| city | CharField | City name |
| session_key | CharField | Django session key |
| login_at | DateTimeField | Timestamp of login |
| logout_at | DateTimeField | Timestamp of logout |
| session_duration | DurationField | Duration of session |
| metadata | JSONField | Additional metadata (referrer, browser, OS) |

**Indexes**:
- `user, login_at` (composite)
- `ip_address, login_at` (composite)
- `username, login_at` (composite)
- `success, login_at` (composite)

**Example Queries**:

```python
from core.security_models import UserLoginHistory

# Get user's last successful login
last_login = UserLoginHistory.get_user_last_login(user)
print(f"Last login from {last_login.ip_address} at {last_login.login_at}")

# Get failed logins in last 24 hours
failed = UserLoginHistory.get_failed_logins(username='admin', hours=24)
print(f"Failed login attempts: {failed.count()}")

# Get all logins from specific IP
ip_logins = UserLoginHistory.objects.filter(ip_address='192.168.1.100')

# Get mobile logins
mobile_logins = UserLoginHistory.objects.filter(device_type='mobile')

# Get all successful logins for user
user_logins = UserLoginHistory.objects.filter(
    user=user,
    success=True
).order_by('-login_at')
```

### ChangeLog

**Purpose**: Track major system changes for production change management

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| change_type | CharField | deployment, configuration, schema_change, security_update, etc. |
| title | CharField | Brief title of the change |
| description | TextField | Detailed description |
| version | CharField | Version number (e.g., v1.2.3) |
| impact_level | CharField | critical, high, medium, low |
| affected_systems | JSONField | List of affected systems/modules |
| change_request_id | CharField | Reference to change request/ticket |
| approval_status | CharField | pending, approved, rejected, emergency |
| approved_by | ForeignKey | User who approved the change |
| performed_by | ForeignKey | User who performed the change |
| deployed_at | DateTimeField | When change was deployed |
| can_rollback | Boolean | Whether change can be rolled back |
| rollback_instructions | TextField | Instructions for rollback |
| rolled_back | Boolean | Whether change has been rolled back |
| rolled_back_at | DateTimeField | When rollback was performed |
| rolled_back_by | ForeignKey | User who performed rollback |
| testing_notes | TextField | Testing performed before deployment |
| validation_status | CharField | pending, passed, failed, skipped |
| documentation_url | URLField | Link to detailed documentation |
| jira_ticket | CharField | Jira/ticket reference |
| git_commit | CharField | Git commit hash |
| git_branch | CharField | Git branch name |
| metadata | JSONField | Additional metadata |

**Indexes**:
- `change_type, deployed_at` (composite)
- `impact_level, deployed_at` (composite)
- `rolled_back, deployed_at` (composite)

**Example Usage**:

```python
from core.security_models import ChangeLog

# Log a deployment
ChangeLog.log_change(
    change_type='deployment',
    title='Deploy v1.2.3 with security patches',
    description='Deployed security updates for authentication system',
    performed_by=request.user,
    version='v1.2.3',
    impact_level='high',
    affected_systems=['authentication', 'api'],
    git_commit='abc123def456',
    git_branch='main',
    jira_ticket='SEC-1234',
    can_rollback=True,
    rollback_instructions='git checkout v1.2.2 && ./deploy.sh',
    testing_notes='All tests passed. Security scan completed.'
)

# Log a configuration change
ChangeLog.log_change(
    change_type='configuration',
    title='Updated rate limiting settings',
    description='Increased API rate limit from 100 to 200 requests/min',
    performed_by=request.user,
    impact_level='medium',
    affected_systems=['api', 'middleware']
)

# Get recent changes
recent = ChangeLog.get_recent_changes(days=30)

# Get critical changes
critical = ChangeLog.get_critical_changes()

# Mark change as rolled back
change = ChangeLog.objects.get(id=1)
change.mark_rollback(
    user=request.user,
    notes='Rolled back due to performance issues'
)
```

## Integration with Authentication

The logging system is automatically integrated with the authentication flow:

### Login Flow

```python
# In authentication/views.py login()

# Successful login
UserLoginHistory.log_login(
    user=user,
    request=request,
    success=True,
    login_type='password'
)

# Failed login
UserLoginHistory.log_login(
    user=user,
    request=request,
    success=False,
    failure_reason='Invalid credentials',
    login_type='password'
)
```

### Logout Flow

```python
# In authentication/views.py logout()

UserLoginHistory.log_logout(
    user=request.user,
    request=request
)
```

### Automatic IP Tracking

The system automatically captures:
- IP address (including proxy detection)
- User agent parsing (browser, OS, device type)
- Session keys for correlation
- Geographic information (if configured)
- Referrer and language headers

## Admin Interface

Both models are registered in the Django admin with comprehensive interfaces:

### User Login History Admin

**Location**: Admin → Core → User Login Histories

**Features**:
- List view with filters (success, login_type, device_type, date)
- Search by username, IP address, user agent
- Read-only (cannot be manually created or edited)
- Date hierarchy for easy navigation
- Detailed view showing all fields including metadata

**List Display**:
- Username
- Success/Failed status
- Login type
- IP address
- Device type
- Login timestamp
- Session duration

### Change Log Admin

**Location**: Admin → Core → Change Logs

**Features**:
- List view with filters (change_type, impact_level, approval_status, rolled_back, date)
- Search by title, description, version, ticket ID, git commit
- Date hierarchy for easy navigation
- Bulk action to mark changes as rolled back
- Detailed view with all fields organized in sections

**List Display**:
- Change type
- Title
- Impact level
- Performed by
- Deployed at
- Rolled back status
- Approval status

**Sections**:
1. Change Information
2. Impact Assessment
3. Change Management
4. Execution
5. Rollback
6. Testing & Validation
7. Documentation
8. Metadata

## Production Best Practices

### 1. Login History Monitoring

**Monitor for Security Threats**:

```python
# Check for brute force attempts
from datetime import timedelta
from django.utils import timezone

# Failed logins from same IP in last hour
suspicious_ips = UserLoginHistory.objects.filter(
    success=False,
    login_at__gte=timezone.now() - timedelta(hours=1)
).values('ip_address').annotate(
    count=models.Count('id')
).filter(count__gte=5)

# Multiple failed logins for same user
suspicious_users = UserLoginHistory.objects.filter(
    success=False,
    login_at__gte=timezone.now() - timedelta(hours=1)
).values('username').annotate(
    count=models.Count('id')
).filter(count__gte=5)

# Logins from unusual locations
user_logins = UserLoginHistory.objects.filter(
    user=user,
    success=True
).order_by('-login_at')

# Check for country changes
if user_logins.count() > 1:
    if user_logins[0].country != user_logins[1].country:
        # Alert on country change
        print(f"Alert: User logged in from different country!")
```

**Dashboard Metrics**:

```python
# Total logins today
today_logins = UserLoginHistory.objects.filter(
    login_at__date=timezone.now().date()
).count()

# Success rate
total = UserLoginHistory.objects.filter(
    login_at__gte=timezone.now() - timedelta(days=7)
).count()
successful = UserLoginHistory.objects.filter(
    login_at__gte=timezone.now() - timedelta(days=7),
    success=True
).count()
success_rate = (successful / total * 100) if total > 0 else 0

# Most common login times
from django.db.models.functions import TruncHour
hourly_logins = UserLoginHistory.objects.filter(
    login_at__gte=timezone.now() - timedelta(days=7)
).annotate(
    hour=TruncHour('login_at')
).values('hour').annotate(
    count=models.Count('id')
).order_by('-count')

# Device type distribution
device_stats = UserLoginHistory.objects.filter(
    login_at__gte=timezone.now() - timedelta(days=30)
).values('device_type').annotate(
    count=models.Count('id')
)
```

### 2. Change Log Management

**Before Every Production Change**:

```python
# Create changelog entry BEFORE deploying
changelog = ChangeLog.log_change(
    change_type='deployment',
    title='Deploy authentication security patch',
    description='''
    Deploying security patch for authentication system:
    - Fixed JWT token validation vulnerability
    - Updated password hashing algorithm
    - Added rate limiting to login endpoints
    ''',
    performed_by=request.user,
    version='v1.3.1',
    impact_level='high',
    affected_systems=['authentication', 'api', 'security'],
    change_request_id='CHG-2024-001',
    approval_status='approved',
    approved_by=manager_user,
    can_rollback=True,
    rollback_instructions='''
    1. git checkout v1.3.0
    2. python manage.py migrate core 0001
    3. ./deploy.sh
    4. Verify rollback with ./test_auth.sh
    ''',
    testing_notes='''
    - All unit tests passed (523/523)
    - Integration tests passed (89/89)
    - Security scan completed - no issues
    - Load test completed - performance acceptable
    - Penetration test completed - vulnerabilities fixed
    ''',
    jira_ticket='SEC-4567',
    git_commit='abc123def456789',
    git_branch='main',
    documentation_url='https://wiki.company.com/deploys/v1.3.1',
    metadata={
        'deployment_method': 'rolling',
        'downtime': '0 seconds',
        'rollback_tested': True,
        'backup_completed': True
    }
)
```

**After Deployment**:

```python
# Update changelog with results
changelog.validation_status = 'passed'
changelog.save()

# If rollback needed
if deployment_failed:
    changelog.mark_rollback(
        user=request.user,
        notes='Deployment failed - performance degradation detected'
    )
```

**Change Log Reports**:

```python
# Get all changes this month
from django.db.models import Count

monthly_changes = ChangeLog.objects.filter(
    deployed_at__month=timezone.now().month
).values('change_type').annotate(
    count=Count('id')
)

# Get high-impact changes
high_impact = ChangeLog.objects.filter(
    impact_level__in=['critical', 'high'],
    deployed_at__gte=timezone.now() - timedelta(days=90)
)

# Get rollback rate
total_changes = ChangeLog.objects.filter(
    deployed_at__gte=timezone.now() - timedelta(days=90)
).count()
rolled_back = ChangeLog.objects.filter(
    deployed_at__gte=timezone.now() - timedelta(days=90),
    rolled_back=True
).count()
rollback_rate = (rolled_back / total_changes * 100) if total_changes > 0 else 0

# Changes by team member
user_changes = ChangeLog.objects.filter(
    deployed_at__gte=timezone.now() - timedelta(days=30)
).values('performed_by__username').annotate(
    count=Count('id')
).order_by('-count')
```

### 3. Data Retention

**Cleanup Old Logs**:

```python
# Run periodically (e.g., via cron or celery)
from datetime import timedelta
from django.utils import timezone

# Delete login history older than 1 year
cutoff_date = timezone.now() - timedelta(days=365)
old_logins = UserLoginHistory.objects.filter(login_at__lt=cutoff_date)
count = old_logins.count()
old_logins.delete()
print(f"Deleted {count} old login records")

# Archive changelogs older than 2 years
archive_date = timezone.now() - timedelta(days=730)
old_changes = ChangeLog.objects.filter(deployed_at__lt=archive_date)
# Export to JSON or archive system before deleting
```

**Recommended Retention Periods**:

| Log Type | Retention Period | Reason |
|----------|------------------|---------|
| Successful Logins | 90 days | Compliance, audit trail |
| Failed Logins | 180 days | Security analysis, threat detection |
| Security Events (high/critical) | 2 years | Compliance, incident investigation |
| Changelogs (critical) | Indefinite | Rollback reference, audit |
| Changelogs (low/medium) | 1 year | Historical reference |

### 4. Security Monitoring

**Real-time Alerts**:

```python
# Implement alerts for suspicious activity

# Alert on multiple failed logins
def check_failed_logins():
    """Run every 5 minutes"""
    recent_failures = UserLoginHistory.objects.filter(
        success=False,
        login_at__gte=timezone.now() - timedelta(minutes=5)
    ).values('username').annotate(
        count=Count('id')
    ).filter(count__gte=3)

    for failure in recent_failures:
        send_alert(
            f"Multiple failed login attempts for {failure['username']}"
        )

# Alert on logins from new locations
def check_new_locations(user):
    recent_logins = UserLoginHistory.objects.filter(
        user=user,
        success=True
    ).order_by('-login_at')[:10]

    known_countries = set(recent_logins.values_list('country', flat=True))
    latest_login = recent_logins[0]

    if latest_login.country not in known_countries:
        send_alert(
            f"Login from new country: {latest_login.country} "
            f"for user {user.username}"
        )

# Alert on critical changes without approval
def check_unapproved_changes():
    """Run every hour"""
    unapproved = ChangeLog.objects.filter(
        impact_level='critical',
        approval_status='pending',
        deployed_at__gte=timezone.now() - timedelta(hours=1)
    )

    if unapproved.exists():
        send_alert(
            f"Critical changes deployed without approval: {unapproved.count()}"
        )
```

## API Endpoints

### Login History API

```python
# Add to urls.py
from core import views

urlpatterns = [
    path('api/my-logins/', views.my_login_history, name='my_login_history'),
]

# In core/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_login_history(request):
    """Get current user's login history"""
    logins = UserLoginHistory.objects.filter(
        user=request.user
    ).order_by('-login_at')[:50]

    data = [{
        'login_at': login.login_at,
        'ip_address': login.ip_address,
        'device_type': login.device_type,
        'login_type': login.login_type,
        'success': login.success,
        'city': login.city,
        'country': login.country,
        'session_duration': str(login.session_duration) if login.session_duration else None
    } for login in logins]

    return Response(data)
```

### Changelog API

```python
# Add to urls.py
urlpatterns = [
    path('api/changelogs/', views.recent_changelogs, name='recent_changelogs'),
]

# In core/views.py
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_changelogs(request):
    """Get recent system changes"""
    changes = ChangeLog.objects.all().order_by('-deployed_at')[:20]

    data = [{
        'id': change.id,
        'change_type': change.change_type,
        'title': change.title,
        'description': change.description,
        'version': change.version,
        'impact_level': change.impact_level,
        'deployed_at': change.deployed_at,
        'performed_by': change.performed_by.username if change.performed_by else None,
        'rolled_back': change.rolled_back
    } for change in changes]

    return Response(data)
```

## Compliance & Audit

### SOC 2 Compliance

The logging system supports SOC 2 requirements:

- **CC6.1 (Access Control)**: UserLoginHistory tracks all access attempts
- **CC7.2 (System Monitoring)**: ChangeLog tracks all system changes
- **CC7.3 (Anomaly Detection)**: Failed login tracking enables threat detection
- **CC8.1 (Change Management)**: Complete change management workflow

### GDPR Compliance

**Right to Access**: Users can request their login history
**Right to Erasure**: Delete user's login history on request
**Data Minimization**: Only collect necessary information
**Purpose Limitation**: Data used only for security purposes

```python
# GDPR: Export user's login data
def export_user_data(user):
    logins = UserLoginHistory.objects.filter(user=user)
    data = {
        'logins': list(logins.values()),
        'total_logins': logins.count(),
        'failed_logins': logins.filter(success=False).count()
    }
    return data

# GDPR: Delete user's login history
def delete_user_login_history(user):
    UserLoginHistory.objects.filter(user=user).delete()
```

## Monitoring Dashboard

Example Grafana/monitoring queries:

```sql
-- Total logins per hour
SELECT
    date_trunc('hour', login_at) as hour,
    COUNT(*) as logins
FROM core_userloginhistory
WHERE login_at >= NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;

-- Failed login rate
SELECT
    COUNT(CASE WHEN success = false THEN 1 END)::float /
    COUNT(*)::float * 100 as failed_rate
FROM core_userloginhistory
WHERE login_at >= NOW() - INTERVAL '24 hours';

-- Top IPs by failed logins
SELECT
    ip_address,
    COUNT(*) as failed_attempts
FROM core_userloginhistory
WHERE success = false
    AND login_at >= NOW() - INTERVAL '1 hour'
GROUP BY ip_address
ORDER BY failed_attempts DESC
LIMIT 10;

-- Changes by impact level
SELECT
    impact_level,
    COUNT(*) as changes
FROM core_changelog
WHERE deployed_at >= NOW() - INTERVAL '30 days'
GROUP BY impact_level
ORDER BY changes DESC;
```

## Troubleshooting

### Issue: Login history not being recorded

**Solution**:
1. Check migrations: `python manage.py migrate core`
2. Verify imports in authentication/views.py
3. Check for errors in logs

### Issue: Session duration not calculated

**Solution**:
- Logout endpoint must be called to calculate duration
- Check if UserLoginHistory.log_logout() is called

### Issue: Geographic information missing

**Solution**:
- Geographic data requires external service (GeoIP)
- Optional feature - system works without it

### Issue: Change log admin action not working

**Solution**:
- Ensure user has permissions
- Check if change is already marked as rolled back

## Summary

This production logging system provides:

1. **Complete Audit Trail**: Every login and logout tracked with full details
2. **IP Address Tracking**: All access attempts recorded with IP, user agent, device type
3. **Change Management**: Full lifecycle tracking for production changes
4. **Security Monitoring**: Real-time detection of suspicious activity
5. **Compliance**: Supports SOC 2, GDPR, ISO 27001 requirements
6. **Rollback Capability**: Track and manage system rollbacks
7. **Admin Interface**: Easy access to logs via Django admin
8. **API Access**: Programmatic access to logging data

The system is production-ready and essential for maintaining security, compliance, and operational excellence in production environments.
