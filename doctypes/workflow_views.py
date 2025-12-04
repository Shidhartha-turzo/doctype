"""
Workflow API Views

Handles workflow-related API endpoints for state transitions,
permissions, and workflow management.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.core.exceptions import PermissionDenied, ValidationError

from .models import Document, Doctype
from .engine_models import Workflow, WorkflowTransition, WorkflowState
from .workflow_engine import (
    WorkflowEngine, WorkflowException, WorkflowTransitionDenied,
    initialize_workflow, get_available_transitions, execute_transition
)

import logging

logger = logging.getLogger(__name__)


@extend_schema(
    responses={200: dict},
    parameters=[
        OpenApiParameter('document_id', int, description='Document ID', location=OpenApiParameter.PATH)
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initialize_document_workflow(request, document_id):
    """
    Initialize workflow for a document

    Sets the document to the initial workflow state.
    """
    document = get_object_or_404(Document, id=document_id)

    try:
        engine = WorkflowEngine(document, request.user)
        doc_state = engine.initialize_workflow()

        return Response({
            'success': True,
            'message': f'Workflow initialized to state: {doc_state.current_state.name}',
            'workflow': doc_state.workflow.name,
            'current_state': doc_state.current_state.name
        })
    except WorkflowException as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    responses={200: dict},
    parameters=[
        OpenApiParameter('document_id', int, description='Document ID', location=OpenApiParameter.PATH)
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_document_workflow_state(request, document_id):
    """
    Get current workflow state for a document

    Returns current state, available transitions, and workflow history.
    """
    document = get_object_or_404(Document, id=document_id)
    engine = WorkflowEngine(document, request.user)

    current_state = engine.get_current_state()
    if not current_state:
        return Response({
            'has_workflow': False,
            'message': 'Document does not have an active workflow'
        })

    # Get available transitions
    transitions = engine.get_available_transitions()
    transitions_data = []

    for transition in transitions:
        can_transition, reason = engine.can_transition(transition)
        transitions_data.append({
            'id': transition.id,
            'label': transition.label,
            'from_state': transition.from_state.name,
            'to_state': transition.to_state.name,
            'require_comment': transition.require_comment,
            'can_execute': can_transition,
            'reason': reason if not can_transition else None
        })

    # Get workflow history
    history = engine.get_workflow_history()

    return Response({
        'has_workflow': True,
        'workflow': engine.get_workflow().name,
        'current_state': {
            'id': current_state.id,
            'name': current_state.name,
            'color': current_state.color,
            'is_final': current_state.is_final,
            'is_success': current_state.is_success
        },
        'available_transitions': transitions_data,
        'history': history
    })


@extend_schema(
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'transition_id': {'type': 'integer'},
                'comment': {'type': 'string'}
            },
            'required': ['transition_id']
        }
    },
    responses={200: dict},
    parameters=[
        OpenApiParameter('document_id', int, description='Document ID', location=OpenApiParameter.PATH)
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def execute_document_transition(request, document_id):
    """
    Execute a workflow transition on a document

    Transitions the document to a new state if the user has permission.
    Optionally sends email notifications.
    """
    document = get_object_or_404(Document, id=document_id)

    transition_id = request.data.get('transition_id')
    comment = request.data.get('comment', '')
    notify = request.data.get('notify', True)

    if not transition_id:
        return Response({
            'success': False,
            'error': 'transition_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    transition = get_object_or_404(WorkflowTransition, id=transition_id)

    try:
        engine = WorkflowEngine(document, request.user)
        doc_state = engine.execute_transition(transition, comment, notify)

        return Response({
            'success': True,
            'message': f'Document transitioned to state: {doc_state.current_state.name}',
            'previous_state': transition.from_state.name,
            'current_state': doc_state.current_state.name,
            'transitioned_by': request.user.email
        })

    except WorkflowTransitionDenied as e:
        return Response({
            'success': False,
            'error': str(e),
            'type': 'permission_denied'
        }, status=status.HTTP_403_FORBIDDEN)

    except ValidationError as e:
        return Response({
            'success': False,
            'error': str(e),
            'type': 'validation_error'
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Workflow transition error: {str(e)}")
        return Response({
            'success': False,
            'error': 'An error occurred during transition',
            'type': 'server_error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    responses={200: dict},
    parameters=[
        OpenApiParameter('slug', str, description='Doctype slug', location=OpenApiParameter.PATH)
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctype_workflow(request, slug):
    """
    Get workflow configuration for a doctype

    Returns workflow states, transitions, and configuration.
    """
    doctype = get_object_or_404(Doctype, slug=slug, is_active=True)

    try:
        workflow = Workflow.objects.get(doctype=doctype, is_active=True)
    except Workflow.DoesNotExist:
        return Response({
            'has_workflow': False,
            'message': 'No active workflow configured for this doctype'
        })

    # Get states
    states = workflow.states.all()
    states_data = [{
        'id': s.id,
        'name': s.name,
        'description': s.description,
        'is_initial': s.is_initial,
        'is_final': s.is_final,
        'is_success': s.is_success,
        'color': s.color
    } for s in states]

    # Get transitions
    transitions = workflow.transitions.all().select_related('from_state', 'to_state')
    transitions_data = [{
        'id': t.id,
        'label': t.label,
        'from_state': t.from_state.name,
        'to_state': t.to_state.name,
        'require_comment': t.require_comment,
        'allowed_roles': [r.name for r in t.allowed_roles.all()]
    } for t in transitions]

    return Response({
        'has_workflow': True,
        'workflow': {
            'id': workflow.id,
            'name': workflow.name,
            'description': workflow.description
        },
        'states': states_data,
        'transitions': transitions_data
    })


@extend_schema(
    responses={200: dict},
    parameters=[
        OpenApiParameter('document_id', int, description='Document ID', location=OpenApiParameter.PATH)
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_workflow_history(request, document_id):
    """
    Get workflow transition history for a document

    Returns all past transitions with timestamps, users, and comments.
    """
    document = get_object_or_404(Document, id=document_id)
    engine = WorkflowEngine(document)

    history = engine.get_workflow_history()

    return Response({
        'document_id': document.id,
        'history': history
    })


@extend_schema(
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'transition_id': {'type': 'integer'}
            },
            'required': ['transition_id']
        }
    },
    responses={200: dict},
    parameters=[
        OpenApiParameter('document_id', int, description='Document ID', location=OpenApiParameter.PATH)
    ]
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_transition_permission(request, document_id):
    """
    Check if a user can execute a specific transition

    Returns permission status and reason if denied.
    """
    document = get_object_or_404(Document, id=document_id)
    transition_id = request.data.get('transition_id')

    if not transition_id:
        return Response({
            'error': 'transition_id is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    transition = get_object_or_404(WorkflowTransition, id=transition_id)
    engine = WorkflowEngine(document, request.user)

    can_transition, reason = engine.can_transition(transition)

    return Response({
        'can_transition': can_transition,
        'transition': {
            'id': transition.id,
            'label': transition.label,
            'from_state': transition.from_state.name,
            'to_state': transition.to_state.name
        },
        'reason': reason if not can_transition else None
    })
