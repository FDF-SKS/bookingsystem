from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    CalendarFeedToken,
    NotificationPreference,
    PushSubscription,
    SentReminder,
)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(ModelAdmin):
    list_display = ('user', 'short_endpoint', 'created', 'last_seen', 'failure_count')
    list_filter = ('created',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'endpoint')
    readonly_fields = ('created', 'last_seen')

    @admin.display(description='Endpoint')
    def short_endpoint(self, obj):
        return f'{obj.endpoint[:70]}…' if len(obj.endpoint) > 70 else obj.endpoint


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(ModelAdmin):
    list_display = (
        'user',
        'notify_bookings',
        'notify_tasks',
        'notify_upcoming',
        'last_updated',
    )
    search_fields = ('user__email', 'user__first_name', 'user__last_name')


@admin.register(CalendarFeedToken)
class CalendarFeedTokenAdmin(ModelAdmin):
    list_display = ('user', 'token', 'created', 'last_updated')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('token', 'created', 'last_updated')


@admin.register(SentReminder)
class SentReminderAdmin(ModelAdmin):
    list_display = ('key', 'created')
    search_fields = ('key',)
    readonly_fields = ('key', 'created')
