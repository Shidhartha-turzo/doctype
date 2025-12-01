"""
Security utilities for the Doctype Engine
Provides helpers for rate limiting, brute force protection, IP validation, etc.
"""
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from functools import wraps
import hashlib
import re
from datetime import timedelta


def get_client_ip(request):
    """
    Extract client IP address from request.
    Handles proxies and load balancers.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip


def get_user_agent(request):
    """Extract user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')


def validate_password_strength(password, settings=None):
    """
    Validate password against security policy.
    Returns tuple: (is_valid, error_message)
    """
    if settings is None:
        from .security_models import SystemSettings
        settings = SystemSettings.get_settings()

    errors = []

    # Length check
    if len(password) < settings.min_password_length:
        errors.append(f"Password must be at least {settings.min_password_length} characters long")

    # Uppercase check
    if settings.require_uppercase and not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")

    # Lowercase check
    if settings.require_lowercase and not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")

    # Digit check
    if settings.require_digit and not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")

    # Special character check
    if settings.require_special_char and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")

    if errors:
        return False, "; ".join(errors)

    return True, ""


def check_rate_limit(identifier, limit, window, prefix='rate_limit'):
    """
    Generic rate limiting using cache.

    Args:
        identifier: Unique identifier (e.g., IP address, user ID)
        limit: Maximum number of requests
        window: Time window in seconds
        prefix: Cache key prefix

    Returns:
        tuple: (is_allowed, current_count, retry_after)
    """
    cache_key = f"{prefix}:{identifier}"
    current_count = cache.get(cache_key, 0)

    if current_count >= limit:
        # Rate limit exceeded
        ttl = cache.ttl(cache_key)
        retry_after = ttl if ttl > 0 else window
        return False, current_count, retry_after

    # Increment counter
    if current_count == 0:
        cache.set(cache_key, 1, window)
    else:
        cache.incr(cache_key)

    return True, current_count + 1, 0


def rate_limit_decorator(key_func=None, limit=None, window=None):
    """
    Decorator for rate limiting views.

    Usage:
        @rate_limit_decorator(key_func=lambda req: get_client_ip(req), limit=10, window=60)
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            from .security_models import SystemSettings
            settings = SystemSettings.get_settings()

            if not settings.enable_rate_limiting:
                return view_func(request, *args, **kwargs)

            # Determine rate limit parameters
            req_limit = limit or settings.rate_limit_requests
            req_window = window or settings.rate_limit_window

            # Get identifier
            if key_func:
                identifier = key_func(request)
            else:
                identifier = get_client_ip(request)

            # Check rate limit
            is_allowed, count, retry_after = check_rate_limit(
                identifier,
                req_limit,
                req_window,
                prefix='api_rate_limit'
            )

            if not is_allowed:
                from .security_models import SecurityAuditLog
                SecurityAuditLog.log_event(
                    event_type='permission_denied',
                    description='Rate limit exceeded',
                    ip_address=get_client_ip(request),
                    severity='medium',
                    request_path=request.path,
                    request_method=request.method,
                    user_agent=get_user_agent(request),
                    metadata={'retry_after': retry_after}
                )

                return JsonResponse({
                    'error': 'Rate limit exceeded',
                    'detail': f'Too many requests. Please try again in {retry_after} seconds.',
                    'retry_after': retry_after
                }, status=429)

            # Add rate limit headers
            response = view_func(request, *args, **kwargs)
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(req_limit)
                response.headers['X-RateLimit-Remaining'] = str(req_limit - count)
                response.headers['X-RateLimit-Reset'] = str(int(timezone.now().timestamp()) + req_window)

            return response

        return wrapped_view
    return decorator


def check_brute_force(username, ip_address):
    """
    Check for brute force attack indicators.

    Returns:
        tuple: (is_blocked, reason, lockout_duration)
    """
    from .security_models import SystemSettings, LoginAttempt, IPBlacklist

    settings = SystemSettings.get_settings()

    if not settings.enable_brute_force_protection:
        return False, "", 0

    # Check IP blacklist first
    if IPBlacklist.is_blacklisted(ip_address):
        return True, "IP address is blacklisted", settings.ip_blacklist_duration

    # Check account lockout
    if LoginAttempt.is_account_locked(username):
        return True, f"Account locked due to multiple failed attempts", settings.account_lockout_duration

    # Check IP-based rate limiting
    ip_failures = LoginAttempt.get_recent_failures(
        ip_address=ip_address,
        minutes=settings.login_rate_window // 60
    )

    if ip_failures >= settings.ip_blacklist_threshold:
        # Auto-blacklist the IP
        IPBlacklist.auto_blacklist_ip(ip_address, ip_failures)
        return True, "Too many failed attempts from this IP", settings.ip_blacklist_duration

    return False, "", 0


def record_login_attempt(username, ip_address, success, user_agent='', failure_reason=''):
    """
    Record a login attempt and handle brute force protection.

    Args:
        username: Username attempting to login
        ip_address: IP address of the attempt
        success: Boolean indicating success/failure
        user_agent: User agent string
        failure_reason: Reason for failure (if applicable)
    """
    from .security_models import LoginAttempt, SecurityAuditLog, SystemSettings

    settings = SystemSettings.get_settings()

    # Record in LoginAttempt model
    status = 'success' if success else 'failed'
    LoginAttempt.record_attempt(
        username=username,
        ip_address=ip_address,
        status=status,
        user_agent=user_agent,
        failure_reason=failure_reason
    )

    # Log to security audit log
    if success and settings.log_successful_logins:
        SecurityAuditLog.log_event(
            event_type='login_success',
            description=f'User {username} logged in successfully',
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            severity='low'
        )
    elif not success and settings.log_failed_logins:
        SecurityAuditLog.log_event(
            event_type='login_failed',
            description=f'Failed login attempt for {username}: {failure_reason}',
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            severity='medium',
            metadata={'failure_reason': failure_reason}
        )


def sanitize_input(value, max_length=None):
    """
    Sanitize user input to prevent injection attacks.

    Args:
        value: Input value to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        value = str(value)

    # Remove null bytes
    value = value.replace('\x00', '')

    # Strip leading/trailing whitespace
    value = value.strip()

    # Enforce max length
    if max_length and len(value) > max_length:
        value = value[:max_length]

    return value


