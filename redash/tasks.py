import logging
from config.celery import app
from redash.models import RedashSQLs, RedashDashboard, RedashRequests

logger = logging.getLogger(__name__)

@app.task
def start_redash_dashboards():
    """
    Запускает запросы дашбордов в Редаше по crontab.
    """
    for dashboard in RedashDashboard.objects.filter(is_active=True).all():
        try:
            dashboard.start_query_by_crontab()
        except Exception as e:
            logger.error(f"Error starting dashboard {dashboard.id}: {e}")

@app.task
def start_redash_sqls():
    """
    Запускает запросы SQL в Редаше по crontab.
    """
    for sql in RedashSQLs.objects.filter(is_active=True).all():
        try:
            sql.start_query_by_crontab()
        except Exception as e:
            logger.error(f"Error starting query {sql.uuid}: {e}")

@app.task
def refresh_all_requests():
    for request in RedashRequests.objects.filter(status__is_final=False).all():
        try:
            request.refresh()
        except Exception as e:
            logger.error(f"Error refreshing request {request.job_id}: {e}")
