from ninja import NinjaAPI

# Основной API для чек-листа
acl_api = NinjaAPI(title="Auto Check List API", version="1.0.0")
# Отдельный API для работы с заказами с ошибками.
# Важно: задаём urls_namespace, чтобы отличать его от acl_api.
oe_api = NinjaAPI(title="Order Errors API", version="1.0.0", urls_namespace="order-errors")
# Импортируем хэндлеры, чтобы маршруты были зарегистрированы в NinjaAPI
# Важно: не удаляйте этот импорт, даже если он кажется «неиспользуемым».
from api.handlers import check_list  # noqa: F401
from api.handlers.order_error import patch_order_error_reissue, patch_order_error_not_reissue  # noqa: F401

