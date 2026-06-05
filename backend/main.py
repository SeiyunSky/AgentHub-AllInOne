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

import asyncio
import logging
import sys

# Windows 上 SelectorEventLoop 不支持子进程,切换到 ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
from backend.seeds.users import seed_users


logger = logging.getLogger(__name__)


def _ensure_database() -> None:
    """幂等建库：仅对 MySQL/MariaDB 生效，其他数据库跳过。"""
    url = settings.DB_URL
    if not url.startswith(("mysql", "mariadb")):
        return

    from sqlalchemy import create_engine, text

    # 从连接串中去掉数据库名，得到一个能连上 MySQL Server 但不指定库的 URL
    # mysql+pymysql://user:pass@host:port/dbname?params → 截掉 /dbname
    try:
        from sqlalchemy.engine.url import URL, make_url
        parsed = make_url(url)
        db_name = parsed.database
        if not db_name:
            return
        # set(database=None) 不会真正去掉库名，必须用 URL.create 重建
        root_url = URL.create(
            drivername=parsed.drivername,
            username=parsed.username,
            password=parsed.password,
            host=parsed.host,
            port=parsed.port,
            database=None,
        )
    except Exception:
        logger.warning("_ensure_database: 解析 DB_URL 失败，跳过自动建库")
        return

    try:
        tmp_engine = create_engine(root_url, pool_pre_ping=False)
        with tmp_engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        tmp_engine.dispose()
        logger.info("_ensure_database: database '%s' ready", db_name)
    except Exception:
        logger.exception("_ensure_database: 自动建库失败，继续启动（手动建库后重试）")


