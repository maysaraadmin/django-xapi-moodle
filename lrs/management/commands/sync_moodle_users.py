# lrs/management/commands/sync_moodle_users.py
from django.core.management.base import BaseCommand
from lrs.models import Actor, MoodleIntegration
import requests
from django.utils import timezone

class Command(BaseCommand):
    help = 'Sync users from Moodle to xAPI actors'
    
    def add_arguments(self, parser):
        parser.add_argument('--integration-id', type=int, help='Moodle Integration ID')
    
    def handle(self, *args, **options):
        integration_id = options.get('integration_id')
        
        if integration_id:
            integrations = MoodleIntegration.objects.filter(id=integration_id, is_active=True)
        else:
            integrations = MoodleIntegration.objects.filter(is_active=True)
        
        for integration in integrations:
            self.stdout.write(f"Syncing users from {integration.moodle_site_name}")
            
            # Moodle web service call to get users
            moodle_params = {
                'wstoken': integration.moodle_token,
                'wsfunction': 'core_user_get_users',
                'moodlewsrestformat': 'json',
                'criteria[0][key]': 'all',
                'criteria[0][value]': ''
            }
            
            try:
                response = requests.post(
                    f"{integration.moodle_url}/webservice/rest/server.php",
                    data=moodle_params
                )
                
                if response.status_code == 200:
                    users = response.json().get('users', [])
                    
                    for user in users:
                        # Create or update Actor
                        actor, created = Actor.objects.update_or_create(
                            moodle_user_id=user['id'],
                            defaults={
                                'actor_id': f"mailto:{user['email']}",
                                'name': f"{user['firstname']} {user['lastname']}",
                                'actor_type': 'Agent',
                                'object_type': 'Agent',
                                'mbox': user['email'],
                                'account_name': str(user['id']),
                                'account_homepage': integration.moodle_url,
                            }
                        )
                        
                        if created:
                            self.stdout.write(f"  Created actor: {actor.name}")
                        else:
                            self.stdout.write(f"  Updated actor: {actor.name}")
                    
                    integration.last_sync = timezone.now()
                    integration.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f"Successfully synced {len(users)} users from {integration.moodle_site_name}")
                    )
                else:
                    self.stderr.write(f"Error: {response.status_code} - {response.text}")
                    
            except Exception as e:
                self.stderr.write(f"Error syncing from {integration.moodle_site_name}: {str(e)}")