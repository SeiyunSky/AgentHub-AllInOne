"""
api/middleware/logging —— 请求日志 + trace_id contextvars 绑定

trace_id 来源优先级:
1. 请求 header X-Trace-Id(微服务 / 网关 / 前端可主动传递,服务端不覆盖)
2. 服务端生成 uuid.uuid4().hex[:16]

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-28
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars


logger = logging.getLogger(__name__)


_TRACE_ID_HEADER = "X-Trace-Id"


class TraceIdMiddleware(BaseHTTPMiddleware):
    """请求入口绑 trace_id 到 contextvars,响应回写 X-Trace-Id header。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get(_TRACE_ID_HEADER) or uuid.uuid4().hex[:16]
        bind_contextvars(trace_id=trace_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request unhandled exception method=%s path=%s elapsed_ms=%.1f",
                request.method, request.url.path, elapsed_ms,
            )
            raise
        else:
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers[_TRACE_ID_HEADER] = trace_id
            logger.info(
                "request method=%s path=%s status=%d elapsed_ms=%.1f",
                request.method, request.url.path, response.status_code, elapsed_ms,
            )
            return response
        finally:
            clear_contextvars()
