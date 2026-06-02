"""
SQLAlchemy 引擎 + session 工厂

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings


# 强制连接级别时区 = UTC,让 MySQL 的 CURRENT_TIMESTAMP / TIMESTAMP 列默认值
# 都按 UTC 写入。否则 server 时区(CST/+08)会让 created_at 与 Python 端
# datetime.now(timezone.utc) 写的 started_at / finished_at 时区错位。
_engine_connect_args: dict = {}
if settings.DB_URL.startswith(("mysql", "mariadb")):
    _engine_connect_args["init_command"] = "SET time_zone='+00:00'"


engine: Engine = create_engine(
    settings.DB_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    # group 路径下并发 session 多:HTTP self.session + orchestrator loop_session +
    # dispatch_to_agent + 子 Thread own_session + create_assistant_message + …
    # 一轮主 Agent + 一个子 Agent 至少同时 6~8 个,默认 5+10 在多轮 / 多子 Agent 下会撞上限
    pool_size=20,
    max_overflow=30,
    # 拿不到连接时 10 秒就报错,避免被静默挂死
    pool_timeout=10,
    echo=False,
    connect_args=_engine_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用的 session 生成器。每次请求拿一个 session,结束自动关。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
