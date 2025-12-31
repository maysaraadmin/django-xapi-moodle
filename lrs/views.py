# lrs/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from .models import Statement, Actor, Verb, Activity, MoodleIntegration
from .serializers import (
    StatementSerializer, StatementCreateSerializer,
    ActorSerializer, VerbSerializer, ActivitySerializer,
    MoodleIntegrationSerializer
)
import json
from datetime import datetime
from django.utils import timezone
import requests
from django.db import transaction

class StatementViewSet(viewsets.ModelViewSet):
    """Handle xAPI statements"""
    queryset = Statement.objects.all()
    serializer_class = StatementSerializer
    permission_classes = [AllowAny]  # For testing; secure in production
    
    @action(detail=False, methods=['post'])
    def xapi_statements(self, request):
        """Handle xAPI statements POST endpoint"""
        if request.method == 'POST':
            # Check if it's a single statement or multiple
            statements_data = request.data
            
            # Handle single statement
            if isinstance(statements_data, dict):
                statements_data = [statements_data]
            
            created_statements = []
            
            for stmt_data in statements_data:
                serializer = StatementCreateSerializer(data=stmt_data)
                if serializer.is_valid():
                    try:
                        with transaction.atomic():
                            # Create or get Actor
                            actor_data = serializer.validated_data['actor']
                            actor, _ = Actor.objects.get_or_create(
                                actor_id=actor_data.get('mbox', actor_data.get('account_name', 'unknown')),
                                defaults={
                                    'name': actor_data.get('name', 'Unknown'),
                                    'actor_type': 'Agent',
                                    'object_type': actor_data.get('objectType', 'Agent'),
                                    'mbox': actor_data.get('mbox', None),
                                    'account_name': actor_data.get('account', {}).get('name', None) if isinstance(actor_data.get('account'), dict) else None,
                                    'account_homepage': actor_data.get('account', {}).get('homePage', None) if isinstance(actor_data.get('account'), dict) else None,
                                }
                            )
                            
                            # Create or get Verb
                            verb_data = serializer.validated_data['verb']
                            verb, _ = Verb.objects.get_or_create(
                                verb_id=verb_data['id'],
                                defaults={'display': verb_data.get('display', {'en-US': verb_data['id'].split('/')[-1]})}
                            )
                            
                            # Handle Object (could be Activity or something else)
                            object_data = serializer.validated_data['object']
                            activity = None
                            
                            if object_data.get('objectType') == 'Activity':
                                activity, _ = Activity.objects.get_or_create(
                                    activity_id=object_data['id'],
                                    defaults={
                                        'definition': object_data.get('definition', {}),
                                        'object_type': 'Activity'
                                    }
                                )
                            
                            # Create Statement
                            statement = Statement.objects.create(
                                actor=actor,
                                verb=verb,
                                activity=activity,
                                object=object_data,
                                result=serializer.validated_data.get('result'),
                                context=serializer.validated_data.get('context'),
                                timestamp=serializer.validated_data.get('timestamp', timezone.now()),
                                authority=serializer.validated_data.get('authority'),
                                version='1.0.0'
                            )
                            
                            created_statements.append(statement.statement_id)
                            
                    except Exception as e:
                        return Response(
                            {'error': f'Failed to create statement: {str(e)}'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'message': f'Successfully created {len(created_statements)} statement(s)',
                'statement_ids': created_statements
            }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def get_statements(self, request):
        """Get statements with filters"""
        queryset = self.get_queryset()
        
        # Apply filters
        actor_id = request.query_params.get('actor')
        verb_id = request.query_params.get('verb')
        activity_id = request.query_params.get('activity')
        since = request.query_params.get('since')
        
        if actor_id:
            queryset = queryset.filter(actor__actor_id=actor_id)
        if verb_id:
            queryset = queryset.filter(verb__verb_id=verb_id)
        if activity_id:
            queryset = queryset.filter(activity__activity_id=activity_id)
        if since:
            try:
                since_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
                queryset = queryset.filter(timestamp__gte=since_date)
            except ValueError:
                pass
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class MoodleXAPIView(APIView):
    """Handle Moodle-specific xAPI integration"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Receive events from Moodle"""
        data = request.data
        
        # Expected Moodle data format
        event_type = data.get('event_type')
        user_id = data.get('user_id')
        course_id = data.get('course_id')
        activity_id = data.get('activity_id')
        activity_type = data.get('activity_type')
        grade = data.get('grade')
        max_grade = data.get('max_grade')
        
        # Map Moodle event to xAPI verb
        verb_map = {
            'course_viewed': 'http://adlnet.gov/expapi/verbs/experienced',
            'course_completed': 'http://adlnet.gov/expapi/verbs/completed',
            'quiz_attempt_submitted': 'http://adlnet.gov/expapi/verbs/attempted',
            'quiz_attempt_reviewed': 'http://adlnet.gov/expapi/verbs/reviewed',
            'assignment_submitted': 'http://adlnet.gov/expapi/verbs/completed',
            'forum_post_created': 'http://adlnet.gov/expapi/verbs/commented',
            'scorm_launched': 'http://adlnet.gov/expapi/verbs/launched',
            'scorm_completed': 'http://adlnet.gov/expapi/verbs/completed',
        }
        
        verb_id = verb_map.get(event_type, 'http://adlnet.gov/expapi/verbs/experienced')
        
        # Create xAPI statement from Moodle data
        statement = {
            'actor': {
                'objectType': 'Agent',
                'account': {
                    'homePage': f"{data.get('site_url', 'http://moodle.local')}",
                    'name': f"user_{user_id}"
                },
                'name': data.get('user_name', 'Unknown User')
            },
            'verb': {
                'id': verb_id,
                'display': {'en-US': verb_id.split('/')[-1]}
            },
            'object': {
                'objectType': 'Activity',
                'id': f"{data.get('site_url', 'http://moodle.local')}/mod/{activity_type}/view.php?id={activity_id}",
                'definition': {
                    'name': {'en-US': data.get('activity_name', 'Unknown Activity')},
                    'description': {'en-US': f"Course: {data.get('course_name', 'Unknown Course')}"},
                    'type': f"http://adlnet.gov/expapi/activities/{activity_type}"
                }
            },
            'context': {
                'contextActivities': {
                    'parent': [{
                        'id': f"{data.get('site_url', 'http://moodle.local')}/course/view.php?id={course_id}",
                        'objectType': 'Activity',
                        'definition': {
                            'name': {'en-US': data.get('course_name', 'Unknown Course')}
                        }
                    }]
                }
            }
        }
        
        # Add result if grade exists
        if grade is not None:
            statement['result'] = {
                'score': {
                    'scaled': float(grade) / float(max_grade) if max_grade else 0,
                    'raw': float(grade),
                    'min': 0,
                    'max': float(max_grade) if max_grade else 100
                },
                'completion': event_type.endswith('_completed'),
                'success': float(grade) >= (float(max_grade) * 0.7 if max_grade else 70)
            }
        
        # Save to LRS
        statement_view = StatementViewSet()
        statement_view.request = request
        statement_view.format_kwarg = None
        response = statement_view.xapi_statements(request)
        
        return Response({
            'status': 'success',
            'moodle_event': event_type,
            'xapi_statement': statement,
            'lrs_response': response.data
        })

class ActorViewSet(viewsets.ModelViewSet):
    """Handle xAPI actors"""
    queryset = Actor.objects.all()
    serializer_class = ActorSerializer
    permission_classes = [AllowAny]

class VerbViewSet(viewsets.ModelViewSet):
    """Handle xAPI verbs"""
    queryset = Verb.objects.all()
    serializer_class = VerbSerializer
    permission_classes = [AllowAny]

class ActivityViewSet(viewsets.ModelViewSet):
    """Handle xAPI activities"""
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    permission_classes = [AllowAny]

class MoodleIntegrationViewSet(viewsets.ModelViewSet):
    """Handle Moodle integration settings"""
    queryset = MoodleIntegration.objects.all()
    serializer_class = MoodleIntegrationSerializer
    permission_classes = [AllowAny]

# UI Views
def dashboard(request):
    """Dashboard view"""
    # Get LRS endpoint info
    lrs_endpoint = request.build_absolute_uri('/api/moodle/event')
    
    # Get real statistics from database
    from .models import Statement, Actor, Activity, Verb, MoodleIntegration
    
    # Calculate real statistics
    total_statements = Statement.objects.count()
    total_actors = Actor.objects.count()
    total_activities = Activity.objects.count()
    total_verbs = Verb.objects.count()
    moodle_integrations = MoodleIntegration.objects.filter(is_active=True)
    
    # Get recent statements
    recent_statements = Statement.objects.select_related('actor', 'verb', 'activity').order_by('-timestamp')[:5]
    
    # Prepare recent statements data
    recent_statements_data = []
    for stmt in recent_statements:
        recent_statements_data.append({
            'id': stmt.id,
            'actor_name': stmt.actor.name if stmt.actor else 'Unknown',
            'actor_email': stmt.actor.mbox if stmt.actor else '',
            'verb_display': stmt.verb.display.get('en-US', stmt.verb.verb_id.split('/')[-1]) if stmt.verb else 'Unknown',
            'activity_name': stmt.activity.definition.get('name', {}).get('en-US', 'Unknown Activity') if stmt.activity and stmt.activity.definition else 'Unknown Activity',
            'activity_type': stmt.activity.definition.get('type', 'Unknown') if stmt.activity and stmt.activity.definition else 'Unknown',
            'timestamp': stmt.timestamp.isoformat() if stmt.timestamp else None,
            'result_score': stmt.result.get('score', {}).get('raw') if stmt.result else None,
            'result_completion': stmt.result.get('completion', False) if stmt.result else False
        })
    
    # Get auth token info (for development - show how to configure)
    auth_info = {
        'endpoint': lrs_endpoint,
        'note': 'Configure in Moodle plugin settings',
        'moodle_settings': {
            'lrs_endpoint': lrs_endpoint,
            'lrs_auth_token': 'Bearer token (or leave empty for AllowAny)'
        },
        'moodle_integrations': [
            {
                'name': integration.moodle_site_name,
                'url': integration.moodle_url,
                'last_sync': integration.last_sync.isoformat() if integration.last_sync else None
            }
            for integration in moodle_integrations
        ]
    }
    
    import json
    context = {
        'lrs_info': json.dumps(auth_info),
        'stats': {
            'total_statements': total_statements,
            'total_actors': total_actors,
            'total_activities': total_activities,
            'total_verbs': total_verbs
        },
        'recent_statements': recent_statements_data
    }
    
    return render(request, 'dashboard.html', context)

def statements_view(request):
    """Statements list view"""
    return render(request, 'statements.html')

def test_api_view(request):
    """API testing view"""
    return render(request, 'test_api.html')

def config_view(request):
    """LRS configuration view for Moodle setup"""
    lrs_endpoint = request.build_absolute_uri('/api/moodle/event')
    return render(request, 'config.html', {'lrs_endpoint': lrs_endpoint})

def web_services_view(request):
    """Web services management view"""
    return render(request, 'web_services.html')

def moodle_manager_view(request):
    """Moodle management view"""
    return render(request, 'moodle_manager.html')

# API Views for Moodle Manager
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .models import MoodleIntegration
from .serializers import MoodleIntegrationSerializer

@api_view(['GET'])
@permission_classes([AllowAny])
def moodle_integrations_api(request):
    """API endpoint to get all Moodle integrations"""
    try:
        integrations = MoodleIntegration.objects.all()
        serializer = MoodleIntegrationSerializer(integrations, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def create_moodle_integration_api(request):
    """API endpoint to create a new Moodle integration"""
    try:
        serializer = MoodleIntegrationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
@permission_classes([AllowAny])
def update_moodle_integration_api(request, pk):
    """API endpoint to update a Moodle integration"""
    try:
        integration = MoodleIntegration.objects.get(pk=pk)
        serializer = MoodleIntegrationSerializer(integration, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except MoodleIntegration.DoesNotExist:
        return Response({'error': 'Integration not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_moodle_integration_api(request, pk):
    """API endpoint to delete a Moodle integration"""
    try:
        integration = MoodleIntegration.objects.get(pk=pk)
        integration.delete()
        return Response({'message': 'Integration deleted successfully'})
    except MoodleIntegration.DoesNotExist:
        return Response({'error': 'Integration not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def test_moodle_connection_api(request):
    """API endpoint to test Moodle connection"""
    try:
        moodle_url = request.data.get('moodle_url')
        token = request.data.get('token')
        
        if not moodle_url:
            return Response({
                'connected': False,
                'message': 'Moodle URL is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Use MoodleAPIService to test connection
        from .services.moodle_api import MoodleAPIService
        api = MoodleAPIService(moodle_url, token)
        
        if api.test_connection():
            try:
                site_info = api.get_site_info()
                return Response({
                    'connected': True,
                    'message': 'Successfully connected to Moodle',
                    'site_info': site_info
                })
            except Exception as e:
                return Response({
                    'connected': True,
                    'message': 'Connected to Moodle but failed to get site info',
                    'error': str(e)
                })
        else:
            return Response({
                'connected': False,
                'message': 'Failed to connect to Moodle. Please check URL and token.',
                'debug_info': {
                    'moodle_url': moodle_url,
                    'token_provided': bool(token),
                    'webservice_url': f"{moodle_url.rstrip('/')}/webservice/rest/server.php"
                }
            })
            
    except Exception as e:
        return Response({
            'connected': False,
            'message': f'Connection test failed: {str(e)}',
            'debug_info': {
                'moodle_url': request.data.get('moodle_url'),
                'token_provided': bool(request.data.get('token'))
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def get_moodle_data_api(request):
    """API endpoint to get Moodle data (services, users, courses)"""
    try:
        moodle_url = request.data.get('moodle_url')
        token = request.data.get('token')
        
        if not moodle_url:
            return Response({'error': 'Moodle URL is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Use MoodleAPIService to get real data
        from .services.moodle_api import MoodleAPIService, MoodleManager
        api = MoodleAPIService(moodle_url, token)
        
        # Get real Moodle data with individual error handling
        services = []
        users = []
        courses = []
        errors = []
        
        try:
            services = api.get_web_services()
        except Exception as e:
            errors.append(f"Failed to get web services: {str(e)}")
        
        try:
            users = api.get_users()
        except Exception as e:
            errors.append(f"Failed to get users: {str(e)}")
        
        try:
            courses = api.get_courses()
        except Exception as e:
            errors.append(f"Failed to get courses: {str(e)}")
        
        # Return partial data with errors if some calls failed
        response_data = {
            'services': services,
            'users': users,
            'courses': courses,
            'stats': {
                'users_count': len(users),
                'courses_count': len(courses),
                'services_count': len(services)
            }
        }
        
        if errors:
            response_data['errors'] = errors
            response_data['message'] = 'Some data could not be retrieved'
        
        return Response(response_data)
        
    except Exception as e:
        return Response({
            'error': f'Failed to load Moodle data: {str(e)}',
            'debug_info': {
                'moodle_url': request.data.get('moodle_url'),
                'token_provided': bool(request.data.get('token'))
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def create_moodle_web_service_api(request):
    """API endpoint to create a web service in Moodle"""
    try:
        moodle_url = request.data.get('moodle_url')
        token = request.data.get('token')
        service_name = request.data.get('service_name')
        short_name = request.data.get('short_name')
        
        if not all([moodle_url, service_name, short_name]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Use MoodleAPIService to create web service
        from .services.moodle_api import MoodleAPIService
        api = MoodleAPIService(moodle_url, token)
        
        result = api.create_web_service(service_name, short_name)
        
        if 'error' in result:
            return Response({'error': result['message']}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': 'Web service created successfully',
            'service': result
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to create web service: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def create_moodle_user_api(request):
    """API endpoint to create a user in Moodle"""
    try:
        moodle_url = request.data.get('moodle_url')
        token = request.data.get('token')
        username = request.data.get('username')
        password = request.data.get('password')
        email = request.data.get('email')
        firstname = request.data.get('firstname', 'API')
        lastname = request.data.get('lastname', 'User')
        
        if not all([moodle_url, username, password, email]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Use MoodleAPIService to create user
        from .services.moodle_api import MoodleAPIService
        api = MoodleAPIService(moodle_url, token)
        
        result = api.create_user(username, password, firstname, lastname, email)
        
        if 'error' in result:
            return Response({'error': result['message']}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': 'User created successfully',
            'user': result
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to create user: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# LRS Integration API Endpoints
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
@require_http_methods(["POST"])
@never_cache
def debug_moodle_api_request(request):
    """Debug endpoint to see what's being sent to Moodle"""
    try:
        # Disable session middleware for this request
        request._dont_enforce_csrf_checks = True
            
        moodle_url = request.data.get('moodle_url')
        token = request.data.get('token')
        
        if not moodle_url:
            return Response({'error': 'Moodle URL is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        from .services.moodle_api import MoodleAPIService
        api = MoodleAPIService(moodle_url, token)
        
        # Debug the exact request being made
        debug_info = {
            'moodle_url': moodle_url,
            'webservice_url': api.webservice_url,
            'token_provided': bool(token),
            'token_length': len(token) if token else 0,
            'request_params': {
                'wstoken': token[:10] + '...' if token else None,
                'wsfunction': 'core_user_get_users',
                'moodlewsrestformat': 'json'
            }
        }
        
        # Try to make the actual request to see the full error
        try:
            # Manually construct the request to see what's happening
            import requests
            request_params = {
                'wstoken': token,
                'wsfunction': 'core_user_get_users',
                'moodlewsrestformat': 'json'
            }
            
            response = requests.post(api.webservice_url, data=request_params, timeout=30)
            debug_info['http_status'] = response.status_code
            debug_info['response_text'] = response.text[:500]  # First 500 chars
            
            try:
                response_json = response.json()
                debug_info['response_json'] = response_json
            except:
                debug_info['json_parse_error'] = 'Failed to parse JSON'
                
        except Exception as e:
            debug_info['request_error'] = str(e)
        
        return Response({
            'success': True,
            'message': 'Debug information collected',
            'debug_info': debug_info
        })
        
    except Exception as e:
        return Response({
            'error': f'Debug endpoint failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
@require_http_methods(["POST"])
@never_cache
def simple_test_api(request):
    """Simple test endpoint to verify server is working"""
    try:
        # Disable session middleware for this request
        request._dont_enforce_csrf_checks = True
        
        return Response({
            'success': True,
            'message': 'Simple test works',
            'method': request.method,
            'data': dict(request.data)
        })
    except Exception as e:
        return Response({
            'error': f'Simple test failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
@require_http_methods(["POST"])
@never_cache
def test_sync_api(request):
    """Test endpoint to debug sync issues"""
    try:
        # Disable session middleware for this request
        request._dont_enforce_csrf_checks = True
            
        return Response({
            'success': True,
            'message': 'Test endpoint works',
            'data_received': {
                'moodle_url': request.data.get('moodle_url'),
                'token_provided': bool(request.data.get('token')),
                'method': request.method,
                'content_type': request.content_type
            }
        })
    except Exception as e:
        return Response({
            'error': f'Test endpoint error: {str(e)}',
            'traceback': str(e.__traceback__) if hasattr(e, '__traceback__') else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
@require_http_methods(["POST"])
@never_cache
def sync_moodle_users_api(request):
    """Sync Moodle users to LRS"""
    try:
        # Disable session middleware for this request
        request._dont_enforce_csrf_checks = True
            
        moodle_url = request.data.get('moodle_url')
        token = request.data.get('token')
        
        if not moodle_url:
            return Response({'error': 'Moodle URL is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        from .services.moodle_api import MoodleAPIService
        api = MoodleAPIService(moodle_url, token)
        
        # Get users from Moodle
        try:
            users = api.get_users()
        except Exception as e:
            return Response({
                'error': f'Failed to get users from Moodle: {str(e)}',
                'debug_info': {
                    'moodle_url': moodle_url,
                    'token_provided': bool(token)
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        synced_count = 0
        
        # Import users to LRS
        from .models import Actor
        for user in users:
            if user.get('email'):
                try:
                    actor, created = Actor.objects.get_or_create(
                        actor_id=user['email'],
                        defaults={
                            'name': f"{user.get('firstname', '')} {user.get('lastname', '')}".strip(),
                            'mbox': user['email'],
                            'actor_type': 'Agent',
                            'object_type': 'Agent',
                            'moodle_user_id': user.get('id')
                        }
                    )
                    if created:
                        synced_count += 1
                except Exception as e:
                    return Response({
                        'error': f'Failed to create actor for user {user.get("email", "unknown")}: {str(e)}',
                        'user_data': user
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': True,
            'message': f'Successfully synced {synced_count} users to LRS',
            'synced_count': synced_count,
            'total_users': len(users)
        })
        
    except Exception as e:
        return Response({
            'error': f'Unexpected error in sync_moodle_users_api: {str(e)}',
            'debug_info': {
                'moodle_url': request.data.get('moodle_url'),
                'token_provided': bool(request.data.get('token'))
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
@require_http_methods(["POST"])
@never_cache
def sync_moodle_courses_api(request):
    """Sync Moodle courses to LRS"""
    try:
        # Disable session middleware for this request
        request._dont_enforce_csrf_checks = True
            
        moodle_url = request.data.get('moodle_url')
        token = request.data.get('token')
        
        if not moodle_url:
            return Response({'error': 'Moodle URL is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        from .services.moodle_api import MoodleAPIService
        api = MoodleAPIService(moodle_url, token)
        
        # Get courses from Moodle
        courses = api.get_courses()
        synced_count = 0
        
        # Import courses to LRS
        from .models import Activity
        for course in courses:
            if course.get('id'):
                activity, created = Activity.objects.get_or_create(
                    activity_id=f"{moodle_url}/course/view.php?id={course['id']}",
                    defaults={
                        'definition': {
                            'name': {'en-US': course.get('fullname', 'Unknown Course')},
                            'description': {'en-US': course.get('summary', '')},
                            'type': 'http://adlnet.gov/expapi/activities/course'
                        },
                        'object_type': 'Activity',
                        'moodle_course_id': course.get('id')
                    }
                )
                if created:
                    synced_count += 1
        
        return Response({
            'success': True,
            'message': f'Successfully synced {synced_count} courses to LRS',
            'synced_count': synced_count,
            'total_courses': len(courses)
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to sync courses: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
@require_http_methods(["POST"])
@never_cache
def sync_moodle_activities_api(request):
    """Sync Moodle activities to LRS"""
    try:
        # Disable session middleware for this request
        request._dont_enforce_csrf_checks = True
            
        moodle_url = request.data.get('moodle_url')
        token = request.data.get('token')
        
        if not moodle_url:
            return Response({'error': 'Moodle URL is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        from .services.moodle_api import MoodleAPIService
        api = MoodleAPIService(moodle_url, token)
        
        # Get courses and activities from Moodle
        courses = api.get_courses()
        synced_count = 0
        
        # Create sample xAPI statements for activities
        from .models import Statement, Actor, Verb, Activity
        from django.utils import timezone
        import uuid
        
        # Create or get default verb
        verb, _ = Verb.objects.get_or_create(
            verb_id='http://adlnet.gov/expapi/verbs/experienced',
            defaults={'display': {'en-US': 'experienced'}}
        )
        
        # Create or get default actor for system
        actor, _ = Actor.objects.get_or_create(
            actor_id='system@moodle.lrs',
            defaults={
                'name': 'Moodle System',
                'actor_type': 'Agent',
                'object_type': 'Agent'
            }
        )
        
        for course in courses:
            if course.get('id'):
                activity, created = Activity.objects.get_or_create(
                    activity_id=f"{moodle_url}/course/view.php?id={course['id']}",
                    defaults={
                        'definition': {
                            'name': {'en-US': course.get('fullname', 'Unknown Course')},
                            'description': {'en-US': course.get('summary', '')},
                            'type': 'http://adlnet.gov/expapi/activities/course'
                        },
                        'object_type': 'Activity',
                        'moodle_course_id': course.get('id')
                    }
                )
                
                # Create xAPI statement for course access
                if created:
                    Statement.objects.get_or_create(
                        statement_id=uuid.uuid4(),
                        defaults={
                            'actor': actor,
                            'verb': verb,
                            'activity': activity,
                            'object': {
                                'objectType': 'Activity',
                                'id': activity.activity_id,
                                'definition': activity.definition
                            },
                            'timestamp': timezone.now(),
                            'stored': timezone.now(),
                            'authority': {'objectType': 'Agent', 'name': 'Moodle System', 'mbox': 'system@moodle.lrs'},
                            'version': '1.0.0',
                            'is_valid': True
                        }
                    )
                    synced_count += 1
        
        return Response({
            'success': True,
            'message': f'successfully synced {synced_count} activities to LRS',
            'synced_count': synced_count,
            'total_activities': len(courses)
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to sync activities: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def generate_xapi_reports_api(request):
    """Generate xAPI reports from Moodle data"""
    try:
        moodle_url = request.data.get('moodle_url')
        token = request.data.get('token')
        
        if not moodle_url:
            return Response({'error': 'Moodle URL is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        from .models import Statement, Actor, Verb, Activity
        from datetime import datetime, timedelta
        import json
        from django.http import HttpResponse
        
        # Get recent statements for reporting
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # Last 30 days
        
        statements = Statement.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).select_related('actor', 'verb', 'activity').order_by('-timestamp')
        
        # Generate report data
        report_data = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': 30
            },
            'summary': {
                'total_statements': statements.count(),
                'unique_actors': statements.values('actor').distinct().count(),
                'unique_activities': statements.values('activity').distinct().count(),
                'unique_verbs': statements.values('verb').distinct().count()
            },
            'statements': []
        }
        
        for stmt in statements[:100]:  # Limit to 100 statements
            report_data['statements'].append({
                'timestamp': stmt.timestamp.isoformat(),
                'actor': {
                    'name': stmt.actor.name,
                    'mbox': stmt.actor.mbox
                },
                'verb': {
                    'id': stmt.verb.verb_id,
                    'display': stmt.verb.display
                },
                'activity': {
                    'id': stmt.activity.activity_id,
                    'definition': stmt.activity.definition
                },
                'result': stmt.result
            })
        
        # Store report data in session for download
        if hasattr(request, 'session'):
            request.session['xapi_report_data'] = report_data
            request.session.modified = True
        
        return Response({
            'success': True,
            'message': f'Generated xAPI report with {len(report_data["statements"])} statements',
            'reports_count': 1,
            'report_data': report_data,
            'download_url': '/api/download-xapi-report/'
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to generate reports: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def download_xapi_report(request):
    """Download xAPI report as JSON file"""
    try:
        # Get report data from session or generate fresh
        from .models import Statement, Actor, Verb, Activity
        from datetime import datetime, timedelta
        import json
        from django.http import HttpResponse
        
        if hasattr(request, 'session') and 'xapi_report_data' in request.session:
            report_data = request.session['xapi_report_data']
        else:
            # Generate fresh report if not in session
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            statements = Statement.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date
            ).select_related('actor', 'verb', 'activity').order_by('-timestamp')
            
            report_data = {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': 30
                },
                'summary': {
                    'total_statements': statements.count(),
                    'unique_actors': statements.values('actor').distinct().count(),
                    'unique_activities': statements.values('activity').distinct().count(),
                    'unique_verbs': statements.values('verb').distinct().count()
                },
                'statements': []
            }
            
            for stmt in statements[:100]:
                report_data['statements'].append({
                    'timestamp': stmt.timestamp.isoformat(),
                    'actor': {
                        'name': stmt.actor.name,
                        'mbox': stmt.actor.mbox
                    },
                    'verb': {
                        'id': stmt.verb.verb_id,
                        'display': stmt.verb.display
                    },
                    'activity': {
                        'id': stmt.activity.activity_id,
                        'definition': stmt.activity.definition
                    },
                    'result': stmt.result
                })
        
        # Create JSON response
        report_json = json.dumps(report_data, indent=2, default=str)
        
        # Create HTTP response with file download headers
        response = HttpResponse(report_json, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="xapi_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'
        response['Content-Length'] = len(report_json)
        
        return response
        
    except Exception as e:
        return Response({
            'error': f'Failed to download report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)