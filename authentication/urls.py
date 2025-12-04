from django.urls import path, include
from . import views

urlpatterns = [
    # Existing authentication endpoints
    path('magic-link/', views.request_magic_link, name='request_magic_link'),
    path('login/', views.login, name='login'),
    path('token/refresh/', views.refresh_token, name='refresh_token'),
    path('sessions/', views.list_sessions, name='list_sessions'),
    path('logout/', views.logout, name='logout'),

    # Signup & Onboarding endpoints
    path('', include('authentication.signup_urls')),
]