def _run_migrations() -> None:
    """启动时自动执行 alembic upgrade head，保持数据库结构与代码同步。"""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    # 阻止 alembic 用 ini 里的 [loggers] 覆盖已配置好的 structlog handler
    alembic_cfg.attributes["configure_logger"] = False
    # 覆盖 ini 里的占位 URL，使用运行时真实配置
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DB_URL)
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期:启动加载资源,关闭释放资源。"""
    configure_logging()
    logger.info("AgentHub backend starting up...")

    # ---- 自动建库（幂等）----
    _ensure_database()

    # ---- 自动迁移 ----
    try:
        _run_migrations()
        logger.info("alembic upgrade head: OK")
    except Exception:
        logger.exception("alembic upgrade head failed (non-fatal, continuing startup)")

    # ---- Agent seed + Skill scan + Adapter registry ----
    db = SessionLocal()
    try:
        from backend.services.skill_service import SkillService

        # 收尸:把上次进程崩溃 / 强杀 / reload 留下的 running/init/suspended thread
        # 标成 error。这些 thread 的 asyncio.Task 早已随旧进程死了,DB 状态和内存
        # 现实不一致会让 chat_service 误判"当前还有 round 在跑"→ 新消息被押进
        # pending 队列等永远不会到来的 round_done。每次启动都收一次,代价是一条
        # UPDATE,换来 DB 状态与现实强一致。
        from sqlalchemy import text as _sql_text

        result = db.execute(_sql_text("""
            UPDATE threads
               SET status = 'error',
                   finished_at = NOW(),
                   error_message = 'backend restart, presumed dead'
             WHERE status IN ('init', 'running', 'suspended')
        """))
        db.commit()
        if result.rowcount:
            logger.warning(
                "stale threads reaped on startup: %d rows (presumed dead from previous run)",
                result.rowcount,
            )

        # 收尸：清理上次崩溃/重启留下的僵尸 pending approval blocks
        from backend.repositories.message_repo import MessageRepository as _MsgRepo
        reaped_approvals = _MsgRepo(db).reap_stale_approval_blocks()
        db.commit()
        if reaped_approvals:
            logger.warning(
                "stale approval blocks reaped on startup: %d blocks (presumed dead from previous run)",
                reaped_approvals,
            )

        # 顺序约束:必须先 seed_users(GUGA 系统用户)→ scan_builtin 让 skills 表填好
        # → seed_agents 再写 agent_skills 关联(seed_agents 内部按 default_skills
        # 配置查 skills 表挂载,且 agents.user_id='GUGA' 必须先存在)
        n_users = seed_users(db)
        if n_users:
            logger.info("seed_users: %d rows affected", n_users)

        n_skills = SkillService(db).scan_builtin()
        logger.info("skill_service.scan_builtin: %d rows affected", n_skills)

        n_agents = seed_agents(db)
        logger.info("seed_agents: %d rows affected", n_agents)

        adapter_registry.seed_from_db(db)
    except Exception:
        logger.exception("seed / skill scan / adapter seed failed (non-fatal)")
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

    # ---- Docker runtime: 镜像准备 + 闲置容器周期回收 ----
    # 整段包在 try 外层:任何失败(SDK 没装 / Docker daemon 不通 / 镜像 build 失败)
    # 都不阻塞 AgentHub 主流程,只让 deploy_app 工具在被调用时才报错。
    # 第一次 ensure_image 可能耗时 3-5 分钟(下载 base + pip install)。
    docker_runtime = None
    idle_cleanup_task = None
    try:
        from backend.services.docker_runtime import get_docker_runtime
        docker_runtime = get_docker_runtime()
        try:
            await docker_runtime.ensure_image()
        except RuntimeError as exc:
            # Docker daemon 不通是预期场景 (Docker Desktop 没启动),
            # 不打全栈,只 warning 提示用户启 Docker
            logger.warning(
                "docker_runtime.ensure_image skipped: %s "
                "(deploy_app 工具暂时不可用,启动 Docker Desktop 后自动恢复)", exc,
            )
        except Exception:
            logger.exception(
                "docker_runtime.ensure_image failed (non-fatal); "
                "deploy_app will fail until image is available"
            )

        # 后台 task: 每 5 分钟扫一次,30 分钟无流量的容器停掉
        async def _idle_cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(300)
                    n = await docker_runtime.stop_idle(idle_minutes=30)
                    if n:
                        logger.info("docker_runtime: reaped %d idle container(s)", n)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("docker_runtime idle cleanup iteration failed")

        idle_cleanup_task = asyncio.create_task(_idle_cleanup_loop())
    except ImportError:
        logger.warning(
            "docker SDK 未安装 (pip install docker==7.1.0),deploy_app 工具不可用"
        )
    except Exception:
        logger.exception("Docker runtime 初始化失败 (non-fatal),deploy_app 工具不可用")

    yield

    logger.info("AgentHub backend shutting down...")

    # ---- 取消 idle cleanup ----
    if idle_cleanup_task is not None:
        idle_cleanup_task.cancel()
        try:
            await idle_cleanup_task
        except (asyncio.CancelledError, Exception):
            pass

    # ---- 停所有 agenthub-* 容器 ----
    if docker_runtime is not None:
        try:
            await docker_runtime.shutdown()
        except Exception:
            logger.exception("docker_runtime.shutdown failed")

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
    from backend.api.v1 import auth as auth_router
    from backend.api.v1 import chat as chat_router
    from backend.api.v1 import conversations as conversations_router
    from backend.api.v1 import messages as messages_router
    from backend.api.v1 import ws as ws_router
    from backend.api.v1 import agents as agents_router
    from backend.api.v1 import skills as skills_router
    from backend.api.v1 import files as files_router
    from backend.api.v1 import artifacts as artifacts_router
    from backend.api.v1 import approvals as approvals_router
    from backend.api.v1 import squads as squads_router
    from backend.api.v1 import sandbox as sandbox_router
    from backend.api.v1 import preview as preview_router
    from backend.api.v1 import workflows as workflows_router

    app.include_router(auth_router.router, prefix="/api/v1", tags=["auth"])
    app.include_router(chat_router.router, prefix="/api/v1", tags=["chat"])
    app.include_router(
        conversations_router.router, prefix="/api/v1", tags=["conversations"]
    )
    app.include_router(messages_router.router, prefix="/api/v1", tags=["messages"])
    app.include_router(ws_router.router, prefix="/api/v1", tags=["ws"])
    app.include_router(agents_router.router, prefix="/api/v1", tags=["agents"])
    app.include_router(skills_router.router, prefix="/api/v1", tags=["skills"])
    app.include_router(files_router.router, prefix="/api/v1", tags=["files"])
    app.include_router(artifacts_router.router, prefix="/api/v1", tags=["artifacts"])
    app.include_router(approvals_router.router, prefix="/api/v1", tags=["approvals"])
    app.include_router(squads_router.router, prefix="/api/v1", tags=["squads"])
    app.include_router(sandbox_router.router, prefix="/api/v1", tags=["sandbox"])
    app.include_router(workflows_router.router, prefix="/api/v1", tags=["workflows"])
    # preview 不带 /api/v1 前缀:用户分享的 URL 是 http://host/preview/{conv_id}/,
    # 浏览器直接访问的 deploy 应用,不属于 API 范畴
    app.include_router(preview_router.router, tags=["preview"])

    # 静态资源：头像等图片文件
    _static_dir = Path(__file__).parent / "static"
    _static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    return app


app = create_app()
