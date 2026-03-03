import logging

from config.celery import app

from order_errors.redash_naumen_sync import RedashNaumenSync

logger = logging.getLogger(__name__)

@app.task
def save_error_orders(dashboard_id: int):
    saved = RedashNaumenSync().save_orders_from_dashboard_responce(dashboard_id)
    logger.info("save_error_orders завершён: saved=%s", saved['saved'])

@app.task
def send_error_orders():
    sent = RedashNaumenSync().send_orders_to_naumen()
    logger.info("send_error_orders завершён: sent=%s", sent['sent'])

@app.task
def sync_order_errors_and_send_to_naumen(dashboard_id: int):
    """
    Синхронизация заказов с ошибками из дашборда Redash и отправка неотправленных в Наумен.
    dashboard_id — ID дашборда Redash с запросом по ошибочным заказам.
    """
    try:
        sync = RedashNaumenSync()
        result = sync.sync_and_send_errors(dashboard_id=dashboard_id)
        logger.info("sync_order_errors_and_send_to_naumen завершён: saved=%s, sent=%s", result["saved"], result["sent"])
        return result
    except Exception as e:
        logger.exception("Ошибка в sync_order_errors_and_send_to_naumen (dashboard_id=%s): %s", dashboard_id, e)
        raise
