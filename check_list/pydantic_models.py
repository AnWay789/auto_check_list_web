import uuid
from pydantic import BaseModel


class DashboardModel(BaseModel):
    """
    Модель дашборда для отправки во внешний сервис (телеграм-бот).
    event_uuid передаём как hex-строку (uuid.uuid4().hex), т.к. фронтенд работает с такими значениями.
    """

    event_uuid: str  # hex-строка UUID (uuid.uuid4().hex)
    dashboard_uid: str
    name: str
    description: str | None = None
    real_url: str
    fake_url: str
    time_for_check: int


