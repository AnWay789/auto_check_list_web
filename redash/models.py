import uuid

from logging import Logger

from django.db import models
from django_celery_beat.models import CrontabSchedule

from django.utils import timezone
from datetime import timedelta

from api.wrappers.redash import RedashClient
from api.schemas.redash.redash_schemas import StartJobBody, JobStatusResponse, JobResponse, StartSQLQueryBody

from config.utils.time import default_start_at

logger = Logger(__name__)

class RedashStatuses(models.Model):
    id = models.SmallIntegerField(primary_key=True)
    description = models.CharField(max_length=255)
    is_final = models.BooleanField(default=False)
    is_success = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Статус запроса в Редаше"
        verbose_name_plural = "Статусы запросов в Редаше"

    def __str__(self):
        return f"ID: {self.id}, Description: {self.description}, Is Final: {self.is_final}, Is Success: {self.is_success}"

class RedashSQLs(models.Model):
    """SQL запросы в Редаше"""
    uuid = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    description = models.CharField(max_length=512, blank=True, null=True, help_text="Описание запроса для удобства. Не влияет на выполнение запроса.")
    data_source_id = models.IntegerField()
    parameters = models.JSONField(blank=True, null=True, help_text=("Параметры для запуска запроса (если в нем они есть). Должны быть в формате JSON. "
                                                                    "Например: {\"Маркетплейс\": \"Озон RFBS\", \"РК\": \"ООО \\\"ПУЛЬС Самара\\\"\"}. "
                                                                    "Если параметры не нужны, то можно оставить пустым."))
    query = models.TextField()
    apply_auto_limit = models.BooleanField(default=True)

    is_active = models.BooleanField(default=True)

    crontab = models.ForeignKey(
        CrontabSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # или другое имя
        related_name='redash_sql_crontab_items',
    )

    start_at = models.DateTimeField(default=default_start_at,
                                    help_text="Время запуска задачи. (по стандарту через 5 минут от текущего времени)")

    class Meta:
        verbose_name = "SQL запрос в Редаше"
        verbose_name_plural = "SQL запросы в Редаше"

    def start_query(self):
        if not self.is_active:
            raise ValueError(f"Запрос с UUID {self.uuid} неактивен, что бы запустить запрос - активируйте запрос.")
        body = StartSQLQueryBody(
            data_source_id=self.data_source_id,
            parameters=self.parameters if self.parameters is not None else None,
            query=self.query,
            apply_auto_limit=self.apply_auto_limit
        )
        redash = RedashClient()
        job_response = redash.run_sql_query(body)
        redash_request = RedashRequests.objects.create(redash_sql=self,
                                      status=RedashStatuses.objects.get(id=job_response.job.status),
                                      job_id=job_response.job.id,
                                      error=job_response.job.error,
                                      query_result_id=job_response.job.query_result_id,
                                      result=job_response.job.result)
        redash_request.save()
        return redash_request

    def set_next_run(self):
        """
        Задает следующий интервал запуска задачи.
        """
        
        if self.crontab:
            schedule = self.crontab
            celery_cron = schedule.schedule 
            now_in_cron_tz = timezone.now().astimezone(schedule.timezone)
            next_time = celery_cron.remaining_estimate(now_in_cron_tz)
            if next_time:
                self.start_at = timezone.now() + next_time
                self.save(update_fields=["start_at"])
        else:
            logger.warning(f"RedashSQLs {self.uuid} has no interval or crontab schedule set.")

    def start_query_by_crontab(self):
        """
        Запускает запрос на SQL запрос по crontab.
        """
        if self.start_at <= timezone.now() and self.is_active:
            self.start_query()
            self.set_next_run()
        elif self.start_at > timezone.now() and self.is_active:
            logger.warning(f"RedashSQLs {self.uuid} has not started yet.")
        else:
            logger.warning(f"RedashSQLs {self.uuid} is not active.")

