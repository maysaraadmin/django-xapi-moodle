from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Statement, Actor, Verb, Activity, MoodleIntegration

@admin.register(Statement)
class StatementAdmin(admin.ModelAdmin):
    list_display = ('statement_id', 'actor_name', 'verb_display', 'activity_name', 'timestamp', 'is_valid')
    list_filter = ('timestamp', 'verb__verb_id', 'is_valid', 'actor__name')
    search_fields = ('actor__name', 'verb__verb_id', 'activity__activity_id', 'object__icontains')
    readonly_fields = ('statement_id', 'stored', 'timestamp')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('statement_id', 'actor', 'verb', 'activity')
        }),
        ('Content', {
            'fields': ('object', 'result', 'context')
        }),
        ('Metadata', {
            'fields': ('authority', 'version', 'is_valid', 'timestamp', 'stored')
        }),
    )
    
    def actor_name(self, obj):
        return obj.actor.name if obj.actor else 'Unknown'
    actor_name.short_description = 'Actor'
    
    def verb_display(self, obj):
        if obj.verb and obj.verb.verb_id:
            return obj.verb.verb_id.split('/')[-1]
        return 'Unknown'
    verb_display.short_description = 'Verb'
    
    def activity_name(self, obj):
        if obj.activity and obj.activity.definition:
            return obj.activity.definition.get('name', {}).get('en-US', obj.activity.activity_id)
        return 'No Activity'
    activity_name.short_description = 'Activity'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('actor', 'verb', 'activity')

@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ('name', 'actor_type', 'mbox', 'moodle_user_id', 'created_at')
    list_filter = ('actor_type', 'created_at')
    search_fields = ('name', 'mbox', 'account_name')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'actor_type', 'object_type')
        }),
        ('Contact Information', {
            'fields': ('mbox', 'mbox_sha1sum', 'openid')
        }),
        ('Account Information', {
            'fields': ('account_name', 'account_homepage', 'moodle_user_id')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )

@admin.register(Verb)
class VerbAdmin(admin.ModelAdmin):
    list_display = ('verb_id_short', 'verb_display', 'created_at')
    search_fields = ('verb_id', 'display')
    readonly_fields = ('created_at',)
    
    def verb_id_short(self, obj):
        return obj.verb_id.split('/')[-1] if obj.verb_id else 'Unknown'
    verb_id_short.short_description = 'Verb ID'
    
    def verb_display(self, obj):
        if obj.display and 'en-US' in obj.display:
            return obj.display['en-US']
        return self.verb_id_short(obj)
    verb_display.short_description = 'Display Name'

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('activity_name', 'object_type', 'moodle_activity_id', 'moodle_course_id', 'created_at')
    list_filter = ('object_type', 'created_at')
    search_fields = ('activity_id', 'definition__icontains')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('activity_id', 'object_type')
        }),
        ('Definition', {
            'fields': ('definition',)
        }),
        ('Moodle Integration', {
            'fields': ('moodle_activity_id', 'moodle_course_id')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    
    def activity_name(self, obj):
        if obj.definition and 'name' in obj.definition:
            return obj.definition['name'].get('en-US', obj.activity_id)
        return obj.activity_id
    activity_name.short_description = 'Activity Name'

@admin.register(MoodleIntegration)
class MoodleIntegrationAdmin(admin.ModelAdmin):
    list_display = ('moodle_site_name', 'moodle_url', 'is_active', 'last_sync', 'created_at')
    list_filter = ('is_active', 'created_at', 'last_sync')
    search_fields = ('moodle_site_name', 'moodle_url')
    readonly_fields = ('created_at', 'last_sync')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('moodle_site_name', 'moodle_url')
        }),
        ('Authentication', {
            'fields': ('moodle_token', 'web_service_user')
        }),
        ('Status', {
            'fields': ('is_active', 'last_sync')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.pk:  # If editing existing object
            readonly.remove('last_sync')  # Allow updating last_sync
        return readonly

# Customize admin site
admin.site.site_header = 'xAPI Learning Record Store'
admin.site.site_title = 'xAPI LRS Admin'
admin.site.index_title = 'Welcome to xAPI LRS'
