"""
FastAPI 应用入口

启动顺序(lifespan):
1. 启动期:
   - 初始化日志
   - adapter_registry.seed_from_db(从 agents 表加载所有 active Agent)
   - 注册 hook(等 hooks 实装后接通)
2. 关闭期:
   - adapter_registry.shutdown(关 MCP 连接等)
   - 数据库引擎 dispose

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-26
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.adapters.registry import registry as adapter_registry
from backend.config import settings
from backend.core.database import engine


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期:启动加载资源,关闭释放资源。"""
    logging.basicConfig(level=logging.INFO)
    logger.info("AgentHub backend starting up...")

    # ---- adapter registry seed ----
    # 等无履生把 seed_from_db 改成同步,直接调
    # TODO[main-1]: 无履生改完后切到 adapter_registry.seed_from_db(SessionLocal())
    logger.info("[TODO/main-1] adapter_registry.seed_from_db 等同步签名落地后接通")

    # ---- hook 注册 ----
    # TODO[main-2]: 等具体 hook(approval / pre_execution / post_execution)实装后,
    # 在这里 hook_manager.register(...) 注册到 HookManager
    logger.info("[TODO/main-2] hook 注册等具体 hook 实装后接通")

    yield

    logger.info("AgentHub backend shutting down...")
    # ---- adapter registry shutdown ----
    try:
        await adapter_registry.shutdown()
    except Exception:
        logger.exception("adapter_registry.shutdown failed")

    # ---- DB 引擎释放 ----
    engine.dispose()
    logger.info("Backend shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentHub Backend",
        version="0.1.0",
        description="多 Agent 协作 IM 平台",
        lifespan=lifespan,
    )

    # ---- CORS ----
    cors_origins = [
        origin.strip()
        for origin in settings.CORS_ALLOWED_ORIGINS.split(",")
        if origin.strip()
    ]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ---- 路由挂载 ----
    # 已实装路由按 /api/v1 前缀挂载;未实装的 stub 路由(单 # TODO 占位)不挂
    # 路由模块按需 import,避免还没实装的 stub 模块在 import 阶段就炸
    from backend.api.v1 import chat as chat_router

    app.include_router(chat_router.router, prefix="/api/v1", tags=["chat"])

    # TODO[main-3]: 各业务路由随实装陆续挂载:
    #   agents / conversations / messages / skills / artifacts / auth / ws

    return app


app = create_app()
