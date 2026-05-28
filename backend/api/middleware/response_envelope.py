"""
ResponseEnvelopeMiddleware —— JSON 响应自动包成 {code, message, data}

跳过条件:
- StreamingResponse(SSE / 大文件):协议要求 raw,不包
- 已经是 envelope 形态:不重复包
- 非 application/json:不包

异常包装走 api/exception_handlers.py 注册的 exception_handler。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-28
"""

from __future__ import annotations

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from backend.schemas.response import envelope_success


logger = logging.getLogger(__name__)


_ENVELOPE_KEYS = {"code", "message", "data"}


class ResponseEnvelopeMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        if isinstance(response, StreamingResponse):
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        chunks = [chunk async for chunk in response.body_iterator]
        body_bytes = b"".join(chunks)
        if not body_bytes:
            return response

        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            logger.warning(
                "response body claims JSON but cannot parse, leaving untouched: %s",
                request.url.path,
            )
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=content_type,
            )

        if (
            isinstance(payload, dict)
            and _ENVELOPE_KEYS.issubset(payload.keys())
        ):
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=content_type,
            )

        if 200 <= response.status_code < 300:
            wrapped = envelope_success(payload)
        else:
            # 错误响应:detail 进 message,原 payload 进 data 保留排查信息
            # (业务绕开 HTTPException 直接返 4xx 时,原 errors 字段不丢失)
            if isinstance(payload, dict):
                detail = payload.get("detail", "")
                data = payload if not detail else None
            else:
                detail = str(payload)
                data = None
            wrapped = {"code": response.status_code, "message": str(detail), "data": data}

        new_body = json.dumps(wrapped, ensure_ascii=False).encode("utf-8")
        new_headers = dict(response.headers)
        new_headers["content-length"] = str(len(new_body))

        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=new_headers,
            media_type=content_type,
        )
