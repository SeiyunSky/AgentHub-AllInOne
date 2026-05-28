"""
context_compactor 三层压缩策略测试

被测对象不 mock,只在系统边界(chat_completion / count_tokens)拦截真 LLM 调用。
真 LLM 摘要质量预览见 scripts/preview_compactor.py。

队伍:咕嘎一辈子队
修改者:Adam Zhang
修改日期:2026-05-28
"""

from __future__ import annotations

import pytest

from backend.services.orchestrator import context_compactor as _cc_module
from backend.services.orchestrator.context_compactor import (
    ContextCompactor,
    RECENT_MESSAGES_KEEP_AFTER_SUMMARY,
    RECENT_TOOL_RESULTS_KEEP,
    context_compactor,
)
from backend.services.orchestrator.llm_client import LLMResponse


@pytest.fixture(autouse=True)
def _reset_count_tokens_disabled():
    """每个测试重置 count_tokens 降级标志,避免上一个测试触发降级污染下一个。"""
    _cc_module._count_tokens_disabled = False
    yield
    _cc_module._count_tokens_disabled = False


# ============================================================
# 构造助手
# ============================================================

def make_user_text(text: str) -> dict:
    """role=user 纯文本消息。"""
    return {"role": "user", "content": text}


def make_assistant_text(text: str) -> dict:
    """role=assistant 纯文本消息。"""
    return {"role": "assistant", "content": text}


def make_tool_use_msg(tool_use_id: str, name: str, input_dict: dict) -> dict:
    """role=assistant 含 tool_use block 的消息。"""
    return {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": tool_use_id, "name": name, "input": input_dict},
        ],
    }


def make_tool_result_msg(tool_use_id: str, content: str, is_error: bool = False) -> dict:
    """role=user 含 tool_result block 的消息(主 Agent loop 步 5 拼回来的形态)。"""
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
                "is_error": is_error,
            }
        ],
    }


# ============================================================
# 1. 纯函数:_estimate_tokens_fallback
# ============================================================

def test_fallback_estimate_uses_char_quarter():
    """字符数 / 4 粗估,误差 ±20% 但够用。"""
    msgs = [make_user_text("a" * 400)]
    # JSON 序列化大约 ~430 字符,/4 ≈ 107
    estimate = ContextCompactor._estimate_tokens_fallback(msgs)
    assert 80 < estimate < 200


def test_fallback_estimate_handles_non_serializable():
    """JSON 序列化失败时退到 repr,不抛异常。"""
    class _Unserializable:
        pass

    msgs = [{"role": "user", "content": _Unserializable()}]
    # 不抛异常,返回某个 int
    estimate = ContextCompactor._estimate_tokens_fallback(msgs)
    assert estimate > 0


# ============================================================
# 2. 纯函数:_is_tool_result_message / _fold_tool_result_message
# ============================================================

def test_is_tool_result_message():
    cc = ContextCompactor

    # 是 tool_result 消息
    tr = make_tool_result_msg("call-1", "output")
    assert cc._is_tool_result_message(tr) is True

    # role=assistant 即使含 tool_use,也不算 tool_result
    tu = make_tool_use_msg("call-1", "x", {})
    assert cc._is_tool_result_message(tu) is False

    # 纯文本 user 消息
    assert cc._is_tool_result_message(make_user_text("hi")) is False

    # content 是 str 而非 list
    assert cc._is_tool_result_message({"role": "user", "content": "hi"}) is False


def test_fold_tool_result_message_replaces_content():
    """折叠后:tool_use_id / is_error 字段保留,content 替换为占位字符串。"""
    msg = make_tool_result_msg("call-1", "huge output content", is_error=False)
    folded = ContextCompactor._fold_tool_result_message(msg)

    assert folded["role"] == "user"
    block = folded["content"][0]
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == "call-1"
    assert block["is_error"] is False
    assert "Tool result truncated" in block["content"]
    assert "huge output content" not in block["content"]


