"""
api/v1/preview.py —— 部署应用反向代理

把 GET/POST/... /preview/{conv_id}/{path} 的请求转发到该会话的容器
内部 IP:8000,让用户能通过 AgentHub 后端域名直接访问 deploy_app 起的应用。

设计要点:
- 路由不带 /api/v1 前缀(用户分享的 URL 是 http://host/preview/xxx/,
  浏览器直接访问的)。main.py 注册时不加 prefix。
- 容器内部 IP 由 docker_runtime.get_container 返回(走 docker bridge 网络,
  端口不映射到 host,host 只能通过容器 IP 访问)。
- 每次转发调 docker_runtime.touch(conv_id) 刷新最后访问时间,
  闲置回收依赖这个时间戳。
- WebSocket / SSE 转发 MVP 不做;httpx.stream 流式转发支持下载大文件。
- conv_id 鉴权暂不做(MVP) [TODO/perm]:理论上要校验 user_id 拥有该 conversation,
  否则任何登录用户能访问别人的部署。

[TODO/perm]: 加 user 鉴权,校验 conv 归属当前用户

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-06-04
"""

from __future__ import annotations

import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Path, Request
from fastapi.responses import Response, StreamingResponse


logger = logging.getLogger(__name__)


router = APIRouter()


# 不转发给容器的 hop-by-hop / 框架级 header(转发会出问题或重复)
_HOP_BY_HOP_HEADERS = frozenset({
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    # 让 httpx / Starlette 自己算 host,不传原 host 否则容器看到的是 AgentHub 的 host
    "host",
    # content-length 让 httpx 自己重算(stream 转发可能改变长度)
    "content-length",
})


def _filter_request_headers(headers) -> dict[str, str]:
    """转发请求时剔除 hop-by-hop。Starlette Headers 是大小写不敏感的多值容器。"""
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in _HOP_BY_HOP_HEADERS:
            continue
        out[k] = v
    return out


def _filter_response_headers(headers) -> dict[str, str]:
    """转发响应时同样剔除 hop-by-hop;额外去掉 content-encoding(httpx 解压后内容已变)。"""
    out: dict[str, str] = {}
    for k, v in headers.items():
        kl = k.lower()
        if kl in _HOP_BY_HOP_HEADERS:
            continue
        # httpx 自动解压 gzip/br,头还说 gzip 浏览器会再次解压失败
        if kl in ("content-encoding", "content-length"):
            continue
        out[k] = v
    return out


# 默认转发超时:30s 足够普通页面 + API,大文件下载靠 stream 不卡这里
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


@router.api_route(
    "/preview/{conv_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    summary="反向代理到会话容器内的部署应用",
    description=(
        "把请求转发到该会话 docker_runtime 启动的容器(localhost 视角下的"
        " 容器内部 IP:8000)。容器不存在时返回 503。"
    ),
)
async def proxy_to_container(
    conv_id: Annotated[str, Path(description="会话 ID")],
    path: str,
    request: Request,
) -> Response:
    """
    转发 path 到 http://{container_ip}:8000/{path}。

    流程:
    1. 查容器(docker_runtime.get_container)
    2. 不在 → 503
    3. 在 → httpx.AsyncClient stream 转发请求 + 响应
    4. touch(conv_id) 刷新闲置时间
    """
    # 解循环依赖 lazy import
    from backend.services.docker_runtime import (
        CONTAINER_INTERNAL_PORT,
        get_docker_runtime,
    )

    runtime = get_docker_runtime()
    handle = await runtime.get_container(conv_id)
    if handle is None:
        return Response(
            status_code=503,
            content=(
                f'{{"error":"container not running for conversation {conv_id}",'
                f'"hint":"先调用 deploy_app 工具部署应用"}}'
            ),
            media_type="application/json",
        )

    target_url = f"http://{handle.internal_ip}:{CONTAINER_INTERNAL_PORT}/{path}"
    forward_headers = _filter_request_headers(request.headers)
    body = await request.body()

    # 刷新闲置时间(转发开始就 touch,不等响应回来)
    runtime.touch(conv_id)

    try:
        async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT, follow_redirects=False) as client:
            proxied = await client.request(
                method=request.method,
                url=target_url,
                headers=forward_headers,
                content=body,
                params=request.query_params,
            )
    except httpx.ConnectError as exc:
        logger.warning(
            "preview proxy: 容器 %s 无响应 (ip=%s): %s",
            handle.container_name, handle.internal_ip, exc,
        )
        return Response(
            status_code=502,
            content='{"error":"container reachable but app not responding (uvicorn 没起?)"}',
            media_type="application/json",
        )
    except httpx.TimeoutException as exc:
        logger.warning("preview proxy: 容器响应超时 conv=%s: %s", conv_id, exc)
        return Response(
            status_code=504,
            content='{"error":"upstream timeout"}',
            media_type="application/json",
        )
    except Exception:
        logger.exception("preview proxy 异常 conv=%s path=%s", conv_id, path)
        return Response(
            status_code=500,
            content='{"error":"reverse proxy internal error"}',
            media_type="application/json",
        )

    response_headers = _filter_response_headers(proxied.headers)
    return Response(
        content=proxied.content,
        status_code=proxied.status_code,
        headers=response_headers,
        media_type=proxied.headers.get("content-type"),
    )
