from django.contrib import admin
from .models import Dashboard, CheckListItem, CheckEvents

from .utils.excel import export_checkevents_to_excel

@admin.register(CheckListItem)
class CheckListItemAdmin(admin.ModelAdmin):
    list_display = ( 'dashboard', 'description', 'interval', 'crontab', 'is_active', 'start_at')
    list_filter = ('is_active', 'dashboard', 'interval', 'crontab')
    search_fields = ('dashboard', 'description',)


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ('uid', 'name', 'url', 'time_for_check')
    search_fields = ('name', 'url', 'uid')


@admin.register(CheckEvents)
class CheckEventsAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'dashboard', 'event_time', 'check_time', 'checked', 'no_problem')
    list_filter = ('checked', 'no_problem', 'event_time')
    search_fields = ('dashboard__name', 'dashboard__uid', 'uuid')
    readonly_fields = ('uuid', 'event_time')
    date_hierarchy = 'event_time'
    actions = [export_checkevents_to_excel]
