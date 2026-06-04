"""
内置系统用户 seed

GUGA 是一个特殊的"系统所有者"用户：
- 所有内置 Agent / Skill 的 user_id / author_id 都指向它
- 普通用户不能登录这个账号（password_hash 设占位值，bcrypt 永远验证失败）
- 通过"权限校验=资源.user_id 等于当前用户 id"这一条统一规则，自然保证内置资源不可被改

队伍：咕嘎一辈子队
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from backend.models.user import User

logger = logging.getLogger(__name__)


# 内置系统用户的固定 ID，所有内置 Agent/Skill 的 user_id/author_id 都指向它
GUGA_USER_ID = "GUGA"

# 永远 hash 不出来的占位值。bcrypt 验证时会失败 → GUGA 账号无法登录。
# 用 "!" 而非空串：留个非空约束的安全垫，bcrypt verify 也会立即返回 False。
_DISABLED_PASSWORD_HASH = "!disabled!"


def seed_users(db: Session) -> int:
    """
    幂等写入 GUGA 系统用户。

    策略：
    - 不存在 → INSERT（disabled 占位 password_hash，禁止登录）
    - 存在   → SKIP（不覆盖，避免影响人为修改的字段）

    事务约定：函数内自管 commit，与 seed_agents / scan_builtin 现有约定一致
    （每个 seed 步骤是独立事务）。代价是 GUGA 用户写库后若后续 seed 失败,
    GUGA 用户行会留下；但这正是幂等需要的——下次启动直接 SKIP。

    返回实际新增的行数（0 或 1）。
    """
    existing = db.query(User).filter_by(id=GUGA_USER_ID).first()
    if existing is not None:
        return 0

    db.add(User(
        id=GUGA_USER_ID,
        username=GUGA_USER_ID,  # 占用 username='GUGA',防止有人注册同名账号
        password_hash=_DISABLED_PASSWORD_HASH,
        display_name="System (GUGA)",
        email=None,
    ))
    db.commit()
    logger.info("Seeded system user GUGA (login disabled)")
    return 1
