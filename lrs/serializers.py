# lrs/serializers.py
from rest_framework import serializers
from .models import Statement, Actor, Verb, Activity, MoodleIntegration
from django.utils import timezone
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
    actor = serializers.JSONField(required=False)
    verb = serializers.JSONField(required=False)
    object = serializers.JSONField(required=False)
    result = serializers.JSONField(required=False, allow_null=True)
    context = serializers.JSONField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField(required=False)
    authority = serializers.JSONField(required=False, allow_null=True)
    
    def validate_actor(self, value):
        """Validate actor object"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Actor must be a JSON object")
        if value is not None and 'objectType' not in value:
            value['objectType'] = 'Agent'
        return value
    
    def validate_verb(self, value):
        """Validate verb object"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Verb must be a JSON object")
        return value
    
    def validate_object(self, value):
        """Validate object object"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Object must be a JSON object")
        return value
    
    def create(self, validated_data):
        """Create Statement instance from validated data"""
        from .models import Statement, Actor, Verb, Activity
        
        # Create or get actor - use account name as unique identifier
        actor_data = validated_data.get('actor')
        account_name = actor_data.get('account', {}).get('name', actor_data.get('mbox', f"mailto:user_{actor_data.get('account', {}).get('name', 'unknown')}@example.com"))
        
        actor, _ = Actor.objects.get_or_create(
            actor_id=account_name,  # Use account name as unique ID
            defaults={
                'name': actor_data.get('name', 'Unknown'),
                'actor_type': 'Agent',
                'object_type': actor_data.get('objectType', 'Agent'),
                'mbox': actor_data.get('mbox', None),
                'account_name': actor_data.get('account', {}).get('name', None) if isinstance(actor_data.get('account'), dict) else None,
                'account_homepage': actor_data.get('account', {}).get('homePage', None) if isinstance(actor_data.get('account'), dict) else None,
            }
        )
        
        # Create or get verb
        verb_data = validated_data.get('verb')
        verb, _ = Verb.objects.get_or_create(
            verb_id=verb_data['id'],
            defaults={'display': verb_data.get('display', {'en-US': verb_data['id'].split('/')[-1]})}
        )
        
        # Create or get activity - use consistent activity_id
        object_data = validated_data.get('object')
        activity_id = object_data.get('id') if object_data else None
        
        activity = None
        if object_data and object_data.get('objectType') == 'Activity':
            activity, _ = Activity.objects.get_or_create(
                activity_id=activity_id,  # Use the same activity_id consistently
                defaults={
                    'definition': object_data.get('definition', {}),
                    'object_type': 'Activity'
                }
            )
        
        # Create statement using the new approach - create actor, verb, activity directly
        statement = Statement.objects.create(
            actor=actor,
            verb=verb,
            activity=activity,
            object=object_data,
            result=validated_data.get('result'),
            context=validated_data.get('context'),
            timestamp=validated_data.get('timestamp', timezone.now()),
            authority=validated_data.get('authority'),
            version='1.0.0'
        )
        
        return statement

class MoodleIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodleIntegration
        fields = '__all__'