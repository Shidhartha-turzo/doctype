from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""

    class Meta:
        model = User
        fields = ['email', 'username', 'full_name', 'first_name', 'last_name', 'created_at', 'is_email_fixed', 'email_verified']
        read_only_fields = ['email', 'created_at']