def test_fold_does_not_mutate_input():
    """折叠返回新 dict,不修改入参(消息可能被多处引用)。"""
    msg = make_tool_result_msg("call-1", "original")
    ContextCompactor._fold_tool_result_message(msg)
    assert msg["content"][0]["content"] == "original"


# ============================================================
# 3. 纯函数:_serialize_messages_for_summary
# ============================================================

def test_serialize_messages_renders_each_block_type():
    msgs = [
        make_user_text("user question"),
        make_tool_use_msg("call-1", "read_file", {"path": "x.py"}),
        make_tool_result_msg("call-1", "file content"),
        make_assistant_text("assistant text"),
    ]
    text = ContextCompactor._serialize_messages_for_summary(msgs)

    assert "[user] user question" in text
    assert "<tool_use read_file" in text
    assert "<tool_result>" in text
    assert "[assistant] assistant text" in text


# ============================================================
# 4. estimate_tokens 异常兜底
# ============================================================

@pytest.mark.asyncio
async def test_estimate_tokens_falls_back_when_count_tokens_raises(monkeypatch):
    """count_tokens API 抛异常时退回字符数 / 4。"""
    from backend.services.orchestrator.llm_client import llm_client as _llm

    async def _fail_count(**kwargs):
        raise RuntimeError("count_tokens API 不支持")

    monkeypatch.setattr(_llm, "count_tokens", _fail_count)

    msgs = [make_user_text("hello world" * 50)]
    estimate = await context_compactor.estimate_tokens(msgs)
    # 退回 fallback,不抛异常
    assert estimate > 0


# ============================================================
# 5. micro_compact 折叠老 tool_result
# ============================================================

def test_micro_compact_keeps_recent_tool_results():
    """
    构造 5 个 tool_result 消息(穿插非 tool_result),
    micro_compact 应保留最近 RECENT_TOOL_RESULTS_KEEP 个,折叠更老的。
    """
    keep = RECENT_TOOL_RESULTS_KEEP  # 默认 3
    total = keep + 2

    msgs: list[dict] = [make_user_text("user request")]
    for i in range(total):
        msgs.append(make_tool_use_msg(f"call-{i}", "x", {}))
        msgs.append(make_tool_result_msg(f"call-{i}", f"output-{i}"))

    compacted = context_compactor.micro_compact(msgs)

    # 消息总数不变
    assert len(compacted) == len(msgs)

    # 拿到所有 tool_result 消息
    tr_msgs = [m for m in compacted if ContextCompactor._is_tool_result_message(m)]
    assert len(tr_msgs) == total

    # 老的 keep 之外的应被折叠 ——content 不再是原始文本
    folded_count = sum(
        1 for m in tr_msgs
        if "Tool result truncated" in m["content"][0]["content"]
    )
    kept_count = sum(
        1 for m in tr_msgs
        if m["content"][0]["content"].startswith("output-")
    )
    assert kept_count == keep
    assert folded_count == total - keep


def test_micro_compact_skips_when_under_threshold():
    """tool_result 数量 <= 保留上限,不折叠任何东西。"""
    msgs = []
    for i in range(RECENT_TOOL_RESULTS_KEEP):
        msgs.append(make_tool_use_msg(f"call-{i}", "x", {}))
        msgs.append(make_tool_result_msg(f"call-{i}", f"output-{i}"))

    compacted = context_compactor.micro_compact(msgs)
    assert compacted == msgs


def test_micro_compact_returns_new_list():
    """不修改入参列表对象引用。"""
    msgs = [make_user_text("a")]
    compacted = context_compactor.micro_compact(msgs)
    assert compacted is not msgs


# ============================================================
# 6. global_summarize:切分 + 拼接
# ============================================================

