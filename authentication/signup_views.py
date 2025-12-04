"""
Signup & Onboarding API Views
Handles self-signup, admin onboarding, email verification
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re

from .models import (
    User, UserEmailSettings, OnboardingInvitation,
    OAuthProvider, MFADevice, PasswordResetToken
)
from core.email_service import EmailService


# ============================================================================
# SELF-SIGNUP FLOW
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """
    Self-signup endpoint
    POST /api/v1/auth/signup

    Request:
    {
        "email": "user@example.com",
        "password": "StrongP@ssw0rd",
        "full_name": "John Doe",
        "username": "johndoe" (optional),
        "phone": "+1234567890" (optional)
    }

    Response:
    {
        "user_id": "user@example.com",
        "email": "user@example.com",
        "onboarding_status": "pending",
        "requires_email_verification": true,
        "tokens": {
            "access": "...",
            "refresh": "..."
        }
    }
    """

    # Validate input
    email = request.data.get('email', '').strip().lower()
    password = request.data.get('password')
    full_name = request.data.get('full_name', '')
    username = request.data.get('username', '').strip()
    phone = request.data.get('phone', '').strip()

    # Validation
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_email(email)
    except ValidationError:
        return Response(
            {'error': 'Invalid email format'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not password:
        return Response(
            {'error': 'Password is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate password strength
    password_validation = validate_password_strength(password)
    if not password_validation['valid']:
        return Response(
            {'error': 'Password is too weak', 'details': password_validation['errors']},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if user already exists
    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'User with this email already exists'},
            status=status.HTTP_409_CONFLICT
        )

    # Check username uniqueness if provided
    if username and User.objects.filter(username=username).exists():
        return Response(
            {'error': 'Username already taken'},
            status=status.HTTP_409_CONFLICT
        )

    # Create user
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                full_name=full_name,
                username=username or None,
                phone=phone or None,
                signup_source='self_signup',
                onboarding_status='pending',
                is_email_fixed=True,  # Will be true after verification
                email_verified=False
            )

            # Create email settings
            UserEmailSettings.objects.create(
                user=user,
                notifications_enabled=True
            )

            # Generate email verification token
            verification_token = user.generate_email_verification_token()

            # Send verification email
            should_send_email = email and user.is_email_fixed
            email_sent = False

            if should_send_email:
                email_service = EmailService()
                verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

                email_sent = email_service.send_template_email(
                    template='signup_confirmation',
                    to_email=email,
                    context={
                        'user': user,
                        'verification_url': verification_url,
                        'full_name': full_name or email.split('@')[0]
                    }
                )

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'user_id': user.email,
                'email': user.email,
                'username': user.username,
                'full_name': user.full_name,
                'onboarding_status': user.onboarding_status,
                'requires_email_verification': True,
                'email_verification_sent': email_sent,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                }
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': 'Failed to create user', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """
    Verify email with token
    POST /api/v1/auth/verify-email

    Request:
    {
        "token": "verification_token_here"
    }

    Response:
    {
        "success": true,
        "message": "Email verified successfully",
        "user": {...}
    }
    """

    token = request.data.get('token')

    if not token:
        return Response(
            {'error': 'Verification token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Find user with this token
        user = User.objects.get(email_verification_token=token)

        # Verify email
        if user.verify_email(token):
            return Response({
                'success': True,
                'message': 'Email verified successfully',
                'user': {
                    'email': user.email,
                    'email_verified': user.email_verified,
                    'onboarding_status': user.onboarding_status
                }
            })
        else:
            return Response(
                {'error': 'Invalid or expired verification token'},
                status=status.HTTP_400_BAD_REQUEST
            )

    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid verification token'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resend_verification_email(request):
    """
    Resend email verification
    POST /api/v1/auth/resend-verification

    Response:
    {
        "success": true,
        "message": "Verification email sent"
    }
    """

    user = request.user

    if user.email_verified:
        return Response(
            {'error': 'Email already verified'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if user has email
    if not user.email or not user.is_email_fixed:
        return Response(
            {'error': 'No fixed email address for this user'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Rate limiting check
    if user.email_verification_sent_at:
        time_since_last_send = timezone.now() - user.email_verification_sent_at
        if time_since_last_send.total_seconds() < 300:  # 5 minutes
            return Response(
                {'error': 'Please wait before requesting another verification email'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

    # Generate new token
    verification_token = user.generate_email_verification_token()

    # Send email
    email_service = EmailService()
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"

    email_sent = email_service.send_template_email(
        template='signup_confirmation',
        to_email=user.email,
        context={
            'user': user,
            'verification_url': verification_url,
            'full_name': user.full_name or user.email.split('@')[0]
        }
    )

    if email_sent:
        return Response({
            'success': True,
            'message': 'Verification email sent'
        })
    else:
        return Response(
            {'error': 'Failed to send verification email'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# ADMIN ONBOARDING FLOW
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_onboard_user(request):
    """
    Admin onboards a new user
    POST /api/v1/admin/users/onboard

    Request:
    {
        "email": "newuser@example.com",
        "full_name": "New User",
        "username": "newuser" (optional),
        "is_email_fixed": true,
        "send_invitation_email": true,
        "role": "staff",
        "welcome_message": "Welcome to the team!"
    }

    Response:
    {
        "user_id": "newuser@example.com",
        "onboarding_status": "invited",
        "invitation_link": "https://...",
        "invitation_sent": true
    }
    """

    # Validate input
    email = request.data.get('email', '').strip().lower()
    full_name = request.data.get('full_name', '')
    username = request.data.get('username', '').strip()
    is_email_fixed = request.data.get('is_email_fixed', True)
    send_invitation = request.data.get('send_invitation_email', True)
    role = request.data.get('role', 'user')
    welcome_message = request.data.get('welcome_message', '')

    # Validation
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_email(email)
    except ValidationError:
        return Response(
            {'error': 'Invalid email format'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Check if user already exists
    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'User with this email already exists'},
            status=status.HTTP_409_CONFLICT
        )

    # Create user
    try:
        with transaction.atomic():
            # Create user without password (will be set during onboarding)
            user = User.objects.create_user(
                email=email,
                password=None,
                full_name=full_name,
                username=username or None,
                signup_source='admin_onboarded',
                onboarding_status='invited',
                is_email_fixed=is_email_fixed,
                email_verified=is_email_fixed  # Admin trusts this email
            )

            # Set password to unusable (user will set during onboarding)
            user.set_unusable_password()
            user.save()

            # Create email settings
            UserEmailSettings.objects.create(
                user=user,
                notifications_enabled=True
            )

            # Create invitation
            invitation = OnboardingInvitation.objects.create(
                user=user,
                invited_by=request.user,
                role_assigned=role,
                welcome_message=welcome_message
            )

            # Build invitation URL
            invitation_url = f"{settings.FRONTEND_URL}/onboard?token={invitation.invitation_token}"
            invitation.invitation_url = invitation_url
            invitation.save()

            # Send invitation email if conditions met
            email_sent = False
            if email and is_email_fixed and send_invitation:
                email_service = EmailService()
                email_sent = email_service.send_template_email(
                    template='onboarding_invitation',
                    to_email=email,
                    context={
                        'user': user,
                        'invited_by': request.user,
                        'invitation_url': invitation_url,
                        'welcome_message': welcome_message,
                        'role': role
                    }
                )

                if email_sent:
                    invitation.email_sent = True
                    invitation.email_sent_at = timezone.now()
                    invitation.status = 'sent'
                    invitation.save()

            return Response({
                'user_id': user.email,
                'email': user.email,
                'username': user.username,
                'onboarding_status': user.onboarding_status,
                'invitation_id': invitation.id,
                'invitation_link': invitation_url,
                'invitation_sent': email_sent,
                'expires_at': invitation.expires_at.isoformat()
            }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': 'Failed to onboard user', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def complete_onboarding(request):
    """
    User completes onboarding with invitation token
    POST /api/v1/auth/complete-onboarding

    Request:
    {
        "token": "invitation_token",
        "password": "NewPassword123!",
        "accept_terms": true
    }

    Response:
    {
        "success": true,
        "user": {...},
        "tokens": {...}
    }
    """

    token = request.data.get('token')
    password = request.data.get('password')
    accept_terms = request.data.get('accept_terms', False)

    # Validation
    if not token:
        return Response(
            {'error': 'Invitation token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not password:
        return Response(
            {'error': 'Password is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not accept_terms:
        return Response(
            {'error': 'You must accept the terms and conditions'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate password strength
    password_validation = validate_password_strength(password)
    if not password_validation['valid']:
        return Response(
            {'error': 'Password is too weak', 'details': password_validation['errors']},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Find invitation
        invitation = OnboardingInvitation.objects.get(invitation_token=token)

        # Check if valid
        if not invitation.is_valid():
            return Response(
                {'error': 'Invitation has expired or is no longer valid'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update user
        with transaction.atomic():
            user = invitation.user
            user.set_password(password)
            user.save()

            # Accept invitation
            invitation.accept()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'success': True,
                'message': 'Onboarding completed successfully',
                'user': {
                    'email': user.email,
                    'username': user.username,
                    'full_name': user.full_name,
                    'onboarding_status': user.onboarding_status
                },
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                }
            })

    except OnboardingInvitation.DoesNotExist:
        return Response(
            {'error': 'Invalid invitation token'},
            status=status.HTTP_404_NOT_FOUND
        )


# ============================================================================
# PASSWORD MANAGEMENT
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """
    Request password reset
    POST /api/v1/auth/password-reset/request

    Request:
    {
        "email": "user@example.com"
    }
    """

    email = request.data.get('email', '').strip().lower()

    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Always return success (don't reveal if email exists)
    try:
        user = User.objects.get(email=email)

        # Only send if email is fixed
        if user.is_email_fixed and user.can_receive_emails():
            # Create reset token
            reset_token = PasswordResetToken.objects.create(
                user=user,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

            # Send email
            email_service = EmailService()
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token.token}"

            email_service.send_template_email(
                template='password_reset',
                to_email=email,
                context={
                    'user': user,
                    'reset_url': reset_url,
                    'expires_in_hours': 24
                }
            )

    except User.DoesNotExist:
        pass  # Don't reveal

    return Response({
        'success': True,
        'message': 'If an account exists with this email, a password reset link has been sent'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Reset password with token
    POST /api/v1/auth/password-reset/confirm

    Request:
    {
        "token": "reset_token",
        "new_password": "NewPassword123!"
    }
    """

    token = request.data.get('token')
    new_password = request.data.get('new_password')

    if not token or not new_password:
        return Response(
            {'error': 'Token and new password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validate password strength
    password_validation = validate_password_strength(new_password)
    if not password_validation['valid']:
        return Response(
            {'error': 'Password is too weak', 'details': password_validation['errors']},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        reset_token = PasswordResetToken.objects.get(token=token)

        if not reset_token.is_valid():
            return Response(
                {'error': 'Invalid or expired reset token'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update password
        user = reset_token.user
        user.set_password(new_password)
        user.save()

        # Mark token as used
        reset_token.use()

        return Response({
            'success': True,
            'message': 'Password reset successfully'
        })

    except PasswordResetToken.DoesNotExist:
        return Response(
            {'error': 'Invalid reset token'},
            status=status.HTTP_404_NOT_FOUND
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def validate_password_strength(password):
    """
    Validate password strength

    Returns:
    {
        "valid": bool,
        "errors": []
    }
    """

    errors = []

    if len(password) < 8:
        errors.append('Password must be at least 8 characters long')

    if not re.search(r'[A-Z]', password):
        errors.append('Password must contain at least one uppercase letter')

    if not re.search(r'[a-z]', password):
        errors.append('Password must contain at least one lowercase letter')

    if not re.search(r'[0-9]', password):
        errors.append('Password must contain at least one digit')

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append('Password must contain at least one special character')

    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
