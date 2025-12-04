"""
OAuth and MFA API Views
Handles OAuth authentication and Multi-Factor Authentication
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import requests
import pyotp
import qrcode
import io
import base64

from .models import (
    User, UserEmailSettings, OAuthProvider, MFADevice
)
from core.email_service import EmailService


# ============================================================================
# OAUTH AUTHENTICATION
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def oauth_init(request, provider):
    """
    Initialize OAuth flow
    GET /api/v1/auth/oauth/{provider}/init

    Supported providers: google, github, microsoft, facebook, linkedin

    Response:
    {
        "authorization_url": "https://..."
    }
    """

    oauth_config = get_oauth_config(provider)

    if not oauth_config:
        return Response(
            {'error': f'OAuth provider "{provider}" not configured'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Build authorization URL
    params = {
        'client_id': oauth_config['client_id'],
        'redirect_uri': oauth_config['redirect_uri'],
        'response_type': 'code',
        'scope': ' '.join(oauth_config['scopes']),
        'state': generate_state_token()  # CSRF protection
    }

    if provider == 'google':
        params['access_type'] = 'offline'
        params['prompt'] = 'consent'

    authorization_url = oauth_config['auth_url'] + '?' + urlencode(params)

    return Response({
        'authorization_url': authorization_url,
        'provider': provider
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def oauth_callback(request, provider):
    """
    OAuth callback handler
    POST /api/v1/auth/oauth/{provider}/callback

    Request:
    {
        "code": "authorization_code",
        "state": "state_token"
    }

    Response:
    {
        "user": {...},
        "tokens": {...},
        "is_new_user": bool
    }
    """

    code = request.data.get('code')
    state = request.data.get('state')

    if not code:
        return Response(
            {'error': 'Authorization code is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    oauth_config = get_oauth_config(provider)

    if not oauth_config:
        return Response(
            {'error': f'OAuth provider "{provider}" not configured'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Exchange code for access token
        token_data = exchange_code_for_token(provider, code, oauth_config)

        if not token_data:
            return Response(
                {'error': 'Failed to exchange authorization code'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get user info from provider
        user_info = get_oauth_user_info(provider, token_data['access_token'], oauth_config)

        if not user_info:
            return Response(
                {'error': 'Failed to retrieve user information'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find or create user
        with transaction.atomic():
            email = user_info.get('email', '').lower()
            provider_uid = user_info.get('id') or user_info.get('sub')

            if not email or not provider_uid:
                return Response(
                    {'error': 'Email or provider ID not available'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if OAuth connection exists
            try:
                oauth_conn = OAuthProvider.objects.get(
                    provider=provider,
                    provider_uid=provider_uid
                )
                user = oauth_conn.user
                is_new_user = False

                # Update OAuth data
                oauth_conn.access_token = token_data['access_token']
                oauth_conn.refresh_token = token_data.get('refresh_token', '')
                oauth_conn.profile_data = user_info
                oauth_conn.last_login_at = timezone.now()
                oauth_conn.save()

            except OAuthProvider.DoesNotExist:
                # Check if user exists with this email
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'full_name': user_info.get('name', ''),
                        'signup_source': 'oauth',
                        'oauth_provider': provider,
                        'oauth_uid': provider_uid,
                        'is_email_fixed': True,
                        'email_verified': user_info.get('email_verified', False),
                        'onboarding_status': 'active'
                    }
                )

                is_new_user = created

                # If user exists but this is a new OAuth connection
                if not created:
                    # Update OAuth info
                    user.oauth_provider = provider
                    user.oauth_uid = provider_uid
                    user.save()

                # Create OAuth connection
                oauth_conn = OAuthProvider.objects.create(
                    user=user,
                    provider=provider,
                    provider_uid=provider_uid,
                    provider_email=email,
                    provider_username=user_info.get('login') or user_info.get('username', ''),
                    access_token=token_data['access_token'],
                    refresh_token=token_data.get('refresh_token', ''),
                    profile_data=user_info,
                    is_primary=True,
                    last_login_at=timezone.now()
                )

                # Create email settings if new user
                if created:
                    UserEmailSettings.objects.create(
                        user=user,
                        notifications_enabled=True
                    )

            # Update last login
            user.last_login = timezone.now()
            user.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'user': {
                    'email': user.email,
                    'username': user.username,
                    'full_name': user.full_name,
                    'email_verified': user.email_verified,
                    'onboarding_status': user.onboarding_status,
                    'mfa_enabled': user.mfa_enabled,
                    'mfa_required': user.mfa_required
                },
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                },
                'is_new_user': is_new_user,
                'oauth_provider': provider
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': 'OAuth authentication failed', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# MFA - TOTP (Authenticator App)
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mfa_setup_totp(request):
    """
    Set up TOTP MFA
    POST /api/v1/auth/mfa/totp/setup

    Request:
    {
        "device_name": "My iPhone"
    }

    Response:
    {
        "secret": "BASE32SECRET",
        "qr_code": "data:image/png;base64,...",
        "uri": "otpauth://totp/...",
        "device_id": 123
    }
    """

    user = request.user
    device_name = request.data.get('device_name', 'Authenticator App')

    # Check if user already has active TOTP device
    existing_device = MFADevice.objects.filter(
        user=user,
        device_type='totp',
        is_active=True
    ).first()

    if existing_device:
        return Response(
            {'error': 'TOTP MFA is already set up. Disable existing device first.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create new TOTP device
    device = MFADevice.objects.create(
        user=user,
        device_type='totp',
        device_name=device_name,
        is_verified=False
    )

    # Get provisioning URI
    totp_uri = device.get_totp_uri()

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_code_base64 = base64.b64encode(buffer.read()).decode()

    return Response({
        'device_id': device.id,
        'secret': device.totp_secret,
        'qr_code': f'data:image/png;base64,{qr_code_base64}',
        'uri': totp_uri,
        'message': 'Scan the QR code with your authenticator app, then verify with a code'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mfa_verify_totp(request):
    """
    Verify TOTP setup
    POST /api/v1/auth/mfa/totp/verify

    Request:
    {
        "device_id": 123,
        "code": "123456"
    }

    Response:
    {
        "success": true,
        "backup_codes": [...]
    }
    """

    user = request.user
    device_id = request.data.get('device_id')
    code = request.data.get('code')

    if not device_id or not code:
        return Response(
            {'error': 'Device ID and code are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        device = MFADevice.objects.get(id=device_id, user=user, device_type='totp')

        if device.is_verified:
            return Response(
                {'error': 'Device is already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify code
        if device.verify_totp(code):
            device.is_verified = True
            device.is_primary = not MFADevice.objects.filter(
                user=user,
                is_active=True,
                is_verified=True
            ).exists()
            device.save()

            # Activate MFA for user
            user.activate_mfa()

            # Generate backup codes
            backup_device = MFADevice.objects.create(
                user=user,
                device_type='backup_codes',
                device_name='Backup Codes',
                is_verified=True
            )
            backup_codes = backup_device.backup_codes

            return Response({
                'success': True,
                'message': 'TOTP MFA enabled successfully',
                'backup_codes': backup_codes,
                'important': 'Save these backup codes in a safe place. They can be used if you lose access to your authenticator app.'
            })
        else:
            return Response(
                {'error': 'Invalid verification code'},
                status=status.HTTP_400_BAD_REQUEST
            )

    except MFADevice.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mfa_disable(request):
    """
    Disable MFA
    POST /api/v1/auth/mfa/disable

    Request:
    {
        "password": "user_password"
    }
    """

    user = request.user
    password = request.data.get('password')

    if not password:
        return Response(
            {'error': 'Password is required to disable MFA'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verify password
    if not user.check_password(password):
        return Response(
            {'error': 'Invalid password'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Disable all MFA devices
    MFADevice.objects.filter(user=user).update(is_active=False)

    # Deactivate MFA for user
    user.deactivate_mfa()

    return Response({
        'success': True,
        'message': 'MFA disabled successfully'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mfa_list_devices(request):
    """
    List user's MFA devices
    GET /api/v1/auth/mfa/devices
    """

    user = request.user
    devices = MFADevice.objects.filter(user=user, is_active=True)

    return Response({
        'devices': [
            {
                'id': device.id,
                'type': device.device_type,
                'name': device.device_name,
                'is_primary': device.is_primary,
                'is_verified': device.is_verified,
                'last_used': device.last_used_at,
                'created_at': device.created_at
            }
            for device in devices
        ]
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def mfa_verify_login(request):
    """
    Verify MFA code during login
    POST /api/v1/auth/mfa/verify-login

    Request:
    {
        "email": "user@example.com",
        "code": "123456",
        "device_type": "totp"
    }

    Response:
    {
        "success": true,
        "tokens": {...}
    }
    """

    email = request.data.get('email', '').lower()
    code = request.data.get('code')
    device_type = request.data.get('device_type', 'totp')

    if not email or not code:
        return Response(
            {'error': 'Email and code are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)

        if not user.mfa_enabled:
            return Response(
                {'error': 'MFA is not enabled for this user'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get primary device of specified type
        device = MFADevice.objects.filter(
            user=user,
            device_type=device_type,
            is_active=True,
            is_verified=True
        ).first()

        if not device:
            return Response(
                {'error': f'No {device_type} device found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Verify code
        verified = False
        if device_type == 'totp':
            verified = device.verify_totp(code)
        elif device_type == 'backup_codes':
            verified = device.use_backup_code(code)

        if verified:
            # Generate tokens
            refresh = RefreshToken.for_user(user)

            # Update last login
            user.last_login = timezone.now()
            user.save()

            return Response({
                'success': True,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                },
                'user': {
                    'email': user.email,
                    'username': user.username,
                    'full_name': user.full_name
                }
            })
        else:
            return Response(
                {'error': 'Invalid verification code'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    except User.DoesNotExist:
        return Response(
            {'error': 'User not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_oauth_config(provider):
    """Get OAuth configuration for provider"""

    configs = {
        'google': {
            'client_id': getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', ''),
            'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
            'token_url': 'https://oauth2.googleapis.com/token',
            'user_info_url': 'https://www.googleapis.com/oauth2/v2/userinfo',
            'redirect_uri': f"{settings.BACKEND_URL}/api/v1/auth/oauth/google/callback",
            'scopes': ['openid', 'email', 'profile']
        },
        'github': {
            'client_id': getattr(settings, 'GITHUB_OAUTH_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'GITHUB_OAUTH_CLIENT_SECRET', ''),
            'auth_url': 'https://github.com/login/oauth/authorize',
            'token_url': 'https://github.com/login/oauth/access_token',
            'user_info_url': 'https://api.github.com/user',
            'redirect_uri': f"{settings.BACKEND_URL}/api/v1/auth/oauth/github/callback",
            'scopes': ['user:email']
        },
        'microsoft': {
            'client_id': getattr(settings, 'MICROSOFT_OAUTH_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'MICROSOFT_OAUTH_CLIENT_SECRET', ''),
            'auth_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
            'token_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
            'user_info_url': 'https://graph.microsoft.com/v1.0/me',
            'redirect_uri': f"{settings.BACKEND_URL}/api/v1/auth/oauth/microsoft/callback",
            'scopes': ['openid', 'email', 'profile']
        }
    }

    config = configs.get(provider)

    # Check if configured
    if config and config['client_id'] and config['client_secret']:
        return config

    return None


def exchange_code_for_token(provider, code, oauth_config):
    """Exchange authorization code for access token"""

    data = {
        'client_id': oauth_config['client_id'],
        'client_secret': oauth_config['client_secret'],
        'code': code,
        'redirect_uri': oauth_config['redirect_uri'],
        'grant_type': 'authorization_code'
    }

    headers = {'Accept': 'application/json'}

    try:
        response = requests.post(
            oauth_config['token_url'],
            data=data,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()

    except Exception:
        pass

    return None


def get_oauth_user_info(provider, access_token, oauth_config):
    """Get user information from OAuth provider"""

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(
            oauth_config['user_info_url'],
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            user_data = response.json()

            # Normalize data across providers
            if provider == 'github':
                # GitHub email might not be in user endpoint
                if not user_data.get('email'):
                    # Fetch emails separately
                    emails_response = requests.get(
                        'https://api.github.com/user/emails',
                        headers=headers
                    )
                    if emails_response.status_code == 200:
                        emails = emails_response.json()
                        primary_email = next(
                            (e for e in emails if e.get('primary')),
                            emails[0] if emails else None
                        )
                        if primary_email:
                            user_data['email'] = primary_email['email']
                            user_data['email_verified'] = primary_email.get('verified', False)

            return user_data

    except Exception:
        pass

    return None


def generate_state_token():
    """Generate CSRF state token"""
    import secrets
    return secrets.token_urlsafe(32)


def urlencode(params):
    """URL encode parameters"""
    from urllib.parse import urlencode as _urlencode
    return _urlencode(params)
