from django.contrib import admin

from order_errors.models import OrderError


@admin.register(OrderError)
class OrderErrorAdmin(admin.ModelAdmin):
    list_display = ('number', 'order_date', 'customer_name', 'store_id', 'is_send_to_naumen', 'error')
    list_filter = ('is_send_to_naumen', 'order_date')
    search_fields = ('number', 'customer_name', 'customer_phone', 'error')
    readonly_fields = ('number', 'order_date', 'customer_name', 'customer_phone', 'rk_name', 'store_id', 'store_address', 'products', 'order_sum', 'error')
