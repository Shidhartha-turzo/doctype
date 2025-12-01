from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'doctypes', views.DoctypeViewSet, basename='doctype')

urlpatterns = [
    path('', include(router.urls)),
    path('schema/<slug:slug>/', views.get_doctype_schema, name='doctype_schema'),
    path('search/<slug:slug>/', views.search_documents, name='search_documents'),
    path('schema/openapi/', views.openapi_schema, name='openapi_schema'),
]
