#!/usr/bin/env python
"""
Test script to verify sync API endpoints work without session corruption
"""
import os
import sys
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import RequestFactory
from lrs.views import simple_test_api, sync_moodle_users_api
from rest_framework import status

def test_simple_endpoint():
    """Test the simple test endpoint"""
    print("Testing simple_test_api...")
    
    factory = RequestFactory()
    request = factory.post('/api/simple-test/', {'test': 'data'})
    
    try:
        response = simple_test_api(request)
        print(f"✅ simple_test_api: {response.status_code}")
        print(f"   Response: {response.data}")
        return True
    except Exception as e:
        print(f"❌ simple_test_api failed: {str(e)}")
        return False

def test_sync_users_endpoint():
    """Test the sync users endpoint"""
    print("Testing sync_moodle_users_api...")
    
    factory = RequestFactory()
    request = factory.post('/api/sync-moodle-users/', {
        'moodle_url': 'http://127.0.0.1/robot/',
        'token': 'fe64053286a57886c594a89a2ab2cd95'
    })
    
    try:
        response = sync_moodle_users_api(request)
        print(f"✅ sync_moodle_users_api: {response.status_code}")
        print(f"   Response: {response.data}")
        return True
    except Exception as e:
        print(f"❌ sync_moodle_users_api failed: {str(e)}")
        return False

if __name__ == '__main__':
    print("🧪 Testing Sync API Endpoints")
    print("=" * 50)
    
    # Test simple endpoint first
    simple_test_passed = test_simple_endpoint()
    print()
    
    # Test sync users endpoint
    sync_test_passed = test_sync_users_endpoint()
    print()
    
    print("=" * 50)
    if simple_test_passed and sync_test_passed:
        print("🎉 All tests passed! Session corruption issue is resolved.")
    else:
        print("❌ Some tests failed. Check the error messages above.")
