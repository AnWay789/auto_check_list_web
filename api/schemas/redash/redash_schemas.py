from pydantic import BaseModel

class StartJobBody(BaseModel):
    id: str
    parameters: dict | None = None
    apply_auto_limit: bool | None = True
    max_age: int | None = 0

class JobResponse(BaseModel):
    id: str
    updated_at: int
    status: int
    error: str | None = None
    # GET /api/jobs/{id} возвращает result как int (query_result_id), GET /api/query_results/{id} — как dict
    result: dict | int | None = None
    query_result_id: int | None = None


class JobStatusResponse(BaseModel):
    job: JobResponse

class StartSQLQueryBody(BaseModel):
    data_source_id: int
    parameters: dict | None = None
    query: str
    apply_auto_limit: bool | None = True
