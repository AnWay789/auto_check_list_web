import logging

import httpx
from config.celery import app
from django.conf import settings
from django.utils import timezone

from lighthouse.models import CheckEvents, CheckListItem, Source
from lighthouse.runner import run_lighthouse

logger = logging.getLogger(__name__)


def _post_to_elk(result: dict) -> None:
    """Отправляет один результат Lighthouse в ELK, если настроены ELK_*."""
    elk_url = getattr(settings, "ELK_URL", None)
    if not elk_url:
        return
    elk_user = getattr(settings, "ELK_USER", None)
    elk_password = getattr(settings, "ELK_PASSWORD", None) or getattr(
        settings, "ELK_AUTH", None
    )
    verify_ssl = getattr(settings, "ELK_VERIFY_SSL", False)
    try:
        auth = (elk_user, elk_password) if (elk_user and elk_password) else None
        with httpx.Client(verify=verify_ssl, timeout=30.0) as client:
            resp = client.post(elk_url, json=result, auth=auth)
            resp.raise_for_status()
            logger.debug("Posted Lighthouse result to ELK: %s", resp.status_code)
    except Exception as e:
        logger.warning("Failed to post to ELK: %s", e)


@app.task
def run_lighthouse_for_source(source_id: int) -> dict | None:
    """
    Запускает Lighthouse для одного источника и сохраняет результат в CheckEvents.
    """
    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist:
        logger.error("Source id=%s not found", source_id)
        return None

    event = CheckEvents.objects.create(source=source)
    result = run_lighthouse(
        url=source.url,
        metadata=source.metadata or {},
        headers=source.headers or {},
    )
    event.status = result.get("status")
    event.metrics = result.get("metrics")
    event.error_message = result.get("message")
    event.save(update_fields=["status", "metrics", "error_message"])

    if getattr(settings, "ELK_URL", None):
        _post_to_elk(result)

    logger.info(
        "Lighthouse run for source %s (%s): status=%s",
        source_id,
        source.name,
        result.get("status"),
    )
    return result


@app.task
def run_scheduled_lighthouse_checks():
    """
    Периодическая задача: находит CheckListItem (lighthouse), готовые к проверке,
    и ставит в очередь по одной задаче на каждый элемент (распараллеливание).
    """
    try:
        item_ids = list(
            CheckListItem.objects.filter(
                is_active=True,
                source__is_active=True,
                start_at__lte=timezone.now(),
            ).values_list("id", flat=True)
        )
        for item_id in item_ids:
            run_lighthouse_for_checklist_item.delay(item_id)
        if item_ids:
            logger.info("Scheduled %s lighthouse check task(s)", len(item_ids))
    except Exception as e:
        logger.error(
            "Error in run_scheduled_lighthouse_checks: %s", e, exc_info=True
        )


@app.task
def run_lighthouse_for_checklist_item(item_id: int) -> dict | None:
    """
    Запускает Lighthouse для одного элемента расписания: создаёт событие,
    сохраняет результат, обновляет start_at. Вызывается из run_scheduled_lighthouse_checks.
    """
    try:
        item = CheckListItem.objects.select_related("source").get(pk=item_id)
    except CheckListItem.DoesNotExist:
        logger.error("CheckListItem id=%s not found", item_id)
        return None

    source = item.source
    event = CheckEvents.objects.create(source=source)
    try:
        result = run_lighthouse(
            url=source.url,
            metadata=source.metadata or {},
            headers=source.headers or {},
        )
        event.status = result.get("status")
        event.metrics = result.get("metrics")
        event.error_message = result.get("message")
        event.save(update_fields=["status", "metrics", "error_message"])

        if getattr(settings, "ELK_URL", None):
            _post_to_elk(result)

        item.set_next_run()
        logger.info(
            "Lighthouse run for checklist item %s (source %s): status=%s",
            item_id,
            source.name,
            result.get("status"),
        )
        return result
    except Exception as e:
        logger.error(
            "Error processing lighthouse checklist item %s: %s",
            item_id,
            e,
            exc_info=True,
        )
        return None
