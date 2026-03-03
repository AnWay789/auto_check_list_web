import uuid
from datetime import timezone as dt_timezone

from django.http import HttpResponseRedirect, Http404
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
import logging

from ..api_app import api
from ..schemas.check_list_colback import CheckListColback
from check_list.models import Dashboard, CheckListItem, CheckEvents

logger = logging.getLogger(__name__)


@api.post("/dashbord_colback/")
def get_check_list(request, payload: CheckListColback):
    """
    Обработка колбэка от фронтенда.
    Фронтенд присылает event_uuid как hex-строку, здесь приводим её к UUID.
    """
    try:
        event_uuid = uuid.UUID(payload.event_uuid)
        event = CheckEvents.objects.get(uuid=event_uuid)
        # Приводим время из колбэка (UTC) к таймзоне приложения (Europe/Moscow)
        if payload.date_time:
            dt = payload.date_time
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, dt_timezone.utc)
            event.button_click_time = timezone.localtime(dt)
        else:
            event.button_click_time = None # при отсутствии времени считаем, что кнопка не нажата
        event.no_problem = not payload.problem  # реверс логики для базы: фронт отправляет problem=True при проблеме
        event.save(update_fields=["button_click_time", "no_problem"])
        logger.info(f"Event {payload.event_uuid} marked as {'problem' if payload.problem else 'ok'}")
        logger.info(f"Button click time: {payload.date_time}, Problem: {payload.problem}")
        return {"status": "success"}
    except (ValueError, TypeError):
        logger.error(f"Invalid event UUID format: {payload.event_uuid}")
        return {"status": "error", "message": "Invalid event UUID"}, 400
    except ObjectDoesNotExist:
        logger.error(f"Event {payload.event_uuid} not found")
        return {"status": "error", "message": "Event not found"}, 404
    except Exception as e:
        logger.error(f"Error processing callback for event {payload.event_uuid}: {str(e)}")
        return {"status": "error", "message": "Internal server error"}, 500


@api.get("/to_dashboard/{event_uuid}/")
def to_dashboard(request, event_uuid: str):
    """
    Фронтенд/переход по ссылке использует hex-строку UUID.
    Здесь приводим её к UUID для поиска в базе.
    """
    try:
        real_uuid = uuid.UUID(event_uuid)
        event = CheckEvents.objects.get(uuid=real_uuid)
        if not event.checked:
            event.checked = True
            event.check_time = timezone.now()
            event.save(update_fields=["checked", "check_time"])
            logger.info(f"Event {event_uuid} marked as checked, redirecting to {event.dashboard.url}")
        else:
            logger.info(f"Event {event_uuid} already checked, redirecting to {event.dashboard.url}")

        if not event.dashboard.url:
            logger.error(f"Dashboard {event.dashboard.uid} has no URL")
            return {"status": "error", "message": "Dashboard URL not configured"}, 500

        return HttpResponseRedirect(event.dashboard.url)
    except (ValueError, TypeError):
        logger.error(f"Invalid event UUID format in redirect: {event_uuid}")
        raise Http404("Invalid event UUID")
    except ObjectDoesNotExist:
        logger.error(f"Event {event_uuid} not found")
        raise Http404("Event not found")
    except Exception as e:
        logger.error(f"Error redirecting for event {event_uuid}: {str(e)}")
        return {"status": "error", "message": "Internal server error"}, 500
