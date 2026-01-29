from datetime import datetime
from ninja import Schema


class CheckListColback(Schema):
    """
    Схема для обратного вызова (ответа) по элементу чеклиста.
    Фронтенд передаёт идентификатор события как hex-строку UUID (uuid.uuid4().hex).
    """

    event_uuid: str  # hex-строка UUID
    problem: bool