class RedashDashboard(models.Model):
    """Дашборды в Редаше"""
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)

    params = models.JSONField(blank=True, null=True, help_text=("Параметры для запуска запроса. Должны быть в формате JSON."
                                                                "Например: {\"Маркетплейс\": \"Озон RFBS\", \"РК\": \"ООО \\\"ПУЛЬС Самара\\\"\"}"
                                                                "Если параметры не нужны, то можно оставить пустым."))
    apply_auto_limit = models.BooleanField(default=True)
    max_age = models.IntegerField(default=0, help_text=("Указывает макс. возраст кэша (API) в секундах."
                                                        "Если кэш старше, то запрос будет выполнен заново."
                                                        "0 означает, что кэш не будет использоваться."))
    crontab = models.ForeignKey(
        CrontabSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,  # или другое имя
        related_name='redash_dashboard_crontab_items',
    )

    start_at = models.DateTimeField(default=default_start_at,
                                    help_text="Время запуска задачи. (по стандарту через 5 минут от текущего времени)")

    class Meta:
        verbose_name = "Дашборд в Редаше"
        verbose_name_plural = "Дашборды в Редаше"

    def __str__(self):
        return f"ID: {self.id}, Name: {self.name}"

    def start_query(self) -> "RedashRequests":
        """
        Запускает запрос на дашборде. Создает запись в таблице RedashRequests с статусом дашборда 
        """
        if not self.is_active:
            raise ValueError(f"Дашборд с ID {self.id} неактивен, что бы запустить запрос - активируйте дашборд.")
        body = StartJobBody(id=str(self.id), 
                            parameters=self.params if self.params else None,
                            apply_auto_limit=True,
                            max_age=0)
        
        redash = RedashClient()
        job_response = redash.start_dashboard_query(body)
        # Сохраняем результат в RedashRequests
        redash_request = RedashRequests.objects.create(dashboard=self,
                                      status=RedashStatuses.objects.get(id=job_response.job.status),
                                      job_id=job_response.job.id,
                                      error=job_response.job.error,
                                      query_result_id=job_response.job.query_result_id,
                                      result=job_response.job.result)
        redash_request.save()
        return redash_request
    
    def set_next_run(self):
        """
        Задает следующий интервал запуска задачи.
        """
        
        if self.crontab:
            schedule = self.crontab
            celery_cron = schedule.schedule
            now_in_cron_tz = timezone.now().astimezone(schedule.timezone)
            next_time = celery_cron.remaining_estimate(now_in_cron_tz)
            if next_time:
                self.start_at = timezone.now() + next_time
                self.save(update_fields=["start_at"])
        else:
            logger.warning(f"CheckListItem {self.id} has no interval or crontab schedule set.")

    def start_query_by_crontab(self):
        """
        Запускает запрос на дашборде по crontab.
        """
        if self.start_at <= timezone.now() and self.is_active:
            self.start_query()
            self.set_next_run()
        elif self.start_at > timezone.now() and self.is_active:
            logger.warning(f"RedashDashboard {self.id} has not started yet.")
        else:
            logger.warning(f"RedashDashboard {self.id} is not active.")

class RedashRequests(models.Model):
    """Запущенные запросы в Редаше"""
    redash_sql = models.ForeignKey(RedashSQLs, on_delete=models.CASCADE, null=True)
    dashboard = models.ForeignKey(RedashDashboard, on_delete=models.CASCADE, null=True)
    status = models.ForeignKey(RedashStatuses, on_delete=models.CASCADE)
    
    job_id = models.CharField(max_length=255, primary_key=True)
    error = models.TextField(blank=True, null=True)
    query_result_id = models.IntegerField(blank=True, null=True)

    result = models.JSONField(blank=True, null=True)

    date_request = models.DateTimeField(auto_now_add=True)
    date_update = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Запущенный запрос в Редаше"
        verbose_name_plural = "Запущенные запросы в Редаше"

    def __str__(self):
        if self.dashboard:
            return f"ID: {self.job_id}, Dashboard: {self.dashboard.name}, Error: {self.error}, Query Result ID: {self.query_result_id}"
        if self.redash_sql:
            return f"ID: {self.job_id}, Dashboard: {self.redash_sql}, Error: {self.error}, Query Result ID: {self.query_result_id}"
    
    def cource(self):
        if self.dashboard:
            return f"Dashboard: {self.dashboard.name}"
        if self.redash_sql:
            return f"SQL: {self.redash_sql.description}"
        return f"Unknown source"
    
    def clear_old(self, days: int = 2):
        """
        Очищает старые запросы, которые были созданы более days (по дефолту 2) дней назад.
        """
        if self.date_request < (timezone.now() - timezone.timedelta(days=days)):
            self.delete()

    def refresh(self):
        """
        Обновляет статус запроса: опрашивает Redash API и при готовности результата подтягивает данные.
        """
        if self.status.is_final:
            raise ValueError(f"Статус запроса с ID {self.job_id} является финальным, обновление результата не требуется.")

        redash = RedashClient()
        # Сначала получаем актуальный статус джоба из Redash (GET /api/jobs/{id})
        job_status_response = redash.get_query_status(
            JobStatusResponse(job=JobResponse(id=self.job_id, updated_at=0, status=0, error=None, result=None, query_result_id=None))
        )
        # В ответе jobs API query_result_id может приходить как result (int)
        if job_status_response.job.query_result_id is None and isinstance(job_status_response.job.result, int):
            job_status_response = JobStatusResponse(
                job=JobResponse(
                    id=job_status_response.job.id,
                    updated_at=job_status_response.job.updated_at,
                    status=job_status_response.job.status,
                    error=job_status_response.job.error,
                    result=job_status_response.job.result,
                    query_result_id=job_status_response.job.result,
                )
            )
        # Подтягиваем полный результат только если джоб завершён и есть query_result_id
        if job_status_response.job.query_result_id:
            job_status_response = redash.get_query_result(job_status_response)

        self.status = RedashStatuses.objects.get(id=job_status_response.job.status)
        self.error = job_status_response.job.error
        self.query_result_id = job_status_response.job.query_result_id
        self.result = job_status_response.job.result
        self.save(update_fields=["status", "error", "query_result_id", "result"])


