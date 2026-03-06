from django.contrib import admin

from order_errors.models import OrderError, Filters


@admin.register(OrderError)
class OrderErrorAdmin(admin.ModelAdmin):
    list_display = ('number', 'order_date', 'customer_name', 'store_id', 'error', 'is_send_to_naumen', 'can_send_to_naumen')
    list_filter = ('is_send_to_naumen', 'can_send_to_naumen', 'order_date')
    search_fields = ('number', 'customer_name', 'customer_phone', 'error')
    readonly_fields = ('number', 'order_date', 'customer_name', 'customer_phone', 'rk_name', 'store_id', 'store_address', 'products', 'order_sum', 'error')
    ordering = ['-order_date']

@admin.register(Filters)
class FiltersAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'is_active')
    search_fields = ('name', 'description')
    ordering = ['is_active']
