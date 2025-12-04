from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from .models import MagicLink, UserSession
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class MagicLinkRequestSerializer(serializers.Serializer):
    """Serializer for requesting a magic link"""
    email = serializers.EmailField()

    def validate_email(self, value):
        # Check if user with this email exists
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email address")
        return value


class LoginSerializer(serializers.Serializer):
    """Serializer for username/password login"""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")

        attrs['user'] = user
        return attrs


class TokenSerializer(serializers.Serializer):
    """Serializer for token response"""
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    session_key = serializers.CharField()
    user = serializers.SerializerMethodField()

    def get_user(self, obj):
        return {
            'email': obj['user'].email,
            'username': obj['user'].username,
            'full_name': getattr(obj['user'], 'full_name', ''),
        }


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for refreshing tokens"""
    refresh_token = serializers.CharField()


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer for user sessions"""
    class Meta:
        model = UserSession
        fields = [
            'id', 'session_key', 'ip_address', 'user_agent',
            'created_at', 'last_activity', 'expires_at', 'is_active'
        ]
        read_only_fields = fields
