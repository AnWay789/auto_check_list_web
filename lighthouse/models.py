import logging

from datetime import timedelta
from django.utils import timezone
from django.db import models

from django_celery_beat.models import IntervalSchedule, CrontabSchedule
from celery.schedules import crontab as celery_crontab

logger = logging.getLogger(__name__)


class Source(models.Model):
    name = models.CharField(max_length=100)
    url = models.URLField()
    headers = models.JSONField(default=None, blank=True, null=True,
                               help_text=("Произвольные заголовки для запроса Lighthouse."
                                                                 "Формат: {\"Header-Name\": \"Header Value\"}"
                                                                 "Ecсли заголовки не нужны, оставить null."))
    metadata = models.JSONField(
        blank=True,
        null=True,
        default=(
            {
                "project": "not set",
                "page_type": "not set"
            }
        ),
        help_text=("Произвольные метаданные для ELK (например project, page_type)."
                   "Формат: {\"key1\": \"value1\", \"key2\": \"value2\"}")
    )
    description = models.TextField(null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class CheckListItem(models.Model):
    id = models.AutoField(primary_key=True)
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name='checklist_items'
    )
    description = models.TextField(null=True, blank=True)
    interval = models.ForeignKey(
        IntervalSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=("Интервал запуска задачи.\n\n\n"
                    "Один из interval или crontab должен быть задан. Если заданы оба, приоритет будет у interval.")
    )
    crontab = models.ForeignKey(
        CrontabSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # или другое имя
        help_text=("Расписание запуска задачи по crontab.\n\n\n"
                    "Один из interval или crontab должен быть задан. Если заданы оба, приоритет будет у interval.")
    )
    is_active = models.BooleanField(default=True)
    start_at = models.DateTimeField(default=timezone.now()+timedelta(minutes=5),
                                    help_text="Время запуска задачи. (по стандарту через 5 минут от текущего времени)")

    def set_next_run(self):
        """
        Задает следующий интервал запуска задачи.
        """
        if self.interval:
            schedule = self.interval
            delta = timedelta(**{schedule.period: schedule.every})
            if delta:
                self.start_at += delta
                self.save(update_fields=["start_at"])
        
        elif self.crontab:
            schedule = self.crontab
            celery_cron = schedule.schedule
            now_in_cron_tz = timezone.now().astimezone(schedule.timezone)
            next_time = celery_cron.remaining_estimate(now_in_cron_tz)
            if next_time:
                self.start_at = timezone.now() + next_time
                self.save(update_fields=["start_at"])
        else:
            logger.warning(f"CheckListItem {self.id} has no interval or crontab schedule set.")

    def __str__(self):
        return self.description

class CheckEvents(models.Model):
    id = models.AutoField(primary_key=True)
    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name='check_events',
    )
    event_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=32, blank=True, null=True)
    metrics = models.JSONField(
        blank=True,
        null=True,
        help_text="Метрики Lighthouse: fcp_ms, fcp_s, tbt_ms, tbt_s, si_ms, si_s, lcp_ms, lcp_s, cls.",
    )
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"History for {self.source.name} at {self.event_time}"
