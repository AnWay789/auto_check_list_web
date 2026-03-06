from django.db import models
from django.utils import timezone



class OrderError(models.Model):
    number = models.IntegerField(primary_key=True)
    order_date = models.DateTimeField()

    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=64)

    rk_name = models.CharField(max_length=255, blank=True, null=True)
    store_address = models.CharField(max_length=512, blank=True, null=True)
    store_id = models.CharField(max_length=64)

    products = models.TextField()
    order_sum = models.FloatField()

    error = models.CharField(max_length=512)
    recommended_action = models.TextField(blank=True, null=True)

    is_send_to_naumen = models.BooleanField(default=False)
    can_send_to_naumen = models.BooleanField(default=True)

    class Meta:
        verbose_name = "400я ошибка заказа"
        verbose_name_plural = "400е ошибки заказов"

    def clear_old(self, days: int = 2):
        """
        Очищает старые запросы, которые были созданы более days (по дефолту 2) дней назад.
        """
        if self.order_date < (timezone.now() - timezone.timedelta(days=days)):
            self.delete()


filter_help_text = """
Фильтр в формате JSON. Например: {\"number\": [1, 2, 3], \"customer_name\": [\"John\", \"Jane\"]
Фильтровать можно по полям: number, customer_name, customer_phone, rk_name, store_id, store_address, products, order_sum, error
Eсли значение будет найдено в поле заказа - заказ не будет отправлен в КЦ
"""


def default_order_error_filter() -> dict:
    return {
        "number": [],
        "customer_name": [],
        "customer_phone": [],
        "rk_name": [],
        "store_id": [],
        "store_address": [],
        "products": [],
        "order_sum": [],
        "error": [],
    }


class Filters(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, help_text="Название фильтра. Для удобства использования в админке")
    description = models.TextField(help_text="Описание фильтра. Почему этот фильтр был заведен")
    filter = models.JSONField(default=default_order_error_filter, help_text=filter_help_text)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Фильтр ошибок заказов"
        verbose_name_plural = "Фильтры ошибок заказов"

    def __str__(self):
        return self.name

    def checking_for_filter(self, order: OrderError) -> bool:
        """
        Возвращает False, если ХОТЯ БЫ ОДИН фильтр сработал:
        любая строка из filter[field] входит в соответствующее поле заказа.
        Если ни одно условие не выполнилось – True (можно отправлять).
        """
        if not self.is_active:
            return True

        data = self.filter or {}

        def matches(field_value, key: str) -> bool:
            patterns = data.get(key) or []
            if not patterns or field_value is None:
                return False
            value_str = str(field_value)
            for pattern in patterns:
                if not pattern:
                    continue
                if str(pattern) in value_str:
                    return True
            return False

        if matches(order.number, "number"):
            return False
        if matches(order.customer_name, "customer_name"):
            return False
        if matches(order.customer_phone, "customer_phone"):
            return False
        if matches(order.rk_name, "rk_name"):
            return False
        if matches(order.store_id, "store_id"):
            return False
        if matches(order.store_address, "store_address"):
            return False
        if matches(order.products, "products"):
            return False
        if matches(order.order_sum, "order_sum"):
            return False
        if matches(order.error, "error"):
            return False

        return True
