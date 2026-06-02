"""
SQLAlchemy 引擎 + session 工厂

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-06-02
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings


# 强制连接级别时区 = UTC,让 MySQL 的 CURRENT_TIMESTAMP / TIMESTAMP 列默认值
# 都按 UTC 写入。否则 server 时区(CST/+08)会让 created_at 与 Python 端
# datetime.now(timezone.utc) 写的 started_at / finished_at 时区错位。
#
# 同时设会话级 lock_wait_timeout = 10s:任何 UPDATE 撞行锁 10s 内拿不到就抛错,
# 不再默认 50s 静默挂死。lock_wait_timeout 在事务发生前就生效,即使代码忘 commit
# 也不会让别的协程被阻塞太久。
#
# 注意:pymysql 的 init_command 只接受单条 SQL,多条要用 connect 事件钩子分别 execute。
_IS_MYSQL = settings.DB_URL.startswith(("mysql", "mariadb"))


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
)


# 每次新建底层 DBAPI 连接时跑一遍会话级 SET,保证时区 + 锁等待都对。
# pymysql init_command 只支持单条,所以用 SQLAlchemy 的 event 钩子分别 execute。
if _IS_MYSQL:
    @event.listens_for(engine, "connect")
    def _set_mysql_session_vars(dbapi_conn, _conn_record):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("SET time_zone='+00:00'")
            cur.execute("SET SESSION innodb_lock_wait_timeout=10")
        finally:
            cur.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    短事务 session 的标准上下文管理器,业务代码应优先用本接口而不是直接 SessionLocal()。

    保证三件事:
    1. **close 前强制 rollback** —— 即使调用方忘 commit,也不会让一个隐式 BEGIN
       的事务长期挂在 MySQL 端占行锁,这是长事务泄漏的根因。
    2. 异常路径自动 rollback + 抛出。
    3. close 一定执行(即使 rollback 也抛错)。

    用法:
        with db_session() as s:
            repo.do_something(s)
            s.commit()    # 显式 commit;漏掉了 finally 也会兜底 rollback
    """
    s = SessionLocal()
    try:
        yield s
    except Exception:
        try:
            s.rollback()
        except Exception:
            pass
        raise
    finally:
        # 保险栓:即便业务代码 commit 过了,这次 rollback 是 no-op;
        # 如果业务忘 commit / 只读取没显式收尾,这里把任何隐式 BEGIN 的空事务回滚掉,
        # 确保 close 之后 MySQL 端不留挂着的事务。
        try:
            s.rollback()
        except Exception:
            pass
        s.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用的 session 生成器。每次请求拿一个 session,结束自动关。"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        # 同 db_session():close 前强制 rollback 兜底
        try:
            db.rollback()
        except Exception:
            pass
        db.close()
