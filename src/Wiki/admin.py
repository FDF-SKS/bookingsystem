from django.contrib import admin
from django_tiptap_editor.admin.mixin import TipTapModelAdminMixin
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin

from .models import WikiPage


@admin.register(WikiPage)
class WikiPageAdmin(TipTapModelAdminMixin, ModelAdmin, ImportExportModelAdmin):
    tiptap_fields = ['content']
    list_display = ('title', 'parent', 'order', 'last_updated')
    list_filter = ('parent',)
    search_fields = ('title', 'content')
    readonly_fields = ('created', 'last_updated')

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
