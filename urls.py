# django_xapi/urls.py
from django.contrib import admin
from django.urls import path, include
from lrs.views import dashboard, statements_view, test_api_view, config_view, web_services_view, moodle_manager_view

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('statements/', statements_view, name='statements'),
    path('test-api/', test_api_view, name='test-api'),
    path('config/', config_view, name='config'),
    path('web-services/', web_services_view, name='web-services'),
    path('moodle-manager/', moodle_manager_view, name='moodle-manager'),
    path('admin/', admin.site.urls),
    path('api/', include('lrs.urls')),
]