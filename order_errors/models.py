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

    class Meta:
        verbose_name = "400я ошибка заказа"
        verbose_name_plural = "400е ошибки заказов"

    def clear_old(self, days: int = 2):
        """
        Очищает старые запросы, которые были созданы более days (по дефолту 2) дней назад.
        """
        if self.order_date < (timezone.now() - timezone.timedelta(days=days)):
            self.delete()
