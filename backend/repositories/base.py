"""
Repository 通用 CRUD 基类

子类指定 ORM 类:
    class ThreadRepo(BaseRepository[Thread]):
        model = Thread

session 由调用方(service 层)注入;repo 只负责 add/flush/refresh,
commit / rollback 由 service 层统一控制(事务边界)。

软删除不在 base 提供,各 repo 用 update(id, is_deleted=True) 自行实现。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

from typing import Any, ClassVar, Generic, Optional, TypeVar

from sqlalchemy.orm import Session

from backend.core.utils import gen_uuid
from backend.models.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """通用 CRUD 基类。子类必须设置 model 类属性。"""

    model: ClassVar[type]

    def __init__(self, session: Session) -> None:
        self.session = session

    # --------------------------------------------------------
    # 读
    # --------------------------------------------------------

    def get(self, id: str) -> Optional[ModelT]:
        return self.session.get(self.model, id)

    def list(
        self,
        *,
        offset: int = 0,
        limit: Optional[int] = None,
        **filters: Any,
    ) -> list[ModelT]:
        """按字段过滤的列表查询。filters 的 kv 直接转 WHERE 等值条件。"""
        query = self.session.query(self.model)
        for key, value in filters.items():
            if not hasattr(self.model, key):
                raise ValueError(f"{self.model.__name__} 没有字段 {key!r}")
            query = query.filter(getattr(self.model, key) == value)
        query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    # --------------------------------------------------------
    # 写(只 add / flush,不 commit)
    # --------------------------------------------------------

    def create(self, **kwargs: Any) -> ModelT:
        """创建并 add 到 session。id 缺省时自动生成 UUID。"""
        if "id" in self.model.__table__.columns and not kwargs.get("id"):
            kwargs["id"] = gen_uuid()
        obj = self.model(**kwargs)
        self.session.add(obj)
        self.session.flush()  # 拿到 id / 触发 server_default,不 commit
        return obj

    def update(self, id: str, **kwargs: Any) -> Optional[ModelT]:
        """
        按 id 更新指定字段(含传 None 置为 NULL)。返回更新后的对象,不存在时返回 None。
        调用方需要 partial update 时,自行 model_dump(exclude_unset=True) 过滤再传入。
        """
        obj = self.get(id)
        if obj is None:
            return None
        for key, value in kwargs.items():
            if not hasattr(self.model, key):
                raise ValueError(f"{self.model.__name__} 没有字段 {key!r}")
            setattr(obj, key, value)
        self.session.flush()
        return obj

    def delete(self, id: str) -> bool:
        """硬删除。返回是否实际删除了行。"""
        obj = self.get(id)
        if obj is None:
            return False
        self.session.delete(obj)
        self.session.flush()
        return True
