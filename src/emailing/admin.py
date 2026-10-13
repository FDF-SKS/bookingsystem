from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import EmailMessageLog, EmailSuppression


@admin.register(EmailMessageLog)
class EmailMessageLogAdmin(ModelAdmin):
    list_display = ('created_at', 'recipient', 'subject', 'status', 'attempts', 'bounce_type')
    list_filter = ('status', 'template', 'created_at')
    search_fields = ('recipient', 'subject', 'ses_message_id')
    date_hierarchy = 'created_at'
    exclude = ('body_html', 'body_text', 'attachments')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(EmailSuppression)
class EmailSuppressionAdmin(ModelAdmin):
    list_display = ('email', 'reason', 'created_at')
    list_filter = ('reason',)
    search_fields = ('email',)
