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


def _make_json_safe(obj):
    """递归把 dict / list 里不可 JSON 序列化的值降级成 str。

    pydantic v2 errors() 的 ctx 字段常带原生 Exception 对象(如 model_validator 抛的
    ValueError),直接进 JSONResponse 会炸。这里只兜底一层,保证响应能发出去。
    """
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


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
        # pydantic v2 errors() 里的 ctx 字段经常带原生 Exception(如 model_validator 抛的
        # ValueError),JSONResponse 序列化会炸 "Object of type X is not JSON serializable"。
        # 整体过一遍把不可序列化的值降级为 str,保留诊断信息又能正常返回。
        safe_errors = _make_json_safe(errors)
        return JSONResponse(
            status_code=422,
            content=envelope_error(422, message, data={"errors": safe_errors}),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception in request")
        return JSONResponse(
            status_code=500,
            content=envelope_error(500, f"{type(exc).__name__}: {exc}"),
        )
