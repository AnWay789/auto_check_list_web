from string import Formatter
import ast
import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)
class OrderError(models.Model):
    number = models.IntegerField(primary_key=True)
    order_date = models.DateTimeField()

    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=64)

    rk_name = models.CharField(max_length=255, blank=True, null=True)
    store_address = models.CharField(max_length=512, blank=True, null=True)
    store_id = models.CharField(max_length=64)

    raw_products = models.JSONField(default=list, help_text="Список товаров в формате JSON. Например: [{\"product_guid\": \"1234567890\", \"product_name\": \"Товар 1\", \"product_code\": \"1234567890\", \"product_price\": 100.0}]", blank=True, null=True)
    products = models.TextField()
    order_sum = models.FloatField()

    error = models.CharField(max_length=512)
    recommended_action = models.TextField(blank=True, null=True)

    is_send_to_naumen = models.BooleanField(default=False)
    can_send_to_naumen = models.BooleanField(default=True)

    has_been_reissued = models.BooleanField(default=False, help_text="Был ли заказ переоформлен", null=True, blank=True)

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


recommended_action_help_text = """
Рекомендация для КЦ. Поддерживается вставка переменных: 
{number} - номер заказа
{customer_name} - имя клиента
{customer_phone} - телефон клиента
{rk_name} - название РК
{store_address} - адрес точки доставки
{store_id} - ID точки доставки
{product} - товар из ошибки (работает только для ошибок {'[GUID]': 'Заказанное количество превышает допустимый остаток.'})
{order_sum} - сумма заказа
{error} - ошибка 
+ ваши переменные из поля custom_values (если они есть)
"""
class RecommendedAction(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField()

    triger_field_choices = [
        ("error", "Ошибка"),
        ("products", "Товары"),
        ("order_sum", "Сумма заказа"),
        ("customer_name", "Имя клиента"),
        ("customer_phone", "Телефон клиента"),
        ("rk_name", "Название РК"),
        ("store_address", "Адрес точки доставки"),
        ("store_id", "ID точки доставки"),
    ]
    triger_field = models.CharField(max_length=255, choices=triger_field_choices, help_text="Поле которое будет проверяться на совпадение тригера")
    trigger = models.TextField(help_text="Ошибка заказа, если будет найдено в строке - подсавится эта рекомендация")
    recommended_action = models.TextField(help_text=recommended_action_help_text)
    
    ignored_values = models.JSONField(default=dict, help_text="Значения которые будут игнорироваться. Например если здесь будет указано {\"store_id\": \"null\"} и это действительно будет так - текущее рекомендация НЕ будет использована", blank=True, null=True)
    fail_values = models.JSONField(default=dict, help_text="Значения которые будут считаться ошибками. Например: {\"store_id\": \"null\"}. Если поле заказа совпадает с одним из значений в этом поле - переменные рекомендации либо не будут подставлены, либо будут подставлены значения из custom_values при их наличии", blank=True, null=True)
    custom_values = models.JSONField(default=dict, help_text="Переменные для вставки в рекомендацию. Например: {\"number\": 1, \"customer_name\": \"John\", \"customer_phone\": \"1234567890\"}. Так же можно использовать для \"стандартных\" значений которые будут подставляться если поле заказа пустое или подходит под fail_values", blank=True, null=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Рекомендация для КЦ"
        verbose_name_plural = "Рекомендации для КЦ"

    def __str__(self):
        return self.name

    def _get_trigger_field(self, order: OrderError) -> str | None:
        """
        Возвращает значение поля из заказа.
        """
        return getattr(order, self.triger_field, None)

    def _get_problem_product_from_error(self, order: OrderError) -> str | None:
        """
        Возвращает название проблемного товара из поля error и raw_products.

        Ожидается формат ошибки:
        {'<GUID>': 'Заказанное количество превышает допустимый остаток.'}
        """
        logger.info("RA: start _get_problem_product_from_error, order=%s", order)

        if not getattr(order, "error", None):
            logger.info("RA: no error field on order or it's empty")
            return None

        error_value = order.error
        logger.info("RA: raw error value (%s): %r", type(error_value), error_value)

        # Приводим error к dict: поддерживаем и строку, и уже готовый dict
        if isinstance(error_value, dict):
            data = error_value
            logger.info("RA: error is already dict with keys=%s", list(data.keys()))
        else:
            try:
                data = ast.literal_eval(str(error_value))
                logger.info("RA: parsed error to dict with keys=%s", list(data.keys()))
            except Exception as e:
                logger.warning("RA: failed to parse error with ast.literal_eval: %r", e, exc_info=True)
                return None

        if not isinstance(data, dict) or not data:
            logger.info("RA: parsed error is not dict or empty: %r", data)
            return None

        guid = list(data.keys())[0]
        logger.info("RA: extracted guid from error: %s", guid)

        raw_products = getattr(order, "raw_products", None) or []
        logger.info("RA: raw_products type=%s len=%d value=%r", type(raw_products), len(raw_products), raw_products)

        for idx, product in enumerate(raw_products):
            pg = str(product.get("product_guid") or "")
            logger.info("RA: check product #%d guid=%s name=%s", idx, pg, product.get("product_name"))
            if pg == guid:
                name = product.get("product_name")
                logger.info("RA: matched product guid, name=%s", name)
                return name

        logger.info("RA: no product found matching guid=%s", guid)
        return None

    def _check_fail_values(self, order: OrderError) -> bool:
        """
        Проверяет значения в fail_values.
        """
        # Если fail_values нет, то возвращаем True
        if not self.fail_values:
            return True
        # Проверяем значения в fail_values
        for key, value in self.fail_values.items():
            # Если значение в fail_values совпадает с значением в заказе, то возвращаем False
            if getattr(order, key) == value:
                return False
        return True

    def _check_ignored_values(self, order: OrderError) -> bool:
        """
        Проверяет значения в ignored_values.
        """
        # Если ignored_values нет, то возвращаем True
        if not self.ignored_values:
            return True
        # Проверяем значения в ignored_values
        for key, value in self.ignored_values.items():
            # Если значение в ignored_values совпадает с значением в заказе, то возвращаем False
            if getattr(order, key) == value:
                return False
        return True

    def _set_varible_in_recommended_action(self, recommended_action: str, custom_values: dict, order: OrderError) -> str:
        """
        Вставляет переменные в рекомендацию.

        Порядок подстановки для каждого плейсхолдера:
        1. Спецслучаи (например {product} из error + raw_products).
        2. Одноимённое поле заказа (getattr(order, name)).
        3. Значение из custom_values — fallback, если поле заказа пустое или отсутствует.
        """
        names = [f for _, f, _, _ in Formatter().parse(recommended_action) if f]
        for name in names:
            value = None

            # 1. Спецслучаи (здесь можно добавлять новые, например {product})
            if name == "product":
                value = self._get_problem_product_from_error(order)

            # 2. Поле заказа
            if value is None:
                value = getattr(order, name, None)

            # 3. Fallback из custom_values (текст, если поля заказа не было
            #    или оно содержит «техническое» значение, например "-" для store_id)
            if (value is None or self._check_fail_values(order)) and name in custom_values:
                value = custom_values[name]

            if value is not None:
                recommended_action = recommended_action.replace(
                    f"{{{name}}}", str(value)
                )

        return recommended_action

    def get_recommended_action(self, order: OrderError) -> str | None:
        """
        Возвращает рекомендацию для КЦ, если триггер сработал.
        """
        if not self.is_active:
            return None

        trigger_field = self._get_trigger_field(order)
        if trigger_field and trigger_field.find(self.trigger) != -1:
            # Если значения в ignored_values не совпадают с значением в заказе, то возвращаем рекомендацию
            if self._check_ignored_values(order):
                recommended_action = self._set_varible_in_recommended_action(self.recommended_action, self.custom_values, order)
                return recommended_action
        return None
