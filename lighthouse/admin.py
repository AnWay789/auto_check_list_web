from django.contrib import admin
from django.contrib import messages

from lighthouse.models import CheckEvents, CheckListItem, Source
from lighthouse.tasks import run_lighthouse_for_source


def run_lighthouse_action(modeladmin, request, queryset):
    """Экшен админки: поставить в очередь запуск Lighthouse для выбранных источников."""
    for source in queryset:
        run_lighthouse_for_source.delay(source.id)
    count = queryset.count()
    messages.success(
        request,
        f"Запуск Lighthouse поставлен в очередь для {count} источник(ов).",
    )


run_lighthouse_action.short_description = "Запустить Lighthouse"


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "url", "description")
    actions = [run_lighthouse_action]


@admin.register(CheckListItem)
class CheckListItemAdmin(admin.ModelAdmin):
    list_display = ("source", "description", "interval", "crontab", "is_active", "start_at")
    list_filter = ("is_active", "interval", "crontab")
    search_fields = ("source__name", "description")
    raw_id_fields = ("source",)


@admin.register(CheckEvents)
class CheckEventsAdmin(admin.ModelAdmin):
    list_display = ("source", "event_time", "status")
    list_filter = ("status", "event_time")
    search_fields = ("source__name",)
    readonly_fields = ("event_time",)
    date_hierarchy = "event_time"
