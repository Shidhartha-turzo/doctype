from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from .models import MagicLink, UserSession
from .serializers import (
    MagicLinkRequestSerializer,
    LoginSerializer,
    TokenSerializer,
    RefreshTokenSerializer,
    UserSessionSerializer
)
from drf_spectacular.utils import extend_schema
from core.security_utils import (
    get_client_ip,
    get_user_agent,
    check_brute_force,
    record_login_attempt
)


def create_tokens_and_session(user, request):
    """Create JWT tokens and session for user"""
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    session = UserSession.objects.create(
        user=user,
        refresh_token=refresh_token,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
    )

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'session_key': session.session_key,
        'user': user
    }


@extend_schema(
    request=MagicLinkRequestSerializer,
    responses={200: {'type': 'object', 'properties': {'message': {'type': 'string'}}}}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def request_magic_link(request):
    """Request a magic link for passwordless login"""
    serializer = MagicLinkRequestSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data['email']
        magic_link = MagicLink.objects.create(email=email)

        magic_link_url = f"http://localhost:3000/auth/magic-link/{magic_link.token}/"

        send_mail(
            'Your Magic Link',
            f'Click here to log in: {magic_link_url}',
            'noreply@doctype.com',
            [email],
            fail_silently=True,
        )

        return Response({
            'message': 'Magic link sent to your email',
            'dev_token': magic_link.token if settings.DEBUG else None
        })

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(request=LoginSerializer, responses={200: TokenSerializer})
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Login with username and password - Protected against brute force attacks"""
    from core.security_models import UserLoginHistory

    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    username = request.data.get('username', '')

    # Check for brute force attack
    is_blocked, reason, lockout_duration = check_brute_force(username, ip_address)
    if is_blocked:
        # Record the blocked attempt
        record_login_attempt(
            username=username,
            ip_address=ip_address,
            success=False,
            user_agent=user_agent,
            failure_reason=f'Blocked: {reason}'
        )
        return Response({
            'error': 'Too many failed attempts',
            'detail': reason,
            'retry_after': lockout_duration
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # Validate credentials
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']

        # Record successful login (existing system)
        record_login_attempt(
            username=username,
            ip_address=ip_address,
            success=True,
            user_agent=user_agent
        )

        # Log to UserLoginHistory (new detailed tracking)
        UserLoginHistory.log_login(
            user=user,
            request=request,
            success=True,
            login_type='password'
        )

        # Create tokens and session
        token_data = create_tokens_and_session(user, request)
        response_serializer = TokenSerializer(token_data)
        return Response(response_serializer.data)

    # Record failed login
    record_login_attempt(
        username=username,
        ip_address=ip_address,
        success=False,
        user_agent=user_agent,
        failure_reason='Invalid credentials'
    )

    # Log failed login to UserLoginHistory
    try:
        user = User.objects.get(username=username)
        UserLoginHistory.log_login(
            user=user,
            request=request,
            success=False,
            failure_reason='Invalid credentials',
            login_type='password'
        )
    except User.DoesNotExist:
        pass  # User doesn't exist, skip detailed logging

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(request=RefreshTokenSerializer, responses={200: {'type': 'object'}})
@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """Refresh access token"""
    serializer = RefreshTokenSerializer(data=request.data)
    if serializer.is_valid():
        refresh_token = serializer.validated_data['refresh_token']

        try:
            session = UserSession.objects.get(refresh_token=refresh_token, is_active=True)

            if not session.is_valid():
                return Response({'error': 'Session expired'}, status=status.HTTP_401_UNAUTHORIZED)

            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)

            return Response({'access_token': access_token})

        except UserSession.DoesNotExist:
            return Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(responses={200: UserSessionSerializer(many=True)})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_sessions(request):
    """List active sessions for the current user"""
    sessions = UserSession.objects.filter(user=request.user, is_active=True)
    serializer = UserSessionSerializer(sessions, many=True)
    return Response(serializer.data)


@extend_schema(responses={204: None})
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout and deactivate session"""
    from core.security_models import SecurityAuditLog, UserLoginHistory

    session_key = request.data.get('session_key') or request.META.get('HTTP_X_SESSION_KEY')

    if session_key:
        try:
            session = UserSession.objects.get(session_key=session_key, user=request.user, is_active=True)
            session.deactivate()

            # Log logout event
            SecurityAuditLog.log_event(
                event_type='logout',
                description=f'User {request.user.username} logged out',
                user=request.user,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
                severity='low'
            )
        except UserSession.DoesNotExist:
            pass

    # Log logout to UserLoginHistory
    UserLoginHistory.log_logout(user=request.user, request=request)

    return Response(status=status.HTTP_204_NO_CONTENT)
