from typing import Any
from httpx import Client

from config.settings import REDASH_API_KEY, REDASH_BASE_URL

from api.schemas.redash.redash_schemas import StartJobBody, StartSQLQueryBody, JobStatusResponse, JobResponse


class RedashClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key else REDASH_API_KEY
        self.base_url = base_url if base_url else REDASH_BASE_URL

    def start_dashboard_query(self, body: StartJobBody) -> JobStatusResponse:
        url = f"{self.base_url}/api/queries/{body.id}/results"
        headers = {"Authorization": f"Key {self.api_key}"}

        response = Client().post(url, headers=headers, json=body.model_dump(exclude_none=True))
        response.raise_for_status()
        return JobStatusResponse.model_validate(response.json())

    def get_query_status(self, job_resp: JobStatusResponse) -> JobStatusResponse:
        url = f"{self.base_url}/api/jobs/{job_resp.job.id}"
        headers = {"Authorization": f"Key {self.api_key}"}
        response = Client().get(url, headers=headers)
        response.raise_for_status()
        return JobStatusResponse.model_validate(response.json())

    def get_query_result(self, job_resp: JobStatusResponse) -> JobStatusResponse:
        if not job_resp.job.query_result_id:
            raise ValueError("Query result ID is missing in the job response.")
        url = f"{self.base_url}/api/query_results/{job_resp.job.query_result_id}"
        headers = {"Authorization": f"Key {self.api_key}"}
        response = Client().get(url, headers=headers)
        response.raise_for_status()
        # GET /api/query_results/{id} возвращает { "query_result": { "data": { "rows": [...] }, ... } },
        # а не { "job": { ... } } — подставляем тело ответа в job.result для совместимости с вызывающим кодом
        data = response.json()
        return JobStatusResponse(
            job=JobResponse(
                id=job_resp.job.id,
                updated_at=0,
                status=job_resp.job.status or 0,
                error=job_resp.job.error,
                result=data,
                query_result_id=job_resp.job.query_result_id,
            )
        )

    def run_sql_query(self, body: StartSQLQueryBody) -> JobStatusResponse:
        url = f"{self.base_url}/api/query_results"
        headers = {"Authorization": f"Key {self.api_key}"}
        response = Client().post(url, headers=headers, json=body.model_dump(exclude_none=True))
        response.raise_for_status()
        return JobStatusResponse.model_validate(response.json())

