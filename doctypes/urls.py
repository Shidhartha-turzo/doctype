from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'doctypes', views.DoctypeViewSet, basename='doctype')

urlpatterns = [
    path('', include(router.urls)),
    path('schema/<slug:slug>/', views.get_doctype_schema, name='doctype_schema'),
    path('search/', views.global_search, name='global_search'),
    path('search/<slug:slug>/', views.search_documents, name='search_documents'),
    path('schema/openapi/', views.openapi_schema, name='openapi_schema'),

    # Document sharing API
    path('documents/<int:document_id>/share/', views.share_document, name='share_document'),

    # Workflow API
    path('documents/<int:document_id>/workflow/', views.document_workflow_state, name='document_workflow_state'),
    path('documents/<int:document_id>/workflow/transition/', views.document_perform_transition, name='document_perform_transition'),
    path('documents/<int:document_id>/workflow/history/', views.document_workflow_history, name='document_workflow_history'),
    path('documents/<int:document_id>/submit/', views.document_submit, name='document_submit'),
    path('documents/<int:document_id>/cancel/', views.document_cancel, name='document_cancel'),

    # Reports API
    path('reports/', views.report_list, name='report_list'),
    path('reports/<int:report_id>/run/', views.report_run, name='report_run'),

    # Attachments API
    path('documents/<int:document_id>/attachments/', views.document_attachments, name='document_attachments'),
    path('attachments/<int:attachment_id>/', views.attachment_detail, name='attachment_download'),

    # Print API
    path('documents/<int:document_id>/print/', views.print_document, name='print_document'),

    # Advanced search (slug-scoped POST)
    path('<slug:doctype_slug>/search/', views.document_search, name='document_search'),

    # Import / Export API (slug-scoped; literal second segment, so they are not
    # shadowed by the single-segment document_list catch-all below)
    path('<slug:doctype_slug>/export/', views.doctype_export, name='doctype_export'),
    path('<slug:doctype_slug>/import/', views.doctype_import, name='doctype_import'),
    path('<slug:doctype_slug>/import-template/', views.doctype_import_template, name='doctype_import_template'),

    # Dynamic Form Views
    path('<slug:doctype_slug>/', views.document_list, name='document_list'),
    path('<slug:doctype_slug>/create/', views.document_create, name='document_create'),
    path('<slug:doctype_slug>/<int:document_id>/edit/', views.document_edit, name='document_edit'),
    path('<slug:doctype_slug>/<int:document_id>/transition/', views.document_transition, name='document_transition'),
    path('<slug:doctype_slug>/<int:document_id>/delete/', views.document_delete, name='document_delete'),
]
