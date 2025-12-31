"""
Moodle API Service for remote management
"""
import requests
import json
from typing import Dict, List, Optional, Any
from django.conf import settings
from urllib.parse import urljoin


class MoodleAPIService:
    """Service for interacting with Moodle Web Service API"""
    
    def __init__(self, moodle_url: str, token: str = None):
        self.moodle_url = moodle_url.rstrip('/')
        self.token = token
        self.webservice_url = f"{self.moodle_url}/webservice/rest/server.php"
    
    def _make_request(self, function: str, **params) -> Dict[str, Any]:
        """Make a request to Moodle Web Service API"""
        request_params = {
            'wstoken': self.token,
            'wsfunction': function,
            'moodlewsrestformat': 'json'
        }
        request_params.update(params)
        
        try:
            response = requests.post(self.webservice_url, data=request_params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for Moodle API errors
            if isinstance(data, dict) and 'exception' in data:
                raise Exception(f"Moodle API Error: {data.get('message', 'Unknown error')}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test connection to Moodle"""
        try:
            # Try to get site info
            result = self._make_request('core_webservice_get_site_info')
            return True
        except Exception as e:
            # Log the error for debugging
            print(f"Connection test failed: {str(e)}")
            return False
    
    def create_web_service(self, service_name: str, short_name: str = None) -> Dict[str, Any]:
        """Create a new external web service in Moodle"""
        if not short_name:
            short_name = service_name.lower().replace(' ', '_')
        
        params = {
            'services': [{
                'shortname': short_name,
                'name': service_name,
                'enabled': 1,
                'requiredcapabilities': '',
                'downloadfiles': 0,
                'uploadfiles': 0
            }]
        }
        
        return self._make_request('core_external_create_services', **params)
    
    def get_web_services(self) -> List[Dict[str, Any]]:
        """Get all external web services"""
        try:
            result = self._make_request('core_external_get_services')
            return result.get('services', [])
        except Exception as e:
            print(f"Error getting web services: {e}")
            return []
    
    def add_function_to_service(self, service_shortname: str, function_name: str) -> Dict[str, Any]:
        """Add a function to an external service"""
        params = {
            'serviceid': service_shortname,
            'functionname': function_name
        }
        
        return self._make_request('core_external_service_add_functions', **params)
    
    def create_user_token(self, username: str, service_shortname: str) -> Dict[str, Any]:
        """Create a token for a user for a specific service"""
        params = {
            'users': [{
                'username': username,
                'service': service_shortname
            }]
        }
        
        return self._make_request('core_external_generate_tokens', **params)
    
    def get_users(self, criteria: List[Dict] = None) -> List[Dict[str, Any]]:
        """Get users from Moodle"""
        # Moodle requires criteria to be sent as a specific structure
        if criteria is None:
            # Get all users with empty criteria
            params = {
                'criteria[0][key]': '',
                'criteria[0][value]': ''
            }
        else:
            # Use provided criteria
            params = {}
            for i, criterion in enumerate(criteria):
                for key, value in criterion.items():
                    params[f'criteria[{i}][{key}]'] = value
        
        result = self._make_request('core_user_get_users', **params)
        return result.get('users', [])
    
    def create_user(self, username: str, password: str, firstname: str, lastname: str, 
                   email: str) -> Dict[str, Any]:
        """Create a new user in Moodle"""
        params = {
            'users': [{
                'username': username,
                'password': password,
                'firstname': firstname,
                'lastname': lastname,
                'email': email,
                'auth': 'manual'
            }]
        }
        
        return self._make_request('core_user_create_users', **params)
    
    def get_courses(self) -> List[Dict[str, Any]]:
        """Get all courses from Moodle"""
        # Try using core_course_get_courses_field which has fewer restrictions
        params = {
            'field': 'fullname'  # Get basic course info
        }
        
        try:
            result = self._make_request('core_course_get_courses_field', **params)
            # This returns a simple list of courses
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'courses' in result:
                return result['courses']
            else:
                return []
        except Exception as e:
            # Fallback to try the original method
            try:
                result = self._make_request('core_course_get_courses')
                if isinstance(result, dict) and 'courses' in result:
                    return result['courses']
                elif isinstance(result, list):
                    return result
                else:
                    return []
            except Exception as e2:
                # If both fail, return empty list
                print(f"Both course API methods failed: {str(e)}, {str(e2)}")
                return []
    
    def create_course(self, fullname: str, shortname: str, categoryid: int = 1) -> Dict[str, Any]:
        """Create a new course in Moodle"""
        params = {
            'courses': [{
                'fullname': fullname,
                'shortname': shortname,
                'categoryid': categoryid
            }]
        }
        
        return self._make_request('core_course_create_courses', **params)
    
    def enrol_user(self, userid: int, courseid: int, roleid: int = 5) -> Dict[str, Any]:
        """Enrol a user in a course (roleid 5 = student)"""
        params = {
            'enrolments': [{
                'roleid': roleid,
                'userid': userid,
                'courseid': courseid
            }]
        }
        
        return self._make_request('enrol_manual_enrol_users', **params)
    
    def get_site_info(self) -> Dict[str, Any]:
        """Get Moodle site information"""
        return self._make_request('core_webservice_get_site_info')
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get course categories"""
        result = self._make_request('core_course_get_categories')
        return result
    
    def assign_system_role(self, userid: int, roleid: int) -> Dict[str, Any]:
        """Assign a system role to a user"""
        params = {
            'assignments': [{
                'roleid': roleid,
                'userid': userid,
                'contextlevel': 'system'  # System level
            }]
        }
        
        return self._make_request('core_role_assign_roles', **params)


class MoodleManager:
    """High-level manager for Moodle operations"""
    
    def __init__(self, moodle_integration):
        self.integration = moodle_integration
        self.api = MoodleAPIService(
            moodle_url=moodle_integration.moodle_url,
            token=moodle_integration.moodle_token
        )
    
    def setup_xapi_service(self) -> Dict[str, Any]:
        """Set up a complete xAPI web service in Moodle"""
        try:
            # Create the web service
            service_result = self.api.create_web_service(
                service_name="xAPI Bridge Service",
                short_name="xapi_bridge"
            )
            
            # Add required functions for xAPI
            xapi_functions = [
                'core_user_get_users',
                'core_course_get_courses',
                'core_webservice_get_site_info',
                'mod_lti_get_tool_launch_data'
            ]
            
            for function in xapi_functions:
                try:
                    self.api.add_function_to_service('xapi_bridge', function)
                except Exception as e:
                    print(f"Warning: Could not add function {function}: {e}")
            
            return {
                'success': True,
                'message': 'xAPI service created successfully',
                'service': service_result
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to create xAPI service: {str(e)}'
            }
    
    def create_service_user(self, username: str, password: str, email: str) -> Dict[str, Any]:
        """Create a dedicated user for web service access"""
        try:
            # Create user
            user_result = self.api.create_user(
                username=username,
                password=password,
                firstname='API',
                lastname='User',
                email=email
            )
            
            # Assign system role (if needed)
            if user_result and len(user_result) > 0:
                userid = user_result[0].get('id')
                try:
                    self.api.assign_system_role(userid, roleid=1)  # Manager role
                except Exception:
                    pass  # Role assignment might fail, that's okay
            
            return {
                'success': True,
                'message': 'Service user created successfully',
                'user': user_result
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to create service user: {str(e)}'
            }
    
    def get_service_token(self, username: str, service_shortname: str = 'xapi_bridge') -> str:
        """Get or create a token for the service"""
        try:
            token_result = self.api.create_user_token(username, service_shortname)
            if token_result and len(token_result) > 0:
                return token_result[0].get('token')
            return None
        except Exception as e:
            print(f"Error creating token: {e}")
            return None
    
    def get_moodle_status(self) -> Dict[str, Any]:
        """Get comprehensive Moodle status"""
        try:
            site_info = self.api.get_site_info()
            services = self.api.get_web_services()
            users = self.api.get_users()
            courses = self.api.get_courses()
            
            return {
                'connected': True,
                'site_info': site_info,
                'services_count': len(services),
                'users_count': len(users),
                'courses_count': len(courses),
                'services': services[:5]  # First 5 services
            }
            
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }
