import ast
import logging
from datetime import timedelta

from django.utils import timezone

from redash.models import RedashRequests

from order_errors.schemas.order_error import RawOrderError, OrderError
from order_errors.models import OrderError as OrderErrorModel, Filters, RecommendedAction

from api.schemas.naumen.naumen_schema import PhoneNumber, CustomForm, CustomFormDefault, CustomForm, NaumenErrorRequest
from api.wrappers.naumen import NaumenClient

logger = logging.getLogger(__name__)

STORE_ERROR = "Неизвестная точка доставки"
PRICE_ERROR = "Невозможно получить цену на товар"
QUANTITY_ERROR = "Заказанное количество превышает допустимый остаток"
VALIDATION_ERROR = "Заказ с таким id уже существует"

STORE_RECOMMENDED_ACTIONS_WITH_STORE = "Переоформить заказ на ближайшую к этой ({store_address}) точку доставки"
STORE_RECOMMENDED_ACTIONS_WITHOUT_STORE = "Просьба выяснить на какую точку пользователь пытался оформить заказ и переоформить его на ближайшую к ней точку доставки"
PRICE_RECOMMENDED_ACTION = "Просьба переоформить заказ на ближайшую к этой ({store_address}) точку доставки и при необходимости (если остатков нет) подобрать аналог товару"
PRICE_RECOMMENDED_ACTION_WITHOUT_STORE = "Просьба переоформить заказ и при необходимости (если остатков нет) подобрать аналог товару"
QUANTITY_RECOMMENDED_ACTIONS_WITH_PRODUCT = "Требуется подобрать аналог товару {product} и переоформить заказ"
QUANTITY_RECOMMENDED_ACTIONS_WITHOUT_PRODUCT = "Требуется подобрать аналог товару и переоформить заказ"
VALIDATION_ERROR_RECOMMENDED_ACTION = (
    "Необходимо проверить существует ли такой заказ в ECOM с этим номером телефона и номером заказа\n"
    "1. Если существует - ничего не делать\n"
    "2. Если не существует - передать L1 и переоформить заказ"
)


class RedashNaumenSync:
    """
    Сервисный класс для синхронизации заказов с ошибками между Redash и Наумен.

    Отвечает за:
    - загрузку данных по ошибочным заказам из Redash;
    - преобразование их в удобный вид для операторов КЦ;
    - сохранение в локную БД;
    - подготовку и отправку обращений в Наумен.
    """

    def _collect_orders(self, dashboard_id: int) -> dict[str, list[RawOrderError]]:
        """
        Получает из Redash сырые строки с ошибками заказов и группирует их по номеру заказа.

        :param dashboard_id: идентификатор дашборда Redash.
        :return: словарь {номер_заказа: [RawOrderError, ...]}.
        """
        # Получаем последний успешный и финальный запрос по указанному дашборду
        request = (
            RedashRequests.objects.filter(
                dashboard_id=dashboard_id,
                status__is_final=True,
                status__is_success=True,
            )
            .order_by("-date_request")
            .first()
        )

        if not request:
            # Нет данных по этому дашборду — возвращаем пустой словарь
            return {}

        try:
            # Ожидаем структуру: result → query_result → data → rows
            rows = request.result.get("query_result", {}).get("data", {}).get("rows", [])
        except (AttributeError, TypeError):
            logger.warning(
                "Неожиданная структура result у запроса Redash request_id=%s",
                getattr(request, "id", None),
            )
            return {}

        orders: dict[str, list[RawOrderError]] = {}
        for row in rows:
            try:
                # Валидируем и приводим строку к pydantic‑схеме RawOrderError
                order_error = RawOrderError.model_validate(row)
            except Exception as e:
                logger.warning("Ошибка валидации строки из Redash: %s", e, exc_info=True)
                continue

            if order_error.number not in orders:
                orders[order_error.number] = []
            orders[order_error.number].append(order_error)

        logger.info(
            "Собрано заказов из Redash (dashboard_id=%s): %s",
            dashboard_id,
            len(orders),
        )
        return orders

    def _filter_existing(
        self,
        raw_orders: dict[str, list[RawOrderError]],
    ) -> dict[str, OrderError]:
        """
        Фильтрует уже существующие заказы и агрегирует данные по оставшимся.

        На вход приходит набор «сырых» строк по заказам из Redash, сгруппированных по номеру
        заказа. Метод:
        - удаляет номера заказов, которые уже присутствуют в модели `OrderErrorModel`;
        - собирает по каждому новому заказу агрегированный объект `OrderError`
          с готовым списком позиций, суммой и рекомендацией для КЦ.

        :param raw_orders: словарь {номер_заказа: [RawOrderError, ...]}.
        :return: словарь {номер_заказа: OrderError}.
        """
        self._remove_existing_orders(raw_orders)

        clear_orders: dict[str, OrderError] = {}

        for order_number, raw_order_items in raw_orders.items():
            if not raw_order_items:
                continue

            first_item = raw_order_items[0]
            order_error = self._build_order_error_base(first_item)
            products, order_total, raw_products = self._build_products_and_total(raw_order_items)

            # ВАЖНО: сначала заполняем raw_products, затем строим рекомендацию,
            # чтобы RecommendedAction мог использовать problem product.
            order_error.products = products
            order_error.order_sum = order_total
            order_error.raw_products = raw_products
            recommended_action = self._build_recommended_action(order_error, products)
            order_error.recommended_action = recommended_action
            clear_orders[order_number] = order_error

        logger.info(
            "После фильтрации существующих осталось заказов для сохранения: %s",
            len(clear_orders),
        )
        return clear_orders

    def _remove_existing_orders(
        self,
        raw_orders: dict[str, list[RawOrderError]],
    ) -> None:
        """
        Удаляет из словаря заказов те номера, которые уже есть в БД.

        Модифицирует входной словарь «на месте», оставляя только новые заказы.

        :param raw_orders: словарь {номер_заказа: [RawOrderError, ...]}.
        """
        existing_orders = OrderErrorModel.objects.filter(
            number__in=raw_orders.keys()
        )

        for existing in existing_orders:
            # Если заказ уже сохранён, повторно его не обрабатываем
            raw_orders.pop(str(existing.number), None)

    def _build_order_error_base(self, first_item: RawOrderError) -> OrderError:
        """
        Формирует базовый объект `OrderError` по первой строке заказа.

        Переносит все общие для заказа атрибуты (номер, дата, клиент, точка и т.п.).
        Список товаров и сумма заказа будут заполнены отдельно.

        :param first_item: первая строка заказа из Redash.
        :return: объект `OrderError` без товаров и суммы.
        """
        return OrderError(
            ts=first_item.order_date,
            number=first_item.number,
            customer_name=first_item.customer_name,
            customer_phone=first_item.customer_phone,
            rk_name=first_item.rk_name,
            store_id=first_item.store_id,
            store_address=first_item.store_address,
            error=first_item.error,
            raw_products=[],
            products=[],
        )

    def _build_products_and_total(
        self,
        raw_order_items: list[RawOrderError],
    ) -> tuple[list[str], float, list[dict]]:
        """
        Собирает человекочитаемый список позиций заказа и рассчитывает итоговую сумму.

        Для каждой позиции вычисляется статус по остаткам в ECOM и 1С, чтобы оператору
        КЦ было проще понять, в чём именно проблема по товару.

        :param raw_order_items: все строки по одному заказу.
        :return: кортеж (список_строк_с_позициями, сумма_заказа, список_raw_товаров).
        """
        products: list[str] = []
        order_total: float = 0.0
        raw_products: list[dict] = []

        for raw_order in raw_order_items:
            # Определяем статус остатков по позиции
            if raw_order.ecom_stock < 1:
                status = "Нет в ECOM"
            elif raw_order.one_s_stock < 1:
                status = "Нет в 1С"
            else:
                status = "Есть везде"
                if raw_order.ordered > raw_order.ecom_stock:
                    status += ", заказано > есть в ECOM"
                if raw_order.ordered > raw_order.one_s_stock:
                    status += ", заказано > есть в 1С"

            # Собираем строку позиции в удобном для КЦ формате
            # Пример:
            # <GUID> - <наименование> (<код>) Цена: <цена> Заказано: <n> В 1С: <x> В ECOM: <y> Статус: <статус>,
            products.append(
                f"{raw_order.product_guid} - {raw_order.product_name} "
                f"({raw_order.product_code}) "
                f"Цена: {raw_order.product_price} "
                f"Заказано: {raw_order.ordered} "
                f"В 1С: {raw_order.one_s_stock} "
                f"В ECOM: {raw_order.ecom_stock} "
                f"Статус: {status},"
            )
            order_total += raw_order.product_price * raw_order.ordered

            # Запоминаем «сырую» информацию о товаре в формате JSON‑совместимого словаря
            raw_products.append(
                {
                    "product_guid": raw_order.product_guid,
                    "product_name": raw_order.product_name,
                    "product_code": raw_order.product_code,
                    "product_price": raw_order.product_price,
                    "ordered": raw_order.ordered,
                    "one_s_stock": raw_order.one_s_stock,
                    "ecom_stock": raw_order.ecom_stock,
                    "status": status,
                }
            )

        return products, order_total, raw_products

    def _build_recommended_action(
        self,
        order_error: OrderError,
        products: list[str],
    ) -> str | None:
        """
        Строит рекомендацию для КЦ, используя модель `RecommendedAction`.

        Логика подбора и подстановки переменных полностью инкапсулирована
        в модели `RecommendedAction` (см. `RecommendedAction.get_recommended_action`).
        Здесь мы просто пробегаем по активным правилам и возвращаем первую
        сработавшую рекомендацию.

        :param order_error: агрегированная информация по заказу.
        :param products: человекочитаемый список позиций заказа (пока не используется,
                         но оставлен для возможного расширения логики).
        :return: текст рекомендации или None.
        """
        for rule in RecommendedAction.objects.filter(is_active=True):
            text = rule.get_recommended_action(order_error)
            if text:
                return text
        return None

    def _save_orders(self, clear_orders: dict[str, OrderError]) -> None:
        """
        Сохраняет подготовленные ошибки заказов в таблицу `OrderErrorModel`.

        Дополнительно прогоняет каждый заказ через набор фильтров `Filters`, чтобы
        решить, можно ли отправлять его в Наумен.

        :param clear_orders: словарь {номер_заказа: OrderError}.
        """
        firlters = Filters.objects.all()
        for order_error in clear_orders.values():
            can_send_to_naumen = True
            for filter in firlters:
                if not filter.checking_for_filter(order_error):
                    can_send_to_naumen = False
                    break
            OrderErrorModel.objects.create(
                number=int(order_error.number),
                order_date=order_error.order_date,

                customer_name=order_error.customer_name,
                customer_phone=order_error.customer_phone,

                rk_name=order_error.rk_name,
                store_address=order_error.store_address,
                store_id=order_error.store_id,

                raw_products=order_error.raw_products,
                products="\n".join(order_error.products),
                order_sum=order_error.order_sum,

                error=order_error.error,
                recommended_action=order_error.recommended_action,
                can_send_to_naumen=can_send_to_naumen,
            )

    def get_and_save_orders(self, dashboard_id: int) -> int:
        """
        Загружает ошибки заказов из дашборда Redash и сохраняет новые записи в БД.

        :param dashboard_id: идентификатор дашборда Redash.
        :return: количество сохранённых заказов.
        """
        orders = self._collect_orders(dashboard_id)
        clear_orders = self._filter_existing(orders)
        self._save_orders(clear_orders)
        count = len(clear_orders)
        logger.info("Сохранено заказов с ошибками: %s", count)
        return count

    def _get_error_order(self) -> tuple[list[NaumenErrorRequest], list[int]]:
        """
        Возвращает ошибки по заказам в формате для Наумена и список номеров заказов (number).
        В scheduledTime и Data_zakaza передаётся текущее время + 1 час (Naumen не принимает дату в прошлом).
        Реальная дата заказа указывается в комментарии.

        :return: (список NaumenErrorRequest, список номеров заказов).
        """
        orders = list(OrderErrorModel.objects.filter(is_send_to_naumen=False, can_send_to_naumen=True).all())
        order_numbers = [o.number for o in orders]

        now_plus_5min = timezone.now() + timedelta(minutes=5)
        order_requests = []
        for order in orders:
            order_date_display = (
                timezone.localtime(order.order_date).strftime("%d.%m.%Y %H:%M")
                if order.order_date else "—"
            )
            order_requests.append(NaumenErrorRequest(
                title=f"{order.number}",
                state="adjourned",
                scheduledTime=now_plus_5min,
                comment=(
                    # В комментарий кладём дату 400‑ошибки и краткую причину из OrderError
                    f"___Дата 400 ошибки: {order_date_display}"
                    f"___Причина ошибки: {order.error}"
                ),
                phoneNumbers=[PhoneNumber(number=order.customer_phone, code="MOBILE")],
                customForm=CustomForm(
                    default=CustomFormDefault(
                        Data_zakaza=[order.order_date.isoformat()],
                        order=[f"{order.number}"],
                        RK=[order.rk_name if order.rk_name else "Не указано"],
                        Adres=[order.store_address if order.store_address else "Не указано"],
                        Naimenovanie=[order.products],
                        sum=[str(order.order_sum)],
                        prichina=[f"{order.error}"],
                        comment=[f"Что делать: {order.recommended_action if order.recommended_action else "Не указано"}"],
                    )
                )
            ))

        return order_requests, order_numbers

    def _send_to_naumen(self) -> int:
        """
        Отправляет неотправленные заказы в Наумен.

        :return: количество успешно отправленных заказов.
        """
        cases, order_numbers = self._get_error_order()
        logger.info(cases)
        if not cases:
            logger.info("Нет заказов для отправки в Наумен")
            return 0
        try:
            client = NaumenClient()
            client.create_case(cases=cases)
            OrderErrorModel.objects.filter(number__in=order_numbers).update(is_send_to_naumen=True)
            logger.info("Отправлено заказов в Наумен: %s", len(order_numbers))
            return len(order_numbers)
        except Exception as e:
            logger.exception("Ошибка отправки заказов в Наумен: %s", e)
            raise

    def save_orders_from_dashboard_responce(self, dashboard_id: int):
        """
        Обёртка над `get_and_save_orders` для использования в API/задачах.

        :param dashboard_id: идентификатор дашборда Redash.
        :return: словарь с ключом saved — сколько заказов сохранено.
        """
        saved = self.get_and_save_orders(dashboard_id)
        return {"saved": saved}

    def send_orders_to_naumen(self):
        """
        Обёртка над `_send_to_naumen` для использования в API/задачах.

        :return: словарь с ключом sent — сколько заказов отправлено.
        """
        sent = self._send_to_naumen()
        return {"sent": sent}

    def sync_and_send_errors(self, dashboard_id: int) -> dict[str, int]:
        """
        Синхронизация заказов с ошибками из Redash и отправка неотправленных в Наумен.
        Возвращает словарь с ключами: saved (сохранено из Redash), sent (отправлено в Наумен).
        """
        saved = self.get_and_save_orders(dashboard_id)
        sent = self._send_to_naumen()
        return {"saved": saved, "sent": sent}
