from django.utils import timezone

def switch_active_status(modeladmin, request, queryset):
    """
    Экшен админки: переключить статус активности выбранных CheckListItem.
    """
    if not request.user.has_perm('check_list.can_switch_active_status'):
        modeladmin.message_user(request, "У вас нет прав для выполнения этого действия.", level='error')
        return

    for item in queryset:
        item.is_active = not item.is_active
        item.save()
switch_active_status.short_description = "Переключить статус активности"


def set_start_at_now(modeladmin, request, queryset):
    """
    Экшен админки: установить текущее время в поле start_at выбранных CheckListItem.
    """
    
    now = timezone.now()
    for item in queryset:
        item.start_at = now
        item.save()
set_start_at_now.short_description = "Установить текущее время в поле start_at"
