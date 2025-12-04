from django.shortcuts import render
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from .serializers import UserSerializer
import random

User = get_user_model()


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing users.
    Only authenticated users can access.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'message': 'API is running'
    })


# ============================================================================
# EASTER EGGS SECTION - Hidden endpoints for fun!
# ============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def konami_code(request):
    """
    Easter egg: Konami code endpoint!
    Visit: /api/konami/ or send header X-Konami-Code: up-up-down-down-left-right-left-right-B-A
    """
    konami = request.META.get('HTTP_X_KONAMI_CODE', '')

    if konami == 'up-up-down-down-left-right-left-right-B-A' or request.path == '/api/konami/':
        messages = [
            {
                'message': 'You found the secret! 30 extra lives granted!',
                'achievement': 'Konami Code Master',
                'bonus': 'Unlimited API calls for the next 5 minutes... just kidding!',
                'secret': 'The real treasure was the doctypes we made along the way',
                'fun_fact': 'This doctype engine was built to solve real-world problems'
            },
            {
                'message': 'Old school gamer detected!',
                'achievement': 'Contra Veteran',
                'bonus': 'Your rate limit has been doubled (not really, but check System Settings)',
                'secret': 'Did you know? This framework can build a CRM in 10 minutes',
                'fun_fact': 'The Konami code was created by Kazuhisa Hashimoto in 1986'
            },
            {
                'message': 'Cheat code activated!',
                'achievement': 'Easter Egg Hunter',
                'bonus': 'You now have admin access to the Matrix (check your permissions first)',
                'secret': 'There are more easter eggs hidden in this codebase...',
                'fun_fact': 'This security system can handle 100 req/min for authenticated users'
            }
        ]

        response_data = random.choice(messages)
        response_data['discovered_by'] = request.user.username if request.user.is_authenticated else 'Anonymous Hero'
        response_data['timestamp'] = 'The time is always NOW'

        return Response(response_data)

    return Response({
        'error': 'Nothing to see here',
        'hint': 'Try sending X-Konami-Code header or visit /api/konami/',
        'clue': 'up-up-down-down-left-right-left-right-B-A'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def teapot(request):
    """
    Easter egg: I'm a teapot (RFC 2324 - Hyper Text Coffee Pot Control Protocol)
    """
    return HttpResponse(
        "I'm a teapot! This Doctype Engine refuses to brew coffee.\n\n"
        "However, it CAN brew up some amazing applications for you!\n"
        "Try building a CRM, HR system, or inventory manager instead.\n\n"
        "Fun fact: HTTP 418 is an actual status code defined in RFC 2324 as an April Fools' joke.",
        status=418,
        content_type='text/plain'
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def developer_quotes(request):
    """
    Easter egg: Random developer wisdom
    """
    quotes = [
        {
            'quote': 'It works on my machine',
            'translation': 'The most dangerous phrase in software development',
            'solution': 'Use Docker, we have it configured!'
        },
        {
            'quote': 'This will only take 5 minutes',
            'translation': 'Famous last words of every developer',
            'reality': 'But with this Doctype Engine, it actually might!'
        },
        {
            'quote': 'We don\'t need to write tests, the code is simple',
            'translation': 'Narrator: The code was not simple',
            'note': 'Good thing we have pytest configured!'
        },
        {
            'quote': 'Let\'s just hardcode it for now',
            'translation': 'There is nothing more permanent than a temporary solution',
            'better_way': 'Use System Settings to configure everything!'
        },
        {
            'quote': 'The database is the problem',
            'translation': 'It\'s never the database',
            'actual_problem': 'Missing index, N+1 queries, or your code'
        },
        {
            'quote': 'We need to add just one more feature',
            'translation': 'Feature creep has entered the chat',
            'wisdom': 'With this engine, adding features is actually easy!'
        },
        {
            'quote': 'Who wrote this code?!',
            'reality': '*checks git blame* oh... it was me',
            'lesson': 'Always write clean code and comments'
        }
    ]

    quote_data = random.choice(quotes)
    quote_data['bonus_tip'] = 'Read REAL_WORLD_APPLICATIONS.md to see how to build production apps'

    return Response(quote_data)


@api_view(['GET'])
@permission_classes([AllowAny])
def matrix(request):
    """
    Easter egg: Take the red pill or blue pill
    """
    choice = request.GET.get('pill', '').lower()

    if choice == 'red':
        return Response({
            'neo': 'You take the red pill...',
            'morpheus': 'Welcome to the real world',
            'reality': {
                'truth': 'This is a Doctype Engine built with Django',
                'features': [
                    'Dynamic schemas without migrations',
                    'Enterprise security out of the box',
                    'Build CRM, HR, Inventory systems in minutes',
                    'Workflow automation',
                    'Complete audit trail',
                    'Rate limiting & brute force protection'
                ],
                'power': 'You can now build any application you imagine',
                'limitation': 'Your imagination (and Python knowledge)'
            },
            'next_step': 'Read QUICKSTART_10MIN.md and build your first app'
        })
    elif choice == 'blue':
        return Response({
            'neo': 'You take the blue pill...',
            'morpheus': 'The story ends, you wake up in your bed',
            'reality': 'Everything seems normal',
            'belief': 'You continue using traditional frameworks',
            'fate': 'Writing migrations, building auth from scratch, no audit logs',
            'ignorance': 'Is bliss... until production breaks',
            'hint': 'Maybe try the red pill? /api/matrix/?pill=red'
        })
    else:
        return Response({
            'morpheus': 'This is your last chance. After this, there is no turning back.',
            'morpheus_continues': 'You take the blue pill - the story ends, you wake up in your bed.',
            'morpheus_concludes': 'You take the red pill - you stay in Wonderland.',
            'neo': 'Which pill do you choose?',
            'choices': {
                'red': '/api/matrix/?pill=red',
                'blue': '/api/matrix/?pill=blue'
            },
            'remember': 'All I\'m offering is the truth. Nothing more.'
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def secret_stats(request):
    """
    Easter egg: Secret stats about the project
    """
    from doctypes.models import Doctype, Document, Module
    from core.security_models import SecurityAuditLog, LoginAttempt, SystemSettings

    try:
        settings = SystemSettings.get_settings()

        return Response({
            'project': 'Doctype Engine',
            'tagline': 'Where Security Meets Flexibility',
            'stats': {
                'modules': Module.objects.count(),
                'doctypes': Doctype.objects.count(),
                'documents': Document.objects.count(),
                'security_events': SecurityAuditLog.objects.count(),
                'login_attempts': LoginAttempt.objects.count(),
            },
            'security': {
                'brute_force_protection': 'Active' if settings.enable_brute_force_protection else 'Disabled',
                'rate_limiting': 'Active' if settings.enable_rate_limiting else 'Disabled',
                'audit_logging': 'Active' if settings.enable_audit_logging else 'Disabled',
                'max_login_attempts': settings.max_login_attempts,
                'rate_limit_authenticated': f'{settings.api_rate_limit_authenticated}/min',
            },
            'power_level': 'OVER 9000!',
            'easter_eggs_found': 'You found one! Keep exploring...',
            'hidden_endpoints': [
                '/api/konami/',
                '/api/teapot/',
                '/api/matrix/',
                '/api/dev-quotes/',
                '/api/secret-stats/',
                '/api/achievement/'
            ]
        })
    except Exception as e:
        return Response({
            'error': 'Stats temporarily unavailable',
            'hint': 'Make sure you\'ve run migrations and initialized System Settings',
            'command': 'python init_security.py'
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def achievement_unlocked(request):
    """
    Easter egg: Achievement system
    """
    achievements = {
        'first_login': {
            'name': 'Welcome Aboard',
            'description': 'Complete your first login',
            'rarity': 'Common',
            'points': 10
        },
        'konami_master': {
            'name': 'Konami Code Master',
            'description': 'Discovered the Konami code easter egg',
            'rarity': 'Rare',
            'points': 50
        },
        'easter_hunter': {
            'name': 'Easter Egg Hunter',
            'description': 'Found all hidden endpoints',
            'rarity': 'Epic',
            'points': 100
        },
        'first_doctype': {
            'name': 'Schema Designer',
            'description': 'Created your first doctype',
            'rarity': 'Uncommon',
            'points': 25
        },
        'security_conscious': {
            'name': 'Security Conscious',
            'description': 'Configured all security settings',
            'rarity': 'Rare',
            'points': 75
        },
        'rapid_developer': {
            'name': 'Rapid Developer',
            'description': 'Built an application in under 10 minutes',
            'rarity': 'Epic',
            'points': 150
        },
        'rtfm': {
            'name': 'RTFM',
            'description': 'Actually read the documentation',
            'rarity': 'Legendary',
            'points': 200
        }
    }

    achievement_name = request.GET.get('unlock', 'first_login')
    achievement = achievements.get(achievement_name, achievements['first_login'])

    return Response({
        'achievement_unlocked': True,
        'achievement': achievement,
        'message': f'Achievement Unlocked: {achievement["name"]}!',
        'total_achievements': len(achievements),
        'all_achievements': list(achievements.keys()),
        'hint': 'Add ?unlock=achievement_name to unlock specific achievements'
    })
