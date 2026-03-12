# Договоренности об использовании API с КЦ нет, но если такая надобность понадобится - функционал имеется

import logging
from django.core.exceptions import ObjectDoesNotExist
from ..api_app import oe_api
from order_errors.models import OrderError

logger = logging.getLogger(__name__)

@oe_api.get("/order_error/{number}/reissue/")
def patch_order_error_reissue(request, number: int):
    """
    Обновление заказа: заказ был переоформлен.
    """
    try:
        order = OrderError.objects.get(number=number)
        order.has_been_reissued = True
        order.save()
    except ObjectDoesNotExist:
        logger.error(f"Order {number} not found")
        return {"status": "error", "message": "Order not found"}, 404
    return {"status": "success"}

@oe_api.get("/order_error/{number}/not_reissue/")
def patch_order_error_not_reissue(request, number: int):
    """
    Обновление заказа: заказ не был переоформлен.
    """
    try:
        order = OrderError.objects.get(number=number)
        order.has_been_reissued = False
        order.save()
    except ObjectDoesNotExist:
        logger.error(f"Order {number} not found")
        return {"status": "error", "message": "Order not found"}, 404
    return {"status": "success"}
