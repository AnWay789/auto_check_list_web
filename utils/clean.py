"""
Утилита и таска для вызова clear_old() по всем моделям, у которых определён этот метод.
"""
import logging

from django.apps import apps

from config.celery import app

logger = logging.getLogger(__name__)


def get_models_with_clear_old():
    """
    Возвращает список моделей, у которых есть метод clear_old.
    """
    result = []
    for model in apps.get_models():
        if hasattr(model, "clear_old") and callable(getattr(model, "clear_old")):
            result.append(model)
    return result


def run_clear_old_for_all_models(days: int | None = None) -> dict[str, int]:
    """
    Для каждой модели с методом clear_old обходит все объекты и вызывает
    instance.clear_old(days). Если days не передан, у каждой модели
    используется свой дефолт из сигнатуры clear_old.

    Возвращает словарь: { 'app_label.ModelName': количество удалённых записей }.
    """
    deleted_by_model = {}
    models = get_models_with_clear_old()

    for model in models:
        label = f"{model._meta.app_label}.{model._meta.model_name}"
        try:
            count_before = model.objects.count()
            for obj in model.objects.all():
                if days is not None:
                    obj.clear_old(days=days)
                else:
                    obj.clear_old()
            count_after = model.objects.count()
            deleted = count_before - count_after
        except Exception as e:
            logger.exception("Ошибка при clear_old для модели %s: %s", label, e)
            deleted = -1
        deleted_by_model[label] = deleted
        if deleted > 0:
            logger.info("clear_old для %s: удалено записей %s", label, deleted)

    return deleted_by_model


@app.task(name="utils.clean.run_clear_old")
def run_clear_old_task(days: int | None = None) -> dict[str, int]:
    """
    Периодическая задача: вызывает run_clear_old_for_all_models(days).
    Если days не передан, у каждой модели используется свой дефолт из clear_old.
    """
    return run_clear_old_for_all_models(days=days)
