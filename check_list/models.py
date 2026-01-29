from datetime import timedelta
from django.utils import timezone
from django.db import models
from django_celery_beat.models import IntervalSchedule, CrontabSchedule
from celery.schedules import crontab as celery_crontab

# Create your models here.
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
    description = models.TextField(null=True, blank=True)
    interval = models.ForeignKey(
        IntervalSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    crontab = models.ForeignKey(
        CrontabSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # или другое имя
    )
    is_active = models.BooleanField(default=True)
    start_at = models.DateTimeField()

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
            celery_cron = celery_crontab(
                minute=schedule.minute,
                hour=schedule.hour,
                day_of_week=schedule.day_of_week,
                day_of_month=schedule.day_of_month,
                month_of_year=schedule.month_of_year,
            )
            next_time = celery_cron.remaining_estimate(timezone.now())
            if next_time:
                self.start_at = timezone.now() + next_time
                self.save(update_fields=["start_at"])

    def __str__(self):
        return self.description

class CheckEvents(models.Model):
    uuid = models.UUIDField(primary_key=True)
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
