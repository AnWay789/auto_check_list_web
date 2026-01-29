import logging
from config.celery import app
from django.utils import timezone

from check_list.models import CheckEvents

logger = logging.getLogger(__name__)

@app.task
def clean_old_events(days: int=180, batch_size: int=10000):
    """
    Периодическая задача для очистки старых событий проверки дашбордов.
    Удаляет события, которые старше определенного времени.
    """
    try:
        # Определяем пороговое время для удаления (например, 180 дней назад)
        threshold_time = timezone.now() - timezone.timedelta(days=days)
        
        while True:
            # Выбрать не более batch_size первичных ключей подходящих записей
            batch_pks = list(
                CheckEvents.objects.filter(event_time__lt=threshold_time)
                .values_list("uuid", flat=True)[:batch_size]
            )
            # Если записей больше нет, выходим из цикла
            if not batch_pks:
                break
            # Удалить только эту порцию
            deleted_count, _ = CheckEvents.objects.filter(uuid__in=batch_pks).delete()
            logger.info(f"Cleaned up {deleted_count} old check events.")

    except Exception as e:
        logger.error(f"Error while cleaning old check events: {e}")
