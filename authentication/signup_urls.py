"""
URL routing for Signup & Onboarding Module
"""

from django.urls import path
from . import signup_views, oauth_mfa_views

urlpatterns = [
    # Self-signup
    path('signup/', signup_views.signup, name='signup'),
    path('verify-email/', signup_views.verify_email, name='verify_email'),
    path('resend-verification/', signup_views.resend_verification_email, name='resend_verification'),

    # Admin onboarding
    path('admin/users/onboard/', signup_views.admin_onboard_user, name='admin_onboard_user'),
    path('complete-onboarding/', signup_views.complete_onboarding, name='complete_onboarding'),

    # Password management
    path('password-reset/request/', signup_views.request_password_reset, name='request_password_reset'),
    path('password-reset/confirm/', signup_views.reset_password, name='reset_password'),

    # OAuth
    path('oauth/<str:provider>/init/', oauth_mfa_views.oauth_init, name='oauth_init'),
    path('oauth/<str:provider>/callback/', oauth_mfa_views.oauth_callback, name='oauth_callback'),

    # MFA - TOTP
    path('mfa/totp/setup/', oauth_mfa_views.mfa_setup_totp, name='mfa_setup_totp'),
    path('mfa/totp/verify/', oauth_mfa_views.mfa_verify_totp, name='mfa_verify_totp'),
    path('mfa/disable/', oauth_mfa_views.mfa_disable, name='mfa_disable'),
    path('mfa/devices/', oauth_mfa_views.mfa_list_devices, name='mfa_list_devices'),
    path('mfa/verify-login/', oauth_mfa_views.mfa_verify_login, name='mfa_verify_login'),
]
