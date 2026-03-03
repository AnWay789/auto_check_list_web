import logging

from datetime import timedelta
from django.utils import timezone
from django.db import models

from django_celery_beat.models import IntervalSchedule, CrontabSchedule
from celery.schedules import crontab as celery_crontab

from config.utils.time import default_start_at

logger = logging.getLogger(__name__)


def default_source_metadata():
    return {"project": "not set", "page_type": "not set"}


class Source(models.Model):
    name = models.CharField(max_length=100)
    url = models.URLField()
    headers = models.JSONField(default=None, blank=True, null=True,
                               help_text=("Произвольные заголовки для запроса Lighthouse."
                                                                 "Формат: {\"Header-Name\": \"Header Value\"}"
                                                                 "Ecли заголовки не нужны, оставить null."))
    metadata = models.JSONField(
        blank=True,
        null=True,
        default=default_source_metadata,
        help_text=("Произвольные метаданные для ELK (например project, page_type)."
                   "Формат: {\"key1\": \"value1\", \"key2\": \"value2\"}")
    )
    description = models.TextField(null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Источник Lighthouse"
        verbose_name_plural = "Источники Lighthouse"

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
    start_at = models.DateTimeField(default=default_start_at,
                                    help_text="Время запуска задачи. (по стандарту через 5 минут от текущего времени)")

    class Meta:
        verbose_name = "Элемент расписания Lighthouse"
        verbose_name_plural = "Элементы расписания Lighthouse"

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
        help_text="Метрики Lighthouse: fcp_ms, fcp_s, tbt_ms, tbt_s, si_ms, si_s, lcp_ms, lcp_s, cls, dns_ms, dns_s, tcp_ms, tcp_s.",
    )
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "История Lighthouse"
        verbose_name_plural = "Истории Lighthouse"

    def __str__(self):
        return f"History for {self.source.name} at {self.event_time}"

    def clear_old(self, days: int = 2):
        """
        Очищает старые запросы, которые были созданы более days (по дефолту 2) дней назад.
        """
        if self.event_time < (timezone.now() - timezone.timedelta(days=days)):
            self.delete()
