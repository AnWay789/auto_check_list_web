from django.contrib import admin

from redash.models import RedashStatuses, RedashSQLs, RedashDashboard, RedashRequests

@admin.register(RedashStatuses)
class RedashStatusesAdmin(admin.ModelAdmin):
    list_display = ('description', 'is_final', 'is_success')
    list_filter = ('is_final', 'is_success')
    search_fields = ('description', 'id')

@admin.register(RedashSQLs)
class RedashSQLsAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'description', 'data_source_id', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('description', 'uuid', 'data_source_id')

@admin.register(RedashDashboard)
class RedashDashboardAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'crontab', 'start_at')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(RedashRequests)
class RedashRequestsAdmin(admin.ModelAdmin):
    list_display = ('redash_sql', 'dashboard', 'status', 'date_request')
    list_filter = ('redash_sql', 'dashboard', 'status')
