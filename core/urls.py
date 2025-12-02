from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('health/', views.health_check, name='health_check'),

    # Easter eggs - hidden endpoints for fun!
    path('konami/', views.konami_code, name='konami'),
    path('teapot/', views.teapot, name='teapot'),
    path('dev-quotes/', views.developer_quotes, name='dev_quotes'),
    path('matrix/', views.matrix, name='matrix'),
    path('secret-stats/', views.secret_stats, name='secret_stats'),
    path('achievement/', views.achievement_unlocked, name='achievement'),
]