@pytest.mark.asyncio
async def test_global_summarize_splits_head_and_tail(monkeypatch):
    """
    输入 N 条消息,N > RECENT_MESSAGES_KEEP_AFTER_SUMMARY:
    - head 应被序列化送给 LLM
    - 返回 [摘要消息 + 最后 KEEP 条原文]
    """
    keep = RECENT_MESSAGES_KEEP_AFTER_SUMMARY  # 默认 5
    total = keep + 8

    msgs = [make_user_text(f"msg-{i}") for i in range(total)]

    captured_head_text: list[str] = []

    async def _fake_chat(*, system, messages, tools, max_tokens=4000, model=None):
        # 摘要 LLM 收到的应该是 head 序列化后的文本
        assert messages[0]["role"] == "user"
        captured_head_text.append(messages[0]["content"])
        return LLMResponse(
            stop_reason="end_turn",
            content_text="STUB SUMMARY",
            tool_calls=[],
            tokens_input=10, tokens_output=20,
        )

    from backend.services.orchestrator.llm_client import llm_client as _llm
    monkeypatch.setattr(_llm, "chat_completion", _fake_chat)

    result = await context_compactor.global_summarize(msgs)

    # 总长 = 1 摘要 + keep 条 tail
    assert len(result) == 1 + keep

    # 第一条是摘要,role=user,内容含 STUB SUMMARY
    summary_msg = result[0]
    assert summary_msg["role"] == "user"
    assert "STUB SUMMARY" in summary_msg["content"]
    assert "历史摘要" in summary_msg["content"]

    # 后续 keep 条是原文,按顺序
    for i, m in enumerate(result[1:]):
        expected_idx = total - keep + i
        assert m == msgs[expected_idx]

    # head_text 包含早期消息
    assert "msg-0" in captured_head_text[0]
    # head_text 不应包含 tail 部分(切分线之后的)
    assert f"msg-{total - 1}" not in captured_head_text[0]


@pytest.mark.asyncio
async def test_global_summarize_skips_when_messages_short(monkeypatch):
    """消息数 <= RECENT_MESSAGES_KEEP_AFTER_SUMMARY,不调摘要 LLM,直接返回原序列。"""
    msgs = [make_user_text(f"m-{i}") for i in range(RECENT_MESSAGES_KEEP_AFTER_SUMMARY)]

    chat_called = False

    async def _should_not_be_called(**kwargs):
        nonlocal chat_called
        chat_called = True
        raise AssertionError("不该调 LLM")

    from backend.services.orchestrator.llm_client import llm_client as _llm
    monkeypatch.setattr(_llm, "chat_completion", _should_not_be_called)

    result = await context_compactor.global_summarize(msgs)
    assert result == msgs
    assert chat_called is False


@pytest.mark.asyncio
async def test_global_summarize_truncates_oversized_head(monkeypatch):
    """
    当 head_text 字符数超过 _SUMMARIZE_HEAD_CHAR_LIMIT,应截断保留尾部,
    送给 LLM 的 head_text 不会无限大。
    """
    # 构造 100 条消息,每条 2000 字符 → head ~200K 字符,触发截断
    msgs = [make_user_text("X" * 2000) for _ in range(100)]

    captured_head_len: list[int] = []

    async def _fake_chat(*, system, messages, **kwargs):
        captured_head_len.append(len(messages[0]["content"]))
        return LLMResponse(
            stop_reason="end_turn",
            content_text="SUM",
            tool_calls=[],
            tokens_input=10, tokens_output=20,
        )

    from backend.services.orchestrator.llm_client import llm_client as _llm
    monkeypatch.setattr(_llm, "chat_completion", _fake_chat)

    await context_compactor.global_summarize(msgs)

    # head_text 应被截到 _SUMMARIZE_HEAD_CHAR_LIMIT(80K)左右
    assert captured_head_len, "_fake_chat 未被调用"
    assert captured_head_len[0] <= 80_000 + 1000  # 容差


@pytest.mark.asyncio
async def test_global_summarize_falls_back_on_llm_failure(monkeypatch):
    """摘要 LLM 抛异常时返回原 messages,不让整个 loop 崩。"""
    msgs = [make_user_text(f"m-{i}") for i in range(RECENT_MESSAGES_KEEP_AFTER_SUMMARY + 5)]

    async def _crash(**kwargs):
        raise RuntimeError("摘要 LLM 不可用")

    from backend.services.orchestrator.llm_client import llm_client as _llm
    monkeypatch.setattr(_llm, "chat_completion", _crash)

    result = await context_compactor.global_summarize(msgs)
    # 兜底应返回原列表(可以是 list(msgs) 浅拷贝,但内容一致)
    assert result == msgs


