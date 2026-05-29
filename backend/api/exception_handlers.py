"""
统一异常处理 → 包成 {code, message, data}

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-28
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.schemas.response import envelope_error


logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """注册三类:HTTPException / RequestValidationError / Exception 兜底。"""

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope_error(exc.status_code, str(exc.detail or "")),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = ".".join(str(p) for p in first.get("loc", []))
        msg = first.get("msg", "validation error")
        message = f"{loc}: {msg}" if loc else msg
        return JSONResponse(
            status_code=422,
            content=envelope_error(422, message, data={"errors": errors}),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception in request")
        return JSONResponse(
            status_code=500,
            content=envelope_error(500, f"{type(exc).__name__}: {exc}"),
        )
