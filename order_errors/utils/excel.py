import io
from datetime import datetime, timedelta

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from ..models import OrderError

def export_order_errors_to_excel(modeladmin, request, queryset):
    """
    Экшен админки: выгрузить выбранные OrderErrors в Excel.
    """
    wb = Workbook()
    ws = wb.active
    if ws:
        ws.title = "OrderErrors"

        # Заголовки колонок
        headers = ["Номер заказа", "Дата заказа", "Имя клиента", "Телефон клиента", "РК", "Адрес точки доставки", "ID точки доставки", "Товары", "Сумма заказа", "Ошибка", "Отправлено в КЦ", "Можно отправить в КЦ", "Рекомендация", "Был переоформлен"]
        ws.append(headers)

        # Данные (время переводим в таймзону приложения для отображения и расчёта длительности)
        for order in queryset:
            ws.append([
                str(order.number),
                order.order_date.strftime("%Y-%m-%d %H:%M:%S") if order.order_date else "-",
                order.customer_name if order.customer_name else "Не известно",
                order.customer_phone,
                order.rk_name if order.rk_name else "Не известно",
                order.store_address if order.store_address else "Не известно",
                order.store_id if order.store_id else "Не известно",
                order.products,
                order.order_sum if order.order_sum else 0,
                order.error,
                "Да" if order.is_send_to_naumen else "Нет",
                "Да" if order.can_send_to_naumen else "Нет",
                order.recommended_action if order.recommended_action else "Заданых действий не предусмотренно",
                "Да" if order.has_been_reissued else "Нет",
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

export_order_errors_to_excel.short_description = "Выгрузить выбранные заказы в Excel"
