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
修改日期:2026-05-29
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.adapters.registry import registry as adapter_registry
from backend.api.exception_handlers import register_exception_handlers
from backend.api.middleware.logging import TraceIdMiddleware
from backend.api.middleware.response_envelope import ResponseEnvelopeMiddleware
from backend.config import settings
from backend.core.database import SessionLocal, engine
from backend.core.logging import configure_logging
from backend.hooks.approval import ApprovalHook
from backend.hooks.base import HookEvent
from backend.hooks.manager import hook_manager
from backend.hooks.post_execution import PostExecutionHook
from backend.hooks.pre_execution import PreExecutionHook
from backend.seeds.agents import seed_agents


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期:启动加载资源,关闭释放资源。"""
    configure_logging()
    logger.info("AgentHub backend starting up...")

    # ---- seed preset agents + scan skills ----
    db = SessionLocal()
    try:
        from backend.services.skill_service import SkillService

        n_agents = seed_agents(db)
        logger.info("seed_agents: %d rows affected", n_agents)

        adapter_registry.seed_from_db(db)

        n_skills = SkillService(db).scan_builtin()
        logger.info("skill_service.scan_builtin: %d rows affected", n_skills)
    except Exception:
        logger.exception("seed / skill scan failed (non-fatal)")
    finally:
        db.close()

    # ---- hook 注册 ----
    # PRE_TOOL_USE 链：先 PreExecutionHook（黑名单 + 沙箱路径前置校验），
    # 再 ApprovalHook（高危工具拦截 / 等待用户决策）。
    # 顺序很关键：路径非法 / 黑名单工具应该被机器直接 block,不该让用户看到审批框；
    # 合法的高危调用再交给用户决策。
    hook_manager.register_sync(HookEvent.PRE_TOOL_USE, PreExecutionHook())
    hook_manager.register_sync(HookEvent.PRE_TOOL_USE, ApprovalHook())

    # POST_TOOL_USE 异步 hook：审计日志（不阻塞主流程）
    hook_manager.register_async(HookEvent.POST_TOOL_USE, PostExecutionHook())

    logger.info(
        "hooks registered: PRE_TOOL_USE=[PreExecutionHook, ApprovalHook], "
        "POST_TOOL_USE=[PostExecutionHook]"
    )

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


def create_app(*, include_lifespan: bool = True) -> FastAPI:
    app = FastAPI(
        title="AgentHub Backend",
        version="0.1.0",
        description="多 Agent 协作 IM 平台",
        lifespan=lifespan if include_lifespan else None,
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

    # ---- 响应包装 middleware ----
    app.add_middleware(ResponseEnvelopeMiddleware)

    # ---- TraceId middleware ----
    # 最后 add → 最外层最先执行,trace_id 绑到 contextvars 后下游 CORS / 响应包装 /
    # 路由 / 业务日志都能自动带上。
    app.add_middleware(TraceIdMiddleware)

    # ---- 全局异常处理器 ----
    register_exception_handlers(app)

    # ---- 路由挂载 ----
    # 已实装路由按 /api/v1 前缀挂载;未实装的 stub 路由(单 # TODO 占位)不挂
    # 路由模块按需 import,避免还没实装的 stub 模块在 import 阶段就炸
    from backend.api.v1 import chat as chat_router
    from backend.api.v1 import conversations as conversations_router
    from backend.api.v1 import messages as messages_router
    from backend.api.v1 import ws as ws_router
    from backend.api.v1 import agents as agents_router
    from backend.api.v1 import skills as skills_router

    app.include_router(chat_router.router, prefix="/api/v1", tags=["chat"])
    app.include_router(
        conversations_router.router, prefix="/api/v1", tags=["conversations"]
    )
    app.include_router(messages_router.router, prefix="/api/v1", tags=["messages"])
    app.include_router(ws_router.router, prefix="/api/v1", tags=["ws"])
    app.include_router(agents_router.router, prefix="/api/v1", tags=["agents"])
    app.include_router(skills_router.router, prefix="/api/v1", tags=["skills"])

    return app


app = create_app()
