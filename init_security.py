#!/usr/bin/env python
"""
Initialize System Settings with default security configuration.
Run this script once after migrations to set up the security system.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doctype.settings')
django.setup()

from core.security_models import SystemSettings


def initialize_system_settings():
    """Create or update system settings with secure defaults"""
    settings = SystemSettings.get_settings()

    print("System Settings initialized successfully!")
    print("\nDefault Security Configuration:")
    print(f"  - Rate Limiting: {'Enabled' if settings.enable_rate_limiting else 'Disabled'}")
    print(f"  - Brute Force Protection: {'Enabled' if settings.enable_brute_force_protection else 'Disabled'}")
    print(f"  - IP Blacklisting: {'Enabled' if settings.enable_ip_blacklist else 'Disabled'}")
    print(f"  - Security Headers: {'Enabled' if settings.enable_security_headers else 'Disabled'}")
    print(f"  - Audit Logging: {'Enabled' if settings.enable_audit_logging else 'Disabled'}")
    print(f"\nAPI Rate Limits:")
    print(f"  - Anonymous: {settings.api_rate_limit_anonymous} requests/minute")
    print(f"  - Authenticated: {settings.api_rate_limit_authenticated} requests/minute")
    print(f"\nBrute Force Protection:")
    print(f"  - Max Login Attempts: {settings.max_login_attempts}")
    print(f"  - Lockout Duration: {settings.account_lockout_duration} seconds")
    print(f"\nPassword Policy:")
    print(f"  - Min Length: {settings.min_password_length}")
    print(f"  - Require Uppercase: {settings.require_uppercase}")
    print(f"  - Require Lowercase: {settings.require_lowercase}")
    print(f"  - Require Digit: {settings.require_digit}")
    print(f"  - Require Special Char: {settings.require_special_char}")
    print(f"\nYou can modify these settings in the Django admin panel at:")
    print(f"  http://localhost:8000/admin/core/systemsettings/")


if __name__ == '__main__':
    initialize_system_settings()
