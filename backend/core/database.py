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
