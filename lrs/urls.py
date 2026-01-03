# lrs/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router for the ViewSets
router = DefaultRouter()
router.register(r'statements', views.StatementViewSet)
router.register(r'actors', views.ActorViewSet)
router.register(r'verbs', views.VerbViewSet)
router.register(r'activities', views.ActivityViewSet)
# router.register(r'moodle-integrations', views.MoodleIntegrationViewSet)  # Commented out to avoid conflicts

urlpatterns = [
    # API endpoints
    path('', views.StatementViewSet.as_view({'get': 'list', 'post': 'create'}), name='statement-list'),
    path('statements/', views.StatementViewSet.as_view({'get': 'list', 'post': 'create'}), name='statement-list'),
    path('statements/<int:pk>/', views.StatementViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='statement-detail'),
    
    # Moodle event endpoint
    path('moodle/event/', views.MoodleXAPIView.as_view(), name='moodle-xapi'),
    path('moodle/event', views.MoodleXAPIView.as_view(), name='moodle-xapi-no-slash'),
    
    # ViewSets
    path('', include(router.urls)),
    
    # Direct API endpoints for Moodle Manager
    path('moodle-integrations/', views.moodle_integrations_api, name='moodle-integrations'),
    path('moodle-integrations/create/', views.create_moodle_integration_api, name='create-moodle-integration'),
    path('moodle-integrations/<int:pk>/update/', views.update_moodle_integration_api, name='update-moodle-integration'),
    path('moodle-integrations/<int:pk>/delete/', views.delete_moodle_integration_api, name='delete-moodle-integration'),
    path('test-moodle-connection/', views.test_moodle_connection_api, name='test-moodle-connection'),
    path('moodle-data/', views.get_moodle_data_api, name='get-moodle-data'),
    path('create-moodle-web-service/', views.create_moodle_web_service_api, name='create-moodle-web-service'),
    path('create-moodle-user/', views.create_moodle_user_api, name='create-moodle-user'),
    
    # LRS Integration endpoints
    path('debug-moodle-api/', views.debug_moodle_api_request, name='debug-moodle-api'),
    path('simple-test/', views.simple_test_api, name='simple-test'),
    path('test-sync/', views.test_sync_api, name='test-sync'),
    path('sync-moodle-users/', views.sync_moodle_users_api, name='sync-moodle-users'),
    path('sync-moodle-courses/', views.sync_moodle_courses_api, name='sync-moodle-courses'),
    path('sync-moodle-activities/', views.sync_moodle_activities_api, name='sync-moodle-activities'),
    path('generate-xapi-reports/', views.generate_xapi_reports_api, name='generate-xapi-reports'),
    path('download-xapi-report/', views.download_xapi_report, name='download-xapi-report'),
    path('statements/get', views.StatementViewSet.as_view({'get': 'get_statements'}), name='get-statements'),
    
    # v1 API endpoints for external compatibility
    path('v1/models/', views.v1_models_api, name='v1-models'),
]