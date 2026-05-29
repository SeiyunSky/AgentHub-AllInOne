"""
TraceIdMiddleware 集成测试

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-28
"""

from __future__ import annotations

import logging

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.logging import TraceIdMiddleware
from backend.core.logging import configure_logging


@pytest.fixture(scope="module", autouse=True)
def _setup_logging():
    configure_logging()
    yield


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)

    @app.get("/ping")
    def ping():
        logging.getLogger("test.stdlib").info("from stdlib")
        structlog.get_logger("test.structlog").info("from structlog", op="ping")
        return {"ok": True}

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


def test_response_has_trace_id_header(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    trace_id = resp.headers.get("X-Trace-Id")
    assert trace_id
    assert len(trace_id) == 16


def test_client_supplied_trace_id_is_respected(client):
    resp = client.get("/ping", headers={"X-Trace-Id": "custom-trace-xyz"})
    assert resp.headers.get("X-Trace-Id") == "custom-trace-xyz"


def test_each_request_gets_unique_trace_id(client):
    ids = {client.get("/ping").headers["X-Trace-Id"] for _ in range(5)}
    assert len(ids) == 5


def test_exception_path_does_not_pollute_next_request(client):
    resp_err = client.get("/boom")
    assert resp_err.status_code == 500
    resp_ok = client.get("/ping")
    assert resp_ok.headers.get("X-Trace-Id")


def test_logger_inherits_trace_id_from_contextvars(client):
    fixed_trace = "trace-fixed-001"
    captured: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record):
            captured.append(self.format(record))

    root = logging.getLogger()
    handler = _Capture()
    # 复用 configure_logging 装的 ProcessorFormatter,渲染逻辑跟生产一致
    if root.handlers:
        handler.setFormatter(root.handlers[0].formatter)
    root.addHandler(handler)
    try:
        client.get("/ping", headers={"X-Trace-Id": fixed_trace})
    finally:
        root.removeHandler(handler)

    full_log = "\n".join(captured)
    assert f"trace_id={fixed_trace}" in full_log
    # stdlib + structlog handler 内部各 1 行 + middleware access log 1 行
    assert full_log.count(f"trace_id={fixed_trace}") >= 3
