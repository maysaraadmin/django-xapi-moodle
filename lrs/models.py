# lrs/models.py
from django.db import models
from django.contrib.auth.models import User
import json
import uuid
from django.core.serializers.json import DjangoJSONEncoder

class Actor(models.Model):
    """xAPI Actor model"""
    ACTOR_TYPES = (
        ('Agent', 'Agent'),
        ('Group', 'Group'),
    )
    
    actor_id = models.CharField(max_length=500, unique=True)
    name = models.CharField(max_length=255)
    actor_type = models.CharField(max_length=20, choices=ACTOR_TYPES)
    object_type = models.CharField(max_length=50, default='Agent')
    mbox = models.EmailField(null=True, blank=True)
    mbox_sha1sum = models.CharField(max_length=200, null=True, blank=True)
    openid = models.URLField(null=True, blank=True)
    account_homepage = models.URLField(null=True, blank=True)
    account_name = models.CharField(max_length=255, null=True, blank=True)
    moodle_user_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.actor_type})"

class Verb(models.Model):
    """xAPI Verb model"""
    verb_id = models.URLField()
    display = models.JSONField(default=dict)  # {"en-US": "verb"}
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.verb_id.split('/')[-1]

class Activity(models.Model):
    """xAPI Activity model"""
    activity_id = models.URLField(unique=True)
    definition = models.JSONField(default=dict)
    object_type = models.CharField(max_length=50, default='Activity')
    moodle_activity_id = models.IntegerField(null=True, blank=True)
    moodle_course_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.activity_id

class Statement(models.Model):
    """xAPI Statement model"""
    statement_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE, related_name='statements')
    verb = models.ForeignKey(Verb, on_delete=models.CASCADE, related_name='statements')
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='statements', null=True)
    object = models.JSONField(default=dict)  # Can be Activity, Agent, etc.
    result = models.JSONField(default=dict, null=True, blank=True)
    context = models.JSONField(default=dict, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    stored = models.DateTimeField(auto_now_add=True)
    authority = models.JSONField(default=dict, null=True, blank=True)
    version = models.CharField(max_length=20, default='1.0.0')
    moodle_data = models.JSONField(default=dict, null=True, blank=True)  # Store original Moodle data
    is_valid = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.actor.name} - {self.verb.verb_id} - {self.timestamp}"

class MoodleIntegration(models.Model):
    """Store Moodle connection details"""
    moodle_url = models.URLField()
    moodle_token = models.CharField(max_length=255)
    moodle_site_name = models.CharField(max_length=255)
    web_service_user = models.CharField(max_length=255, blank=True, null=True)
    lrs_endpoint = models.URLField(blank=True, null=True, help_text="LRS endpoint for this Moodle instance")
    auto_sync = models.CharField(max_length=20, choices=[('disabled', 'Disabled'), ('hourly', 'Hourly'), ('daily', 'Daily'), ('weekly', 'Weekly')], default='disabled')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.moodle_site_name