# ============================================================
# 7. maybe_compact 三层递进决策
# ============================================================

@pytest.mark.asyncio
async def test_maybe_compact_skips_when_under_threshold(monkeypatch):
    """token 估算 < 阈值,直接返回原 messages,不调 micro 也不调 global。"""
    msgs = [make_user_text("short")]

    async def _low_estimate(self, messages):
        return 100  # 远低于 30K 阈值

    monkeypatch.setattr(ContextCompactor, "estimate_tokens", _low_estimate)

    result = await context_compactor.maybe_compact(msgs)
    assert result == msgs


@pytest.mark.asyncio
async def test_maybe_compact_micro_then_recovers(monkeypatch):
    """
    超阈值 → micro_compact 折叠后字符数显著下降,粗估回落到阈值下 → 不进 global。

    场景设计:大量老 tool_result(50K 字符 × N)被折叠为短占位,
    最近 RECENT_TOOL_RESULTS_KEEP 个 tool_result 用短内容(避免占位之外还超阈值)。
    """
    keep = RECENT_TOOL_RESULTS_KEEP
    old_count = 6  # 老的会被折叠

    msgs: list[dict] = [make_user_text("user")]
    # 老的:50K 大输出(总计 300K 字符,/4 = 75K token,远超阈值)
    for i in range(old_count):
        msgs.append(make_tool_use_msg(f"old-{i}", "x", {}))
        msgs.append(make_tool_result_msg(f"old-{i}", "X" * 50_000))
    # 最近 keep 个:短输出
    for i in range(keep):
        msgs.append(make_tool_use_msg(f"new-{i}", "x", {}))
        msgs.append(make_tool_result_msg(f"new-{i}", "tiny"))

    async def _high_estimate(self, messages):
        # estimate_tokens 报告超阈值,触发 micro_compact
        return 80_000

    monkeypatch.setattr(ContextCompactor, "estimate_tokens", _high_estimate)

    # 不让它进 global
    summarize_called = False

    async def _should_not_be_called(messages):
        nonlocal summarize_called
        summarize_called = True
        return messages

    monkeypatch.setattr(context_compactor, "global_summarize", _should_not_be_called)

    result = await context_compactor.maybe_compact(msgs)

    # 应该走了 micro_compact(老 tool_result 被折叠)
    folded_count = sum(
        1 for m in result
        if ContextCompactor._is_tool_result_message(m)
        and "Tool result truncated" in m["content"][0]["content"]
    )
    assert folded_count == old_count

    # micro 后字符数应回落:keep 个短 tool_result + old_count 个占位 + 杂项消息 ≈ 几 KB
    # 远低于 30K token 阈值 → 不进 global
    assert summarize_called is False


@pytest.mark.asyncio
async def test_maybe_compact_falls_through_to_global(monkeypatch):
    """
    超阈值 → micro_compact 后**字符数仍超**(比如 tool_result 不多但消息正文巨大)
    → 走 global_summarize。
    """
    msgs = [make_user_text("X" * 200_000) for _ in range(20)]  # ~4M 字符

    async def _high_estimate(self, messages):
        return 100_000

    monkeypatch.setattr(ContextCompactor, "estimate_tokens", _high_estimate)

    summarize_input: list[list[dict]] = []

    async def _capture_summarize(messages):
        summarize_input.append(messages)
        return [{"role": "user", "content": "[GLOBAL SUMMARY]"}]

    monkeypatch.setattr(context_compactor, "global_summarize", _capture_summarize)

    result = await context_compactor.maybe_compact(msgs)

    # 走了 global,且收到的是 micro 后的(本场景无 tool_result,所以 micro 不动)
    assert len(summarize_input) == 1
    assert result == [{"role": "user", "content": "[GLOBAL SUMMARY]"}]
