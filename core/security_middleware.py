"""
Security middleware for the Doctype Engine
Provides automatic protection against common attacks.
"""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from .security_utils import (
    get_client_ip,
    get_user_agent,
    check_rate_limit,
    check_ip_whitelist,
    verify_api_key
)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses.
    Implements OWASP recommended security headers.
    """

    def process_response(self, request, response):
        from .security_models import SystemSettings

        settings = SystemSettings.get_settings()

        if not settings.enable_security_headers:
            return response

        # HTTP Strict Transport Security (HSTS)
        response['Strict-Transport-Security'] = f'max-age={settings.hsts_max_age}; includeSubDomains; preload'

        # Content Security Policy (CSP)
        if settings.enable_csp:
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
                "style-src 'self' 'unsafe-inline'",
                "img-src 'self' data: https:",
                "font-src 'self' data:",
                "connect-src 'self'",
                "frame-ancestors 'none'",
            ]
            response['Content-Security-Policy'] = '; '.join(csp_directives)

        # X-Frame-Options (Clickjacking protection)
        response['X-Frame-Options'] = 'DENY'

        # X-Content-Type-Options (MIME sniffing protection)
        response['X-Content-Type-Options'] = 'nosniff'

        # X-XSS-Protection (Legacy XSS protection)
        response['X-XSS-Protection'] = '1; mode=block'

        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy (formerly Feature Policy)
        permissions_directives = [
            'geolocation=()',
            'microphone=()',
            'camera=()',
            'payment=()',
            'usb=()',
            'magnetometer=()',
        ]
        response['Permissions-Policy'] = ', '.join(permissions_directives)

        return response


class RateLimitMiddleware(MiddlewareMixin):
    """
    Global rate limiting middleware.
    Protects all endpoints from abuse.
    """

    def process_request(self, request):
        from .security_models import SystemSettings, SecurityAuditLog

        settings = SystemSettings.get_settings()

        if not settings.enable_rate_limiting:
            return None

        # Skip rate limiting for certain paths
        exempt_paths = ['/admin/', '/static/', '/media/']
        if any(request.path.startswith(path) for path in exempt_paths):
            return None

        # Determine rate limit based on authentication
        if request.user.is_authenticated:
            limit = settings.api_rate_limit_authenticated
        else:
            limit = settings.api_rate_limit_anonymous

        # Use IP as identifier
        ip_address = get_client_ip(request)

        # Check rate limit (60 second window)
        is_allowed, count, retry_after = check_rate_limit(
            identifier=ip_address,
            limit=limit,
            window=60,
            prefix='global_rate_limit'
        )

        if not is_allowed:
            # Log the rate limit violation
            SecurityAuditLog.log_event(
                event_type='permission_denied',
                description='Global rate limit exceeded',
                user=request.user if request.user.is_authenticated else None,
                ip_address=ip_address,
                user_agent=get_user_agent(request),
                request_path=request.path,
                request_method=request.method,
                severity='medium',
                metadata={'retry_after': retry_after}
            )

            return JsonResponse({
                'error': 'Rate limit exceeded',
                'detail': f'Too many requests. Please try again in {retry_after} seconds.',
                'retry_after': retry_after
            }, status=429)

        return None

    def process_response(self, request, response):
        """Add rate limit headers to response"""
        from .security_models import SystemSettings

        settings = SystemSettings.get_settings()

        if settings.enable_rate_limiting and hasattr(response, 'headers'):
            # Determine rate limit based on authentication
            if request.user.is_authenticated:
                limit = settings.api_rate_limit_authenticated
            else:
                limit = settings.api_rate_limit_anonymous

            # Add headers
            response.headers['X-RateLimit-Limit'] = str(limit)

        return response


class IPBlacklistMiddleware(MiddlewareMixin):
    """
    Block requests from blacklisted IP addresses.
    """

    def process_request(self, request):
        from .security_models import IPBlacklist, SecurityAuditLog

        ip_address = get_client_ip(request)

        # Check if IP is blacklisted
        if IPBlacklist.is_blacklisted(ip_address):
            # Log the blocked attempt
            SecurityAuditLog.log_event(
                event_type='permission_denied',
                description='Request from blacklisted IP',
                ip_address=ip_address,
                user_agent=get_user_agent(request),
                request_path=request.path,
                request_method=request.method,
                severity='high'
            )

            return JsonResponse({
                'error': 'Access denied',
                'detail': 'Your IP address has been blacklisted due to suspicious activity.'
            }, status=403)

        return None


class IPWhitelistMiddleware(MiddlewareMixin):
    """
    Restrict admin access to whitelisted IPs only (if enabled).
    """

    def process_request(self, request):
        from .security_models import SystemSettings, SecurityAuditLog

        # Only check for admin paths
        if not request.path.startswith('/admin/'):
            return None

        settings = SystemSettings.get_settings()

        if not settings.require_whitelist_for_admin:
            return None

        ip_address = get_client_ip(request)

        if not settings.is_ip_whitelisted(ip_address):
            # Log the blocked attempt
            SecurityAuditLog.log_event(
                event_type='permission_denied',
                description='Admin access attempt from non-whitelisted IP',
                user=request.user if request.user.is_authenticated else None,
                ip_address=ip_address,
                user_agent=get_user_agent(request),
                request_path=request.path,
                request_method=request.method,
                severity='high'
            )

            return JsonResponse({
                'error': 'Access denied',
                'detail': 'Admin access is restricted to whitelisted IP addresses only.'
            }, status=403)

        return None


class APIKeyMiddleware(MiddlewareMixin):
    """
    Validate API keys for API requests (if enabled).
    """

    def process_request(self, request):
        from .security_models import SystemSettings, SecurityAuditLog

        settings = SystemSettings.get_settings()

        if not settings.require_api_key:
            return None

        # Only check API paths
        if not request.path.startswith('/api/'):
            return None

        # Skip authentication endpoints
        exempt_paths = ['/api/schema/', '/api/docs/']
        if any(request.path.startswith(path) for path in exempt_paths):
            return None

        # Skip if user is already authenticated via JWT
        if request.user.is_authenticated:
            return None

        # Verify API key
        is_valid, user, api_key_obj = verify_api_key(request)

        if not is_valid:
            # Log the failed attempt
            SecurityAuditLog.log_event(
                event_type='permission_denied',
                description='Invalid or missing API key',
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
                request_path=request.path,
                request_method=request.method,
                severity='medium'
            )

            return JsonResponse({
                'error': 'Authentication required',
                'detail': 'Valid API key required for this endpoint.'
            }, status=401)

        # Attach user to request
        if user:
            request.user = user

        # Attach API key object for custom rate limiting
        request.api_key = api_key_obj

        return None


class BruteForceProtectionMiddleware(MiddlewareMixin):
    """
    Protect login endpoints from brute force attacks.
    """

    def process_request(self, request):
        from .security_models import SystemSettings, SecurityAuditLog
        from .security_utils import check_brute_force

        # Only check login endpoints
        login_paths = ['/auth/login/', '/auth/magic-link/request/']
        if request.path not in login_paths:
            return None

        settings = SystemSettings.get_settings()

        if not settings.enable_brute_force_protection:
            return None

        # Only check POST requests (actual login attempts)
        if request.method != 'POST':
            return None

        ip_address = get_client_ip(request)

        # Check for username in request data
        try:
            import json
            data = json.loads(request.body) if request.body else {}
            username = data.get('username') or data.get('email', '')
        except:
            username = ''

        # Check brute force indicators
        is_blocked, reason, lockout_duration = check_brute_force(username, ip_address)

        if is_blocked:
            # Log the blocked attempt
            SecurityAuditLog.log_event(
                event_type='permission_denied',
                description=f'Login blocked: {reason}',
                username=username,
                ip_address=ip_address,
                user_agent=get_user_agent(request),
                request_path=request.path,
                request_method=request.method,
                severity='high',
                metadata={'reason': reason, 'lockout_duration': lockout_duration}
            )

            return JsonResponse({
                'error': 'Too many failed attempts',
                'detail': reason,
                'retry_after': lockout_duration
            }, status=429)

        return None


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Log all API requests (if enabled in settings).
    """

    def process_request(self, request):
        from .security_models import SystemSettings, SecurityAuditLog

        settings = SystemSettings.get_settings()

        if not settings.enable_audit_logging or not settings.log_api_requests:
            return None

        # Skip logging for certain paths to avoid noise
        skip_paths = ['/admin/', '/static/', '/media/', '/api/schema/', '/api/docs/']
        if any(request.path.startswith(path) for path in skip_paths):
            return None

        # Log the request
        SecurityAuditLog.log_event(
            event_type='suspicious_activity',  # Using this as generic API request type
            description=f'{request.method} {request.path}',
            user=request.user if request.user.is_authenticated else None,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            request_path=request.path,
            request_method=request.method,
            severity='low'
        )

        return None


class SecureJSONMiddleware(MiddlewareMixin):
    """
    Validate JSON payloads to prevent attacks via deeply nested structures.
    """

    def process_request(self, request):
        from .security_utils import validate_json_schema

        # Only check JSON requests
        if request.content_type != 'application/json':
            return None

        # Skip for GET requests (no body)
        if request.method == 'GET':
            return None

        try:
            import json
            if request.body:
                data = json.loads(request.body)

                # Validate JSON structure
                is_valid, error = validate_json_schema(data)

                if not is_valid:
                    return JsonResponse({
                        'error': 'Invalid request',
                        'detail': error
                    }, status=400)

        except json.JSONDecodeError:
            pass  # Let Django handle JSON decode errors

        return None
