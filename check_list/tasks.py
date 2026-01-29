import uuid
import httpx
import logging
from config.celery import app
from django.utils import timezone

from config.settings import DJANGO_EXTERNAL_URL
from .settings import TELEGRAM_URL, SEND_MESSAGE_ENDPOINT

from .models import CheckListItem, CheckEvents
from .pydantic_models import DashboardModel

from check_list.utils.clean_events import clean_old_events  # Импорт утилиты для очистки старых событий что бы она регестрировалсь

logger = logging.getLogger(__name__)

@app.task
def debug_task(message: str = "Hello from Celery"):
    """
    Простая отладочная задача, которая выводит сообщение в логи worker'а.
    Эту задачу удобно использовать для проверки работоспособности Celery.
    """
    print(f"[{timezone.now()}] Celery debug_task: {message}")

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
                    dashboards_to_send.append(
                        DashboardModel(
                            event_uuid=event.uuid.hex,
                            dashboard_uid=item.dashboard.uid,
                            name=item.dashboard.name,
                            description=item.description,
                            real_url=item.dashboard.url,
                            fake_url=f"http://{DJANGO_EXTERNAL_URL}/api/to_dashboard/{event.uuid.hex}/",
                            time_for_check=item.dashboard.time_for_check,
                        ).model_dump(mode="json")
                    )
                    # Обновляем время следующего запуска
                    item.set_next_run()
                    logger.info(f"Prepared dashboard {item.dashboard.name} (event {event.uuid}) for notification")
                except Exception as e:
                    logger.error(f"Error processing checklist item {item.id}: {str(e)}")
                    continue

        if dashboards_to_send:
            # Вызываем задачу отправки дашбордов
            send_dashboard_notification.delay(dashboards_to_send)
            logger.info(f"Scheduled notification for {len(dashboards_to_send)} dashboard(s)")
        else:
            logger.debug("No dashboards to send")
    except Exception as e:
        logger.error(f"Error in start_send_dashboard_notification: {str(e)}", exc_info=True)       

@app.task
def send_dashboard_notification(dashboards_to_send: list[dict]):
    """
    Отправляет список дашбордов на проверку в телеграм бот.
    Обрабатывает ошибки подключения и таймауты.
    """
    url = f"http://{TELEGRAM_URL}{SEND_MESSAGE_ENDPOINT}"
    try:
        logger.info(f"Sending {len(dashboards_to_send)} dashboard(s) to telegram bot at {url}")
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url=url,
                json={"dashboards": dashboards_to_send}
            )
            response.raise_for_status()
            logger.info(f"Successfully sent dashboards to telegram bot. Response: {response.status_code}")
    except httpx.TimeoutException:
        logger.error(f"Timeout while sending dashboards to telegram bot at {url}")
        raise
    except httpx.ConnectError as e:
        logger.error(f"Connection error while sending dashboards to telegram bot at {url}: {str(e)}")
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} while sending dashboards to telegram bot: {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while sending dashboards to telegram bot: {str(e)}", exc_info=True)
        raise

