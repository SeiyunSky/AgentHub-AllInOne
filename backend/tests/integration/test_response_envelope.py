"""
ResponseEnvelopeMiddleware + 异常处理器集成测试

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-28
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.api.exception_handlers import register_exception_handlers
from backend.api.middleware.response_envelope import ResponseEnvelopeMiddleware


class _Item(BaseModel):
    name: str
    qty: int


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(ResponseEnvelopeMiddleware)
    register_exception_handlers(app)

    @app.get("/dict")
    def get_dict():
        return {"foo": "bar", "n": 1}

    @app.get("/list")
    def get_list():
        return [{"id": 1}, {"id": 2}]

    @app.get("/null")
    def get_null():
        return None

    @app.get("/scalar")
    def get_scalar():
        return 42

    @app.get("/notfound")
    def not_found():
        raise HTTPException(status_code=404, detail="资源不存在")

    @app.post("/validate")
    def validate(item: _Item):
        return item.model_dump()

    @app.get("/boom")
    def boom():
        raise RuntimeError("internal crash")

    @app.get("/sse")
    async def sse():
        async def _gen():
            yield {"event": "ping", "data": "1"}
            yield {"event": "ping", "data": "2"}
        return EventSourceResponse(_gen())

    return TestClient(app, raise_server_exceptions=False)


def test_dict_response_wrapped(client):
    resp = client.get("/dict")
    assert resp.status_code == 200
    assert resp.json() == {"code": 200, "message": "", "data": {"foo": "bar", "n": 1}}


def test_list_response_wrapped_with_array_data(client):
    body = client.get("/list").json()
    assert body["code"] == 200
    assert body["data"] == [{"id": 1}, {"id": 2}]


def test_null_response_wrapped(client):
    assert client.get("/null").json() == {"code": 200, "message": "", "data": None}


def test_scalar_response_wrapped(client):
    assert client.get("/scalar").json() == {"code": 200, "message": "", "data": 42}


def test_http_exception_wrapped(client):
    resp = client.get("/notfound")
    assert resp.status_code == 404
    body = resp.json()
    assert body == {"code": 404, "message": "资源不存在", "data": None}


def test_validation_error_wrapped(client):
    resp = client.post("/validate", json={"name": "x"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == 422
    assert "qty" in body["message"]
    assert "errors" in body["data"]


def test_unhandled_exception_wrapped_as_500(client):
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == 500
    assert "RuntimeError" in body["message"]
    assert body["data"] is None


def test_sse_response_not_wrapped(client):
    """SSE 流式响应必须保持 raw 协议,不能被 JSON 包装。"""
    with client.stream("GET", "/sse") as resp:
        assert "text/event-stream" in resp.headers.get("content-type", "")
        text = b"".join(resp.iter_bytes()).decode("utf-8")
        assert "event: ping" in text
        assert "data: 1" in text


def test_already_wrapped_payload_not_double_wrapped():
    app = FastAPI()
    app.add_middleware(ResponseEnvelopeMiddleware)

    @app.get("/wrapped")
    def already_wrapped():
        return {"code": 418, "message": "I'm a teapot", "data": {"x": 1}}

    body = TestClient(app).get("/wrapped").json()
    assert body == {"code": 418, "message": "I'm a teapot", "data": {"x": 1}}
