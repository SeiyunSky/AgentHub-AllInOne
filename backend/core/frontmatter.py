"""
通用 YAML frontmatter 解析与渲染

供需要"frontmatter + 正文" markdown 文件的子系统复用,目前包括:
- services/memory_service.py    长期记忆 .md
- services/skill_service.py     Skill .md(待实现)
- services/prompt_service.py    Prompt 模板 .md(待实现)

宽容策略:
- 文件无 `---` 边界 → 返回 ({}, 全文)
- frontmatter YAML 解析失败 → 返回 ({}, 全文) + logger.warning
- 这样手动编辑出语法错误时,正文仍能展示,不影响列表浏览

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-25
"""

import logging
import re
from typing import Any

import yaml

logger = logging.getLogger(__name__)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """
    从 markdown 文本中分离 YAML frontmatter 与正文。

    宽容策略:
    - 没有 `---` 边界 → 返回 ({}, 原文)
    - YAML 解析失败 → 返回 ({}, 原文) + logger.warning
    - frontmatter 不是 dict 结构 → 返回 ({}, 原文) + logger.warning
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    raw_meta, body = match.group(1), match.group(2)
    try:
        meta = yaml.safe_load(raw_meta)
    except yaml.YAMLError as exc:
        logger.warning("frontmatter YAML 解析失败,降级为空元数据: %s", exc)
        return {}, text

    if meta is None:
        return {}, body
    if not isinstance(meta, dict):
        logger.warning("frontmatter 不是 dict 结构,降级为空元数据")
        return {}, body

    return meta, body


def render_frontmatter(meta: dict[str, Any]) -> str:
    """
    把 frontmatter 元数据渲染成 YAML 块(含 `---` 边界)。
    保持 key 顺序(sort_keys=False),输出 utf-8 安全。
    调用方负责把传入字段已序列化为 YAML 友好类型(datetime → ISO 字符串等)。
    """
    body = yaml.safe_dump(
        meta,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    return f"---\n{body}---\n"
