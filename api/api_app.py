from ninja import NinjaAPI

api = NinjaAPI(title="Auto Check List API", version="1.0.0")

# Импортируем хэндлеры, чтобы маршруты были зарегистрированы в NinjaAPI
# Важно: не удаляйте этот импорт, даже если он кажется «неиспользуемым».
from api.handlers import check_list  # noqa: F401
