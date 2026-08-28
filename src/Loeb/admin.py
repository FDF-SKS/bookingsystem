from django.contrib import admin
from django.urls import reverse
from import_export.admin import ImportExportModelAdmin
from unfold.admin import ModelAdmin

from . import models


@admin.register(models.Loeb)
class LoebAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ('name', 'team', 'is_active', 'show_map', 'show_points', 'created')
    list_filter = ('is_active', 'show_map', 'show_points', 'team')
    search_fields = ('name', 'team__name')


@admin.register(models.PhysicalStation)
class PhysicalStationAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ('name', 'qr_code', 'station_url', 'is_active', 'created')
    list_filter = ('is_active',)
    search_fields = ('name', 'qr_code')
    exclude = ('qr_code',)
    change_form_template = 'admin/Loeb/physicalstation/change_form.html'

    class Media:
        css = {
            'all': ('css/admin_leaflet_fix.css',),
        }

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            obj = self.get_object(request, object_id)
            if obj:
                extra_context['full_qr_url'] = request.build_absolute_uri(obj.get_absolute_url())
                extra_context['qr_download_name'] = self.get_qr_download_name(obj)
        return super().changeform_view(request, object_id, form_url, extra_context)

    @staticmethod
    def get_qr_download_name(obj):
        path = (obj.get_absolute_url() or '').strip('/').replace('/', '-')
        filename = path or 'station'
        return filename.replace(' ', '-') + '.png'

    @admin.display(description='QR URL')
    def station_url(self, obj):
        if not obj or not obj.pk:
            return ''
        try:
            return obj.get_full_url()
        except Exception:
            return ''


@admin.register(models.Task)
class TaskAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ('title', 'loeb', 'task_type', 'is_published', 'station', 'created')
    list_filter = ('task_type', 'is_published', 'loeb')
    search_fields = ('title', 'description', 'loeb__name')


@admin.register(models.Hold)
class HoldAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ('name', 'loeb', 'pin_code', 'is_active', 'created')
    list_filter = ('is_active', 'loeb')
    search_fields = ('name', 'pin_code')


@admin.register(models.TaskSubmission)
class TaskSubmissionAdmin(ModelAdmin, ImportExportModelAdmin):
    list_display = ('hold', 'task', 'state', 'points_awarded', 'created')
    list_filter = ('state', 'task__loeb')
    search_fields = ('hold__name', 'task__title')
