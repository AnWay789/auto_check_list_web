import uuid
import httpx
import logging
from config.celery import app
from django.utils import timezone

from config.settings import DJANGO_EXTERNAL_URL
from .settings import TELEGRAM_URL, SEND_MESSAGE_ENDPOINT

from check_list.utils.text_format import markdownv2_to_html
from .models import CheckListItem, CheckEvents
from .pydantic_models import DashboardModel

from utils.clean import run_clear_old_task  # Регистрация таски очистки по всем моделям с clear_old
from utils.uteka.uteka import run_uteka_price_task, run_uteka_share_task  # noqa: F401 — регистрация тасок Ютека

logger = logging.getLogger(__name__)

@app.task
def start_send_dashboard_notification():
    """
    Периодическая задача для проверки и отправки дашбордов на проверку.
    Проверяет все активные элементы чек-листа и отправляет те, которые готовы к проверке.
    """
    try:
        # Получаем все активные элементы чек-листа
        items = CheckListItem.objects.filter(
            is_active=True
        )

        dashboards_to_send = []
        for item in items:
            # Проверяем, пора ли отправлять дашборд
            if item.start_at <= timezone.now():
                try:
                    # Создаем событие проверки дашборда
                    event = CheckEvents.objects.create(
                        uuid=uuid.uuid4(),
                        dashboard=item.dashboard,
                    )
                    # Добавляем модель дашборда для отправки
                    # Внешнему миру (телеграм-боту) отдаём hex-значение UUID, т.к. фронтенд работает с такими строками.
                    dash = DashboardModel(
                            event_uuid=event.uuid.hex,
                            dashboard_uid=item.dashboard.uid,
                            name=markdownv2_to_html(item.dashboard.name),
                            description=markdownv2_to_html(item.description) if item.description else "",
                            real_url=item.dashboard.url,
                            fake_url=f"http://{DJANGO_EXTERNAL_URL}/acl_api/to_dashboard/{event.uuid.hex}/",
                            # TODO: Сейчас время для проверки борда считается на стороне фронтенда, нужно 
                            # переделать что бы это считалось на стороне сервера. 
                            # 
                            time_for_check=item.dashboard.time_for_check,
                        ).model_dump(mode="json")
                    logger.info(f"{dash}")
                    dashboards_to_send.append(
                        dash
                    )
                    # Обновляем время следующего запуска
                    item.set_next_run()
                    logger.info(f"Подготовлен дашборд {item.dashboard.name} (event {event.uuid}) для отправки")
                except Exception as e:
                    logger.error(f"Ошибка при обработке элемента чек-листа {item.id}: {str(e)}")
                    continue

        if dashboards_to_send:
            # Вызываем задачу отправки дашбордов
            send_dashboard_notification.delay(dashboards_to_send)
            logger.info(f"Запланирована отправка {len(dashboards_to_send)} дашбордов")
        else:
            logger.debug("Нет дашбордов для отправки")
    except Exception as e:
        logger.error(f"Ошибка в start_send_dashboard_notification: {str(e)}", exc_info=True)

@app.task
def send_dashboard_notification(dashboards_to_send: list[dict]):
    """
    Отправляет список дашбордов на проверку в телеграм бот.
    Обрабатывает ошибки подключения и таймауты.
    """
    url = f"http://{TELEGRAM_URL}{SEND_MESSAGE_ENDPOINT}"
    try:
        logger.info(f"Отправка {len(dashboards_to_send)} дашбордов в телеграм бот по адресу {url}")
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url=url,
                json={"dashboards": dashboards_to_send}
            )
            response.raise_for_status()
            logger.info(f"Дашборды успешно отправлены в телеграм бот. Ответ: {response.status_code}")
    except httpx.TimeoutException:
        logger.error(f"Таймаут при отправке дашбордов в телеграм бот по адресу {url}")
        raise
    except httpx.ConnectError as e:
        logger.error(f"Ошибка соединения при отправке дашбордов в телеграм бот по адресу {url}: {str(e)}")
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"Ошибка HTTP {e.response.status_code} при отправке дашбордов в телеграм бот: {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при отправке дашбордов в телеграм бот: {str(e)}", exc_info=True)
        raise

