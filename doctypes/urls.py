from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import workflow_views
from . import version_views

router = DefaultRouter()
router.register(r'doctypes', views.DoctypeViewSet, basename='doctype')

urlpatterns = [
    path('', include(router.urls)),
    path('schema/<slug:slug>/', views.get_doctype_schema, name='doctype_schema'),
    path('search/<slug:slug>/', views.search_documents, name='search_documents'),
    path('schema/openapi/', views.openapi_schema, name='openapi_schema'),

    # Document sharing API
    path('documents/<int:document_id>/share/', views.share_document, name='share_document'),

    # Workflow API
    path('documents/<int:document_id>/workflow/init/', workflow_views.initialize_document_workflow, name='workflow_init'),
    path('documents/<int:document_id>/workflow/state/', workflow_views.get_document_workflow_state, name='workflow_state'),
    path('documents/<int:document_id>/workflow/transition/', workflow_views.execute_document_transition, name='workflow_transition'),
    path('documents/<int:document_id>/workflow/history/', workflow_views.get_workflow_history, name='workflow_history'),
    path('documents/<int:document_id>/workflow/check/', workflow_views.check_transition_permission, name='workflow_check'),
    path('doctypes/<slug:slug>/workflow/', workflow_views.get_doctype_workflow, name='doctype_workflow'),

    # Version API
    path('documents/<int:document_id>/versions/', version_views.list_versions, name='version_list'),
    path('documents/<int:document_id>/versions/history/', version_views.get_version_history, name='version_history'),
    path('documents/<int:document_id>/versions/compare/', version_views.compare_versions, name='version_compare'),
    path('documents/<int:document_id>/versions/<int:version_number>/', version_views.get_version, name='version_get'),
    path('documents/<int:document_id>/versions/<int:version_number>/restore/', version_views.restore_version, name='version_restore'),

    # Dynamic Form Views
    path('<slug:doctype_slug>/', views.document_list, name='document_list'),
    path('<slug:doctype_slug>/create/', views.document_create, name='document_create'),
    path('<slug:doctype_slug>/<int:document_id>/edit/', views.document_edit, name='document_edit'),
    path('<slug:doctype_slug>/<int:document_id>/delete/', views.document_delete, name='document_delete'),
]
