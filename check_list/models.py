from logging import Logger

from datetime import timedelta
from django.utils import timezone
from django.db import models

from django_celery_beat.models import IntervalSchedule, CrontabSchedule
from celery.schedules import crontab as celery_crontab

logger = Logger(__name__)

class DashType(models.Model):
    name = models.TextField()

class Dashboard(models.Model):
    uid = models.CharField(unique=True, max_length=128)
    name = models.CharField(max_length=255)
    url = models.URLField()
    time_for_check = models.IntegerField(help_text="Время в минутах для проверки дашборда")

    def __str__(self):
        return self.name

class CheckListItem(models.Model):
    id = models.AutoField(primary_key=True)
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='checklist_items'
    )
    description = models.TextField(null=True, blank=True, 
                                   help_text="Описание задачи для проверки дашборда.\nМожно писать в Telegram MarkdownV2 формате. \n```блок кода``` \n`код` \n*жирный* \n_курсив_ \n__подчёркнутый__ \n~зачёркнутый~ \n[ссылка](http://example.com) \n\n%без форматирования%")
    interval = models.ForeignKey(
        IntervalSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='check_list_interval_items',
    )
    crontab = models.ForeignKey(
        CrontabSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # или другое имя
        related_name='check_list_crontab_items',
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
    uuid = models.UUIDField(primary_key=True)
    # dash_type = models.ForeignKey(
    #     DashType,
    #     on_delete=models.SET_NULL,
    #     null=True
    # )
    dashboard = models.ForeignKey(
        Dashboard,
        on_delete=models.CASCADE,
        related_name='history_dashboards'
    )
    event_time = models.DateTimeField(auto_now_add=True)
    check_time = models.DateTimeField(null=True, blank=True)
    no_problem = models.BooleanField(default=True)
    checked = models.BooleanField(default=False)

    def __str__(self):
        return f"History for {self.dashboard.name} at {self.event_time}"