def validate_json_schema(data, allowed_keys=None, max_depth=10, current_depth=0):
    """
    Validate JSON data to prevent attacks via deeply nested structures.

    Args:
        data: JSON data to validate
        allowed_keys: Set of allowed keys (None = all allowed)
        max_depth: Maximum nesting depth
        current_depth: Current depth (used in recursion)

    Returns:
        tuple: (is_valid, error_message)
    """
    if current_depth > max_depth:
        return False, f"JSON structure too deeply nested (max depth: {max_depth})"

    if isinstance(data, dict):
        # Check for too many keys
        if len(data) > 1000:
            return False, "Too many keys in JSON object (max: 1000)"

        # Check allowed keys
        if allowed_keys:
            invalid_keys = set(data.keys()) - allowed_keys
            if invalid_keys:
                return False, f"Invalid keys: {', '.join(invalid_keys)}"

        # Recursively validate nested structures
        for key, value in data.items():
            is_valid, error = validate_json_schema(value, None, max_depth, current_depth + 1)
            if not is_valid:
                return False, error

    elif isinstance(data, list):
        # Check for too many items
        if len(data) > 10000:
            return False, "Too many items in JSON array (max: 10000)"

        # Recursively validate items
        for item in data:
            is_valid, error = validate_json_schema(item, None, max_depth, current_depth + 1)
            if not is_valid:
                return False, error

    return True, ""


def generate_secure_token(length=32):
    """
    Generate a cryptographically secure random token.

    Args:
        length: Length of the token

    Returns:
        URL-safe token string
    """
    import secrets
    return secrets.token_urlsafe(length)


def hash_token(token):
    """
    Hash a token for secure storage.

    Args:
        token: Token to hash

    Returns:
        SHA256 hash of the token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_api_key(request):
    """
    Verify API key from request headers.

    Args:
        request: Django request object

    Returns:
        tuple: (is_valid, user, api_key_object)
    """
    from .security_models import SystemSettings, APIKey

    settings = SystemSettings.get_settings()

    if not settings.require_api_key:
        return True, None, None

    # Get API key from header
    api_key = request.META.get(f'HTTP_{settings.api_key_header_name.upper().replace("-", "_")}')

    if not api_key:
        return False, None, None

    # Hash the key
    key_hash = APIKey.hash_key(api_key)

    # Look up the key
    try:
        api_key_obj = APIKey.objects.select_related('user').get(key_hash=key_hash)

        if not api_key_obj.is_valid():
            return False, None, None

        # Record usage
        api_key_obj.record_usage()

        return True, api_key_obj.user, api_key_obj

    except APIKey.DoesNotExist:
        return False, None, None


def check_ip_whitelist(request):
    """
    Check if request IP is in the whitelist.

    Args:
        request: Django request object

    Returns:
        Boolean indicating if IP is whitelisted
    """
    from .security_models import SystemSettings

    settings = SystemSettings.get_settings()

    # Check if whitelist is required for admin access
    if request.path.startswith('/admin/') and settings.require_whitelist_for_admin:
        ip_address = get_client_ip(request)
        return settings.is_ip_whitelisted(ip_address)

    return True


def mask_sensitive_data(data, fields=None):
    """
    Mask sensitive data for logging.

    Args:
        data: Dictionary containing data
        fields: List of field names to mask (default: common sensitive fields)

    Returns:
        Dictionary with masked sensitive fields
    """
    if fields is None:
        fields = ['password', 'token', 'secret', 'api_key', 'credit_card', 'ssn']

    masked_data = data.copy()

    for field in fields:
        if field in masked_data:
            value = str(masked_data[field])
            if len(value) > 4:
                masked_data[field] = f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
            else:
                masked_data[field] = "****"

    return masked_data


def cleanup_expired_data():
    """
    Cleanup expired security data (blacklists, sessions, logs, etc.)
    Should be run periodically via cron or celery task.
    """
    from .security_models import IPBlacklist, SecurityAuditLog
    from authentication.models import MagicLink, UserSession

    results = {
        'ip_blacklists_removed': 0,
        'magic_links_removed': 0,
        'sessions_removed': 0,
        'audit_logs_removed': 0,
    }

    # Remove expired IP blacklists
    now = timezone.now()
    expired_blacklists = IPBlacklist.objects.filter(
        is_permanent=False,
        expires_at__lt=now
    )
    results['ip_blacklists_removed'] = expired_blacklists.delete()[0]

    # Remove expired magic links
    expired_links = MagicLink.objects.filter(expires_at__lt=now)
    results['magic_links_removed'] = expired_links.delete()[0]

    # Remove expired sessions
    expired_sessions = UserSession.objects.filter(expires_at__lt=now)
    results['sessions_removed'] = expired_sessions.delete()[0]

    # Cleanup old audit logs
    results['audit_logs_removed'] = SecurityAuditLog.cleanup_old_logs()

    return results
