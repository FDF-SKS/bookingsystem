from django.urls import path

from . import views

urlpatterns = [
    path('offline/', views.OfflineView.as_view(), name='notifications_offline'),

    # Settings
    path('settings/', views.NotificationSettingsView.as_view(), name='notifications_settings'),
    path('settings/preferences/', views.update_preferences, name='notifications_update_preferences'),

    # Web Push subscription API
    path('push/subscribe/', views.push_subscribe, name='notifications_push_subscribe'),
    path('push/unsubscribe/', views.push_unsubscribe, name='notifications_push_unsubscribe'),
    path('push/test/', views.push_test, name='notifications_push_test'),

    # Device calendar feeds
    path('calendar/<uuid:token>.ics', views.calendar_feed, name='notifications_calendar_feed'),
    path('calendar/rotate/', views.rotate_calendar_token, name='notifications_rotate_calendar'),
]
