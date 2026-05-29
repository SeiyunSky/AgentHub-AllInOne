"""
统一 API 响应包装 schema

code = HTTP status code(200/400/404/422/500)
message = 错误时填 detail,成功时空字符串
data = 业务原响应体(object / array / scalar / null)

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-28
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    供 OpenAPI 文档 / 前端生成 TypeScript 类型用的包装模型。
    middleware 直接用 envelope_success / envelope_error helpers 构造 dict,不走本类。
    """
    code: int = Field(description="状态码,与 HTTP status 一致(200/400/404/422/500)")
    message: str = Field(default="", description="错误时填详细原因,成功时空")
    data: Optional[T] = Field(default=None, description="业务响应体,错误时为 null")


def envelope_success(data: Any) -> dict:
    return {"code": 200, "message": "", "data": data}


def envelope_error(code: int, message: str, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}
