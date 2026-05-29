"""
ContextCompactor —— 主 Agent 短期记忆压缩三层

对应主 Agent 设计文档第十节,作用对象是 _agent_loop 内部的 messages_history(对话流),
不是会话级历史(那是第 5 / 6 层 system prompt 的事)。

三层策略:
1. 大工具输出持久化   dispatch 子 Thread 完成 → 完整结果不放 messages_history,只留摘要
                    + thread_id。本层是**约定**,在 thread_service.\_extract_summary
                    + orchestrator.dispatch_to_agent 写入消息时已经实现,compactor 不做。
2. micro_compact     保留最近 N(默认 3)次 tool_result,更老的折叠为占位字符串。
3. global_summarize  token 超阈值 → 调 llm_client 单独发摘要请求,
                    用摘要 + 最近 5 条原文替换 messages。

调用约定:
- _agent_loop 每轮结束(下一轮开头前)调 maybe_compact(messages),
  内部按 token 估算决定不压 / 压第 2 层 / 压第 3 层,递进式。
- error_recovery.on_prompt_too_long 决策 truncate_history=True 时也走 global_summarize。

token 估算:
MVP 阶段用字符数 / 4 粗估,误差 ±20% 但够用。等真有 token 优化需求再换 tiktoken
或 anthropic count_tokens API。

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.config import settings
from backend.services.orchestrator.llm_client import llm_client


logger = logging.getLogger(__name__)


# 模块级降级标志:首次 count_tokens 失败后置 True,本进程后续直接走 fallback
# 不再发请求,避免每轮 404 / 5xx 噪音 + 浪费 RPM 配额
_count_tokens_disabled: bool = not settings.ENABLE_COUNT_TOKENS_API


# ============================================================
# 阈值与策略常量
# ============================================================

COMPACT_THRESHOLD_TOKENS = 30_000
RECENT_TOOL_RESULTS_KEEP = 3
RECENT_MESSAGES_KEEP_AFTER_SUMMARY = 5

# global_summarize 喂给摘要 LLM 的 head_text 字符上限。
# 超阈值才进 global_summarize,head_text 本身可能很长——直接发可能超摘要 LLM context。
# 80K 字符约 20K token,远低于 Kimi/Anthropic 200K 上限,留足摘要 LLM 自身工作空间。
_SUMMARIZE_HEAD_CHAR_LIMIT = 80_000
_SUMMARIZE_TRUNCATION_MARK = "\n\n...(earlier history truncated due to length)\n\n"

# 摘要 LLM 调用的 system prompt
_SUMMARIZE_SYSTEM = (
    "你是对话历史摘要助手。把一段主 Agent 的对话历史压缩成结构化 markdown 总结,"
    "字数控制在 2000 字以内。\n\n"
    "保留:\n"
    "1. 用户的核心需求与关键约束\n"
    "2. 已派出的子 Thread:目标 / 当前状态 / 关键产出结论\n"
    "3. 主 Agent 的中间决策(为何选某个 Agent / 为何拆任务)\n\n"
    "丢掉:重复的 system 注入消息、未派活的犹豫、纯 think-aloud 段落。\n\n"
    "**只输出 markdown 摘要正文,不要前后客套**。"
)

# 占位字符串,折叠老 tool_result 用
_TRUNCATED_TOOL_RESULT_PLACEHOLDER = (
    "[Tool result truncated to save context. "
    "If you need full content, call the corresponding read tool with thread_id / file path again.]"
)


# ============================================================
# ContextCompactor
# ============================================================

class ContextCompactor:
    """主 Agent loop 的 messages_history 压缩器。"""

    # --------------------------------------------------------
    # token 估算
    # --------------------------------------------------------

    async def estimate_tokens(
        self,
        messages: list[dict[str, Any]],
    ) -> int:
        """
        估算 messages token 数。

        优先调 anthropic count_tokens API(精确,误差小);失败或被 settings 关闭时
        退回字符数 / 4 兜底。首次失败后置模块级降级标志,本进程不再重试,
        避免每轮 LLM 调用都触发 404 / 5xx 噪音(如 Kimi /anthropic 端点不支持本接口)。
        """
        global _count_tokens_disabled
        if _count_tokens_disabled:
            return self._estimate_tokens_fallback(messages)

        try:
            return await llm_client.count_tokens(messages=messages)
        except Exception as exc:
            _count_tokens_disabled = True
            logger.warning(
                "count_tokens API 不可用,本进程切换到字符数 / 4 兜底: %s: %s",
                type(exc).__name__, exc,
            )
            return self._estimate_tokens_fallback(messages)

    @staticmethod
    def _estimate_tokens_fallback(messages: list[dict[str, Any]]) -> int:
        """
        字符数 / 4 粗估。误差 ±20% 但纯本地计算,毫秒级。

        用途:
        - estimate_tokens 兜底(API 失败时)
        - maybe_compact 二次估算(micro_compact 后只需要"是否显著缩水"的粗判断,
          不值得再花一次 HTTP RTT)
        """
        try:
            payload = json.dumps(messages, ensure_ascii=False)
        except (TypeError, ValueError):
            payload = repr(messages)
        return len(payload) // 4

    # --------------------------------------------------------
    # 第 2 层:micro_compact
    # --------------------------------------------------------

    def micro_compact(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        保留最近 RECENT_TOOL_RESULTS_KEEP 次 tool_result,更老的折叠为占位。

        这里"tool_result"指 messages 里 role=user 且 content 是 list,
        且 list 里有 type=tool_result block 的消息(主 Agent loop 步 5
        把 tool_result 拼成 user 消息追加到 messages)。

        其他消息(role=assistant 含 tool_use,role=user 纯文本提问 / 子 Thread
        事件注入)全部保留——它们是任务推进的脉络,不能丢。

        返回新列表,不修改入参。
        """
        # 找出所有 tool_result 消息的索引
        tool_result_indices: list[int] = []
        for idx, msg in enumerate(messages):
            if self._is_tool_result_message(msg):
                tool_result_indices.append(idx)

        # 决定哪些要折叠:keep 最后 N 个,前面的折叠
        if len(tool_result_indices) <= RECENT_TOOL_RESULTS_KEEP:
            return list(messages)

        fold_until = tool_result_indices[-RECENT_TOOL_RESULTS_KEEP]
        # fold_until 之前的 tool_result 索引
        to_fold = set(i for i in tool_result_indices if i < fold_until)

        result: list[dict[str, Any]] = []
        for idx, msg in enumerate(messages):
            if idx in to_fold:
                # 把这条消息里所有 tool_result block 的 content 替换为占位
                folded = self._fold_tool_result_message(msg)
                result.append(folded)
            else:
                result.append(msg)
        return result

    # --------------------------------------------------------
    # 第 3 层:global_summarize
    # --------------------------------------------------------

    async def global_summarize(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        token 严重超阈值时的兜底压缩:调 LLM 摘要历史,
        返回 [摘要 user 消息 + 最近 RECENT_MESSAGES_KEEP_AFTER_SUMMARY 条原文]。

        消息数 <= RECENT_MESSAGES_KEEP_AFTER_SUMMARY 时不摘要(没意义),
        直接返回原序列。
        """
        if len(messages) <= RECENT_MESSAGES_KEEP_AFTER_SUMMARY:
            return list(messages)

        # 切分:前段进摘要,后段保留原文
        head = messages[:-RECENT_MESSAGES_KEEP_AFTER_SUMMARY]
        tail = messages[-RECENT_MESSAGES_KEEP_AFTER_SUMMARY:]

        # 把 head 序列化成可读文本喂给摘要 LLM
        head_text = self._serialize_messages_for_summary(head)

        # 长度保护:head_text 本身可能超过摘要 LLM 的 context 上限
        # (走到这里就是因为 messages 已经超阈值)。截断头部保留尾部
        # ——尾部内容更接近"当前任务",对摘要 LLM 推断意图更有帮助。
        if len(head_text) > _SUMMARIZE_HEAD_CHAR_LIMIT:
            keep_tail_len = _SUMMARIZE_HEAD_CHAR_LIMIT - len(_SUMMARIZE_TRUNCATION_MARK)
            head_text = _SUMMARIZE_TRUNCATION_MARK + head_text[-keep_tail_len:]
            logger.info(
                "global_summarize head_text truncated to last %d chars",
                keep_tail_len,
            )

        try:
            response = await llm_client.chat_completion(
                system=_SUMMARIZE_SYSTEM,
                messages=[{"role": "user", "content": head_text}],
                tools=[],
                max_tokens=4000,
            )
        except Exception:
            logger.exception("global_summarize 调用 LLM 失败,退回原 messages")
            return list(messages)

        summary_text = response.content_text or "(摘要失败:LLM 未返回内容)"

        summary_msg = {
            "role": "user",
            "content": (
                "[历史摘要——以下是本轮之前的对话压缩版,完整原文已不再保留]\n\n"
                f"{summary_text}"
            ),
        }
        return [summary_msg] + list(tail)

    # --------------------------------------------------------
    # 主入口
    # --------------------------------------------------------

    async def maybe_compact(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        每轮结束调:检查 token 是否超阈值,超则按三层策略递进压缩。

        递进策略:
        1. 估 token(精确,走 count_tokens API),未超阈值 → 直接返回原序列
        2. 超阈值 → micro_compact 折叠老 tool_result
        3. 用字符数 / 4 粗估二次确认 —— 不再调 count_tokens API,
           micro_compact 折叠的字符数变化是确定性的,粗估足以判断"是否显著回落"
        4. 仍超阈值 → global_summarize 兜底
        """
        tokens = await self.estimate_tokens(messages)
        if tokens < COMPACT_THRESHOLD_TOKENS:
            return list(messages)

        logger.info(
            "context tokens=%d > threshold=%d, run micro_compact",
            tokens,
            COMPACT_THRESHOLD_TOKENS,
        )
        compacted = self.micro_compact(messages)

        # 二次估算用字符数 / 4 粗估,不再多花一次 count_tokens API:
        # micro_compact 把 tool_result content 折叠为短占位字符串,字符数变化是确定的,
        # 粗估足以判断回落与否
        compacted_tokens_rough = self._estimate_tokens_fallback(compacted)
        if compacted_tokens_rough < COMPACT_THRESHOLD_TOKENS:
            return compacted

        logger.info(
            "micro_compact insufficient (rough tokens=%d), run global_summarize",
            compacted_tokens_rough,
        )
        return await self.global_summarize(compacted)

    # --------------------------------------------------------
    # 内部辅助
    # --------------------------------------------------------

    @staticmethod
    def _is_tool_result_message(msg: dict[str, Any]) -> bool:
        """判断一条消息是否是"tool_result 回灌消息"。"""
        if msg.get("role") != "user":
            return False
        content = msg.get("content")
        if not isinstance(content, list):
            return False
        return any(
            isinstance(b, dict) and b.get("type") == "tool_result"
            for b in content
        )

    @staticmethod
    def _fold_tool_result_message(msg: dict[str, Any]) -> dict[str, Any]:
        """
        把消息里所有 tool_result block 的 content 替换为占位字符串。
        其他字段(tool_use_id / is_error)保留——LLM 仍能看到工具被调过、
        是否成功,只是不再保留具体 output。

        返回新 dict,不修改入参。
        """
        new_content: list[dict[str, Any]] = []
        for block in msg.get("content", []):
            if isinstance(block, dict) and block.get("type") == "tool_result":
                folded_block = dict(block)
                folded_block["content"] = _TRUNCATED_TOOL_RESULT_PLACEHOLDER
                new_content.append(folded_block)
            else:
                new_content.append(block)
        return {**msg, "content": new_content}

    @staticmethod
    def _serialize_messages_for_summary(messages: list[dict[str, Any]]) -> str:
        """
        把 messages 序列化成可读文本喂给摘要 LLM。

        Anthropic 协议里 content 可能是 str 或 list[block]。
        这里展开成"[role] 文本"格式,工具调用 / 结果用方括号标记保留 LLM 可读性。
        """
        lines: list[str] = []
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content")

            if isinstance(content, str):
                lines.append(f"[{role}] {content}")
                continue

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        lines.append(f"[{role}] {block!r}")
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        lines.append(f"[{role}] {block.get('text', '')}")
                    elif btype == "tool_use":
                        name = block.get("name", "?")
                        inp = block.get("input", {})
                        lines.append(f"[{role}] <tool_use {name} input={inp}>")
                    elif btype == "tool_result":
                        result = block.get("content", "")
                        is_err = block.get("is_error", False)
                        tag = "tool_error" if is_err else "tool_result"
                        lines.append(f"[{role}] <{tag}> {result}")
                    else:
                        lines.append(f"[{role}] <{btype}> {block}")
                continue

            # 兜底
            lines.append(f"[{role}] {content!r}")
        return "\n".join(lines)


context_compactor = ContextCompactor()
