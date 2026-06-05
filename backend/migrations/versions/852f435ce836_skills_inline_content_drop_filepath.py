"""skills_inline_content_drop_filepath

把 Skill 正文从文件存储改为 DB content 列。

upgrade 步骤：
1. 加 content 列（默认 ''，避免现有行违反 NOT NULL）
2. 遍历 skills 表，按 file_path 读 .md 文件正文（去 frontmatter）回填 content
   - 文件不存在 → content 留空字符串，启动时 scan_builtin 兜底
3. 删 file_path 列

downgrade 仅恢复列结构，不重建文件。

Revision ID: 852f435ce836
Revises: 909725750cbd
Create Date: 2026-06-05 10:13:40.779452

"""
from pathlib import Path
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = '852f435ce836'
down_revision: Union[str, Sequence[str], None] = '909725750cbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
# backend 目录：当前文件在 backend/migrations/versions/，向上两级到 backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


def _read_md_body(file_path: str) -> str:
    """读 .md 文件正文（去掉 frontmatter）。文件不存在或读失败返回空串。"""
    try:
        # file_path 形如 "skills/foo.md" 或 "skills/user_xxx/bar.md"
        path = _BACKEND_ROOT / file_path
        text = path.read_text(encoding="utf-8")
        return _FRONTMATTER_RE.sub("", text, count=1).strip()
    except Exception:
        return ""


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 先加 content 列为 nullable（MySQL TEXT 不允许 server_default,
    #    所以先建 nullable，回填后再改为 NOT NULL）
    op.add_column(
        'skills',
        sa.Column(
            'content',
            sa.Text(),
            nullable=True,
            comment='Skill 正文（Markdown）',
        ),
    )

    # 2. 回填：把 file_path 指向的 .md 文件正文读出来写进 content
    #    用 op.get_bind() 拿原生连接执行，避免 ORM 模型与当前 schema 不匹配
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, file_path FROM skills")).fetchall()
    for row in rows:
        skill_id = row[0]
        file_path = row[1]
        body = _read_md_body(file_path) if file_path else ""
        bind.execute(
            sa.text("UPDATE skills SET content = :c WHERE id = :id"),
            {"c": body, "id": skill_id},
        )

    # 3. 把 content 改为 NOT NULL（此时所有行已有非 NULL 值）
    op.alter_column(
        'skills', 'content',
        existing_type=sa.Text(),
        nullable=False,
        existing_comment='Skill 正文（Markdown）',
    )

    # 4. 更新 name 注释 + 删 file_path 列
    op.alter_column(
        'skills', 'name',
        existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=100),
        comment='英文唯一标识',
        existing_comment='英文唯一标识，对应 .md 文件名',
        existing_nullable=False,
    )
    op.drop_column('skills', 'file_path')


def downgrade() -> None:
    """Downgrade schema. 仅恢复列结构,不重建 .md 文件。"""
    op.add_column(
        'skills',
        sa.Column(
            'file_path',
            mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=255),
            nullable=False,
            server_default='',
            comment='指向 skills/{name}.md',
        ),
    )
    op.alter_column(
        'skills', 'name',
        existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=100),
        comment='英文唯一标识，对应 .md 文件名',
        existing_comment='英文唯一标识',
        existing_nullable=False,
    )
    op.drop_column('skills', 'content')
