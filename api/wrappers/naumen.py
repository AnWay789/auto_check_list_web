import logging

from httpx import Client, BasicAuth

from config.settings import NAUMEN_BASE_URL, NAUMEN_PROJECT_ID, NAUMEN_AUTH_NAME, NAUMEN_AUTH_PASSWORD

from api.schemas.naumen.naumen_schema import PhoneNumber, CustomForm, CustomFormDefault, CustomForm, NaumenErrorRequest

from order_errors.models import OrderError

logger = logging.getLogger(__name__)


class NaumenClient():

    def __init__(self, base_url: str | None = None, project_id: str | None = None, username: str | None = None, password: str | None = None):
        self.base_url = base_url if base_url else NAUMEN_BASE_URL
        self.project_id = project_id if project_id else NAUMEN_PROJECT_ID
        self.username = username if username else NAUMEN_AUTH_NAME
        self.password = password if password else NAUMEN_AUTH_PASSWORD

    def create_case(self, cases: list[NaumenErrorRequest], project_id: str | None = None) -> list | None:
        if self.username and self.password:
            responses = []
            for case_data in cases:
                url = f"{self.base_url}/api/v2/projects/{project_id if project_id else self.project_id}/cases"
                response = Client().post(url, json=case_data.model_dump(mode='json'), auth=BasicAuth(username=self.username, password=self.password))
                if not response.is_success:
                    try:
                        body = response.text
                    except Exception:
                        body = "(не удалось прочитать тело ответа)"
                    logger.error(
                        "Naumen API error: %s %s, response: %s",
                        response.status_code,
                        response.reason_phrase or "",
                        body[:2000] if body else "(пусто)",
                    )
                response.raise_for_status()
                responses.append(response.json())
            return responses
        else:
            raise ValueError("Для NaumenClient не определены username и password")
