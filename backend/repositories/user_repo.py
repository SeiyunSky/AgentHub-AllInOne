"""
UserRepository —— users 表 CRUD

继承 BaseRepository[User] 拿到通用 get / list / create / update / delete,
本类只新增按 username / email 查询、更新登录时间这类业务专属方法。

session 由调用方注入;repo 只 add / flush,commit 由 service 决定。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-06-02
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from backend.models.user import User
from backend.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    # --------------------------------------------------------
    # 业务读
    # --------------------------------------------------------

    def get_by_username(self, username: str) -> Optional[User]:
        """按登录名查用户。username 列有 unique 约束,最多 1 条。"""
        return (
            self.session.query(User)
            .filter(User.username == username)
            .one_or_none()
        )

    def get_by_email(self, email: str) -> Optional[User]:
        """按邮箱查用户。email 列也是 unique;主要给"忘记密码"流程用。"""
        return (
            self.session.query(User)
            .filter(User.email == email)
            .one_or_none()
        )

    def username_taken(self, username: str) -> bool:
        """注册前快速判定 username 是否已被占用。"""
        return self.get_by_username(username) is not None

    def email_taken(self, email: str) -> bool:
        """同上,email 占用判定。"""
        return self.get_by_email(email) is not None

    # --------------------------------------------------------
    # 业务写
    # --------------------------------------------------------

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> User:
        """创建用户。display_name 缺省时回退到 username。"""
        return self.create(
            username=username,
            password_hash=password_hash,
            email=email,
            display_name=display_name or username,
        )

    def touch_last_login(self, user_id: str) -> Optional[User]:
        """登录成功时调,把 last_login_at 刷新到当前 UTC 时间。"""
        return self.update(
            user_id,
            last_login_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )


__all__ = ["UserRepository"]
