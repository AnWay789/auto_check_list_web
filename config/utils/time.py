from django.utils import timezone
from datetime import datetime, timedelta

def default_start_at(time_delta: int = 5) -> datetime:
    """
    Возвращает время сейчас + time_delta

    Args:
        time_delta(int): Дельта времени в минутах которая будет добавлена к текущему времени
    """
    return timezone.now() + timedelta(minutes=time_delta)
