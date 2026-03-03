import io
from datetime import datetime, timedelta

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from ..models import Dashboard, CheckListItem, CheckEvents


def _format_timedelta_hms(td: timedelta) -> str:
    total = int(td.total_seconds())
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"

def _timedelta_checking(check_time : datetime | None, button_click_time : datetime | None):
    if check_time and button_click_time:
        result = _format_timedelta_hms(check_time - button_click_time)
    else:
        if not check_time:
            result = "На ссылку не нажимали"
        elif not button_click_time:
            result = "На кнопку не нажимали"
        else:
            result = "Источник не проверялся"
    return result

def export_checkevents_to_excel(modeladmin, request, queryset):
    """
    Экшен админки: выгрузить выбранные CheckEvents в Excel.
    """
    wb = Workbook()
    ws = wb.active
    if ws:
        ws.title = "CheckEvents"

        # Заголовки колонок
        headers = ["UUID проверки", "UID дашборда", "Имя дашборда", "Дата и время проверки", "Фактическая дата и время проверки", "Время нажатия кнопки", "Длительность проверки", "Проверено", "Есть проблема"]
        ws.append(headers)

        # Данные
        for ev in queryset.select_related("dashboard"):
            ws.append([
                str(ev.uuid),
                ev.dashboard.uid,
                ev.dashboard.name,
                ev.event_time.strftime("%Y-%m-%d %H:%M:%S"),
                ev.check_time.strftime("%Y-%m-%d %H:%M:%S") if ev.check_time else "-",
                ev.button_click_time.strftime("%Y-%m-%d %H:%M:%S"),
                _timedelta_checking(ev.check_time, ev.button_click_time),
                "да" if ev.checked else "нет",
                "нет" if ev.no_problem else "да",
            ])

        # Сохранить книгу в память
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        filename = f"checkevents_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

export_checkevents_to_excel.short_description = "Выгрузить выбранные cобытия в Excel"
