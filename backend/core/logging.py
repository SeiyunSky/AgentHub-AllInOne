"""
core/logging —— 结构化日志配置(structlog + stdlib logging 桥接)

设计目标:
1. 全工程统一日志格式(开发=彩色对齐 / 生产=单行 JSON)
2. **未迁移的 stdlib `logging.getLogger(__name__)` 调用同样享受结构化输出**,
   不阻塞业务代码逐步迁移到 structlog.get_logger
3. 提供 contextvars 绑定能力,后续在 chat_service / orchestrator 入口绑 trace_id /
   user_id / conversation_id 后,整条调用链所有日志自动带上这些字段

工作原理:
- structlog 的 processor 链负责"把任意输入(stdlib LogRecord 或 structlog event_dict)
  渲染成最终行"
- ProcessorFormatter 是 structlog 提供的桥:让 stdlib logging 的 Formatter 走同一条
  processor 链,从而 stdlib 日志和 structlog 日志输出格式完全一致
- foreign_pre_chain 处理 stdlib 来的 record(打时间戳、等级、merge contextvars 等);
  最后一段 renderer 共用,console 或 json 二选一

使用方式:
    from backend.core.logging import configure_logging, bind_contextvars, clear_contextvars
    configure_logging()  # 启动期一次性调用
    bind_contextvars(trace_id="abc", user_id="u1")  # 入口处绑

    # 业务代码可继续用 stdlib logger,也可以逐步迁到 structlog:
    import logging; log = logging.getLogger(__name__); log.info("...")
    import structlog; log = structlog.get_logger(); log.info("...", k=v)

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-27
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, unbind_contextvars

from backend.config import settings


__all__ = [
    "configure_logging",
    "bind_contextvars",
    "clear_contextvars",
    "unbind_contextvars",
]


def _build_shared_processors() -> list[Any]:
    """
    structlog 与 stdlib logging 共享的 processor 链(渲染前的预处理)。

    顺序很关键:
    - merge_contextvars 必须在最前面,后续 processor 才能看到 bound 字段
    - add_log_level / TimeStamper 添加固定字段
    - StackInfoRenderer / format_exc_info 处理异常信息
    - 最后由各自路径的 renderer 收尾(本函数不含 renderer)
    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _select_renderer():
    """根据 settings.LOG_FORMAT 选 renderer。console 给开发,json 给生产。"""
    if settings.LOG_FORMAT.lower() == "json":
        return structlog.processors.JSONRenderer()
    # 默认 console:彩色 + 字段对齐;非 TTY 时 colors 自动降级
    return structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())


def configure_logging() -> None:
    """
    一次性配置 structlog + stdlib logging。
    main.py 在 lifespan 启动期最早处调用,**取代** logging.basicConfig。

    幂等:重复调用安全(stdlib root logger handler 会被替换,structlog 配置覆盖)。
    """
    shared_processors = _build_shared_processors()
    renderer = _select_renderer()

    # ---- structlog 配置 ----
    # processors 链尾部用 ProcessorFormatter.wrap_for_formatter:
    # 把 event_dict 包成"等待被 ProcessorFormatter 渲染"的占位,实际 renderer 由
    # stdlib handler 上挂的 ProcessorFormatter 跑。这样 structlog 与 stdlib 共用
    # 同一个 renderer 实例,输出格式统一。
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ---- stdlib logging 配置 ----
    # ProcessorFormatter 收 stdlib LogRecord:
    # - foreign_pre_chain:对 stdlib 来的 record 跑一遍 shared_processors,补齐
    #   timestamp / level / contextvars 等字段(structlog 来的已经跑过)
    # - processors:最后只跑 renderer,因为前面已经预处理过
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # 清掉已有 handler(防止重复配置时日志重复输出)
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    # 抑制几个特别吵的第三方库(避免淹没业务日志,可按需扩展)
    for noisy in ("urllib3", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
