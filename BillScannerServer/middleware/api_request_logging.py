

from __future__ import annotations

import logging
import os
import time
from typing import Callable, Optional, Set

from fastapi import Request
from starlette.responses import Response as StarletteResponse

from database import SessionLocal
from models.api_request_log import ApiRequestLog

log = logging.getLogger("api_request_log")


_DEFAULT_SKIP_PATHS = "/docs,/redoc,/openapi.json,/favicon.ico"
SKIP_PATHS: Set[str] = set(
    p.strip()
    for p in os.environ.get("API_LOG_SKIP_PATHS", _DEFAULT_SKIP_PATHS).split(",")
    if p.strip()
)


_LOG_OPTIONS = os.environ.get("API_LOG_LOG_OPTIONS", "").strip().lower() in {
    "1",
    "true",
    "yes",
}

_FAILURE_BODY_MAX = 8000
_TRACE_MAX = 16000


def _should_skip(request: Request) -> bool:
    if request.method == "OPTIONS" and not _LOG_OPTIONS:
        return True
    path = request.url.path
    if path in SKIP_PATHS:
        return True
    return False


def _client_ip(request: Request) -> Optional[str]:
    if request.client:
        return request.client.host
    return None


def _failure_body_preview(response: StarletteResponse) -> Optional[str]:
    try:
        body = getattr(response, "body", None)
        if not body:
            return None
        if isinstance(body, memoryview):
            body = body.tobytes()
        raw = bytes(body)[:_FAILURE_BODY_MAX]
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


def _server_traceback(request: Request) -> Optional[str]:
    tb = getattr(request.state, "server_traceback", None)
    if not tb:
        return None
    s = str(tb)
    if len(s) > _TRACE_MAX:
        return s[:_TRACE_MAX] + "\n... [truncated]"
    return s


def persist_request_log(
    *,
    method: str,
    path: str,
    query_string: Optional[str],
    client_ip: Optional[str],
    user_agent: Optional[str],
    status_code: int,
    duration_ms: float,
    failure_response_body: Optional[str],
    server_traceback: Optional[str],
) -> None:
    is_failure = status_code >= 400
    db = SessionLocal()
    try:
        row = ApiRequestLog(
            method=method,
            path=path[:2048] if path else "",
            query_string=query_string or None,
            client_ip=(client_ip or "")[:128] or None,
            user_agent=user_agent,
            status_code=status_code,
            duration_ms=duration_ms,
            is_failure=is_failure,
            failure_response_body=failure_response_body if is_failure else None,
            server_traceback=server_traceback if is_failure else None,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Failed to persist ApiRequestLog — logging must not break responses")
    finally:
        db.close()


async def api_request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], StarletteResponse],
) -> StarletteResponse:
    if _should_skip(request):
        return await call_next(request)

    t0 = time.perf_counter()
    method = request.method
    path = request.url.path
    query_string = request.url.query or None
    ua = request.headers.get("user-agent")
    ip = _client_ip(request)

    response = await call_next(request)
    status_code = response.status_code
    duration_ms = (time.perf_counter() - t0) * 1000.0

    fail_body: Optional[str] = None
    if status_code >= 400:
        fail_body = _failure_body_preview(response)

    trace = _server_traceback(request)

    log.info(
        "%s %s → %s (%.0f ms)",
        method,
        path,
        status_code,
        duration_ms,
    )

    persist_request_log(
        method=method,
        path=path,
        query_string=query_string,
        client_ip=ip,
        user_agent=ua,
        status_code=status_code,
        duration_ms=duration_ms,
        failure_response_body=fail_body,
        server_traceback=trace,
    )

    return response
