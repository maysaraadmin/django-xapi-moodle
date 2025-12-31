# lrs/serializers.py
from rest_framework import serializers
from .models import Statement, Actor, Verb, Activity, MoodleIntegration
import json

class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = '__all__'

class VerbSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verb
        fields = '__all__'

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = '__all__'

class StatementSerializer(serializers.ModelSerializer):
    actor_data = ActorSerializer(source='actor', read_only=True)
    verb_data = VerbSerializer(source='verb', read_only=True)
    activity_data = ActivitySerializer(source='activity', read_only=True)
    
    class Meta:
        model = Statement
        fields = '__all__'

class StatementCreateSerializer(serializers.Serializer):
    """Serializer for incoming xAPI statements"""
    actor = serializers.JSONField()
    verb = serializers.JSONField()
    object = serializers.JSONField()
    result = serializers.JSONField(required=False, allow_null=True)
    context = serializers.JSONField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField(required=False)
    authority = serializers.JSONField(required=False, allow_null=True)
    
    def validate_actor(self, value):
        """Validate actor object"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Actor must be a JSON object")
        if 'objectType' not in value:
            value['objectType'] = 'Agent'
        return value
    
    def validate_verb(self, value):
        """Validate verb object"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Verb must be a JSON object")
        if 'id' not in value:
            raise serializers.ValidationError("Verb must have an 'id' field")
        return value

class MoodleIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodleIntegration
        fields = '__all__'