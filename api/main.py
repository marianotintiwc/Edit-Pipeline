from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from api.app_config import get_app_config
from api.routes.batches import router as batches_router
from api.routes.config import router as config_router
from api.routes.jobs import router as jobs_router
from api.routes.presets import router as presets_router
from api.routes.profiles import router as profiles_router
from api.routes.runs import router as runs_router

config = get_app_config()
logger = logging.getLogger("api")

app = FastAPI(title=config.api_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(presets_router, prefix="/api")
app.include_router(profiles_router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(batches_router, prefix="/api")


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    started_at = perf_counter()
    response = await call_next(request)
    elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request_complete method=%s path=%s status=%s elapsed_ms=%.2f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
