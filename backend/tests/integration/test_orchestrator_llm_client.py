"""
Orchestrator LLM Client 集成测试 —— 真调外部 LLM 端点

跑测试前需要在环境变量里配:
    EXTERNAL_API_BASE  
    EXTERNAL_API_KEY   
    EXTERNAL_MODEL    

backend/.env 已配置,直接跑即可。CI / 无网环境用 -m "not integration" 跳过。

Run with:
    PYTHONIOENCODING=utf-8 pytest -m integration backend/tests/integration/test_orchestrator_llm_client.py -v

队伍:咕嘎一辈子队
修改者:咕嘎
修改日期:2026-05-26
"""

import pytest

from backend.config import settings
from backend.services.orchestrator.llm_client import (
    LLMResponse,
    LLMToolCall,
    OrchestratorLLMClient,
)


pytestmark = pytest.mark.integration


@pytest.fixture
def llm():
    """
    每个测试拿一个新 client。
    EXTERNAL_API_KEY 没配就 skip(本地能跑,CI 默认跳)。
    settings 会自动从 backend/.env 加载,所以这里直接查 settings 而非 os.environ。
    """
    if not settings.EXTERNAL_API_KEY:
        pytest.skip("EXTERNAL_API_KEY not set in .env")
    return OrchestratorLLMClient()


# ============================================================
# 场景 1: end_turn —— 最简问答,无工具
# ============================================================

async def test_end_turn_returns_text(llm):
    """LLM 拿到简单提示 → stop_reason=end_turn,content_text 非空。"""
    resp = await llm.chat_completion(
        system="你是一个简洁的助手,回答不超过 20 字。",
        messages=[{"role": "user", "content": '回复"收到"两个字。'}],
        tools=[],
        max_tokens=200,
    )
    assert isinstance(resp, LLMResponse)
    assert resp.stop_reason == "end_turn"
    assert resp.content_text and len(resp.content_text.strip()) > 0
    assert resp.tool_calls == []


async def test_end_turn_reports_output_tokens(llm):
    """成功调用后 output tokens > 0(input tokens 各家 LLM 行为不同,这里不强约束)。"""
    resp = await llm.chat_completion(
        system="一句话回复。",
        messages=[{"role": "user", "content": "ok"}],
        tools=[],
        max_tokens=50,
    )
    assert resp.tokens_output > 0


# ============================================================
# 场景 2: tool_use —— 主 Agent loop 真正要走的路径
# ============================================================

async def test_tool_use_parsed_correctly(llm):
    """
    LLM 拿到工具定义 + 明确触发条件的 user 消息时,应该:
    1. stop_reason=tool_use
    2. tool_calls 列表至少 1 项
    3. 每个 tool_call 含完整的 id / name / input
    """
    tools = [{
        "name": "get_weather",
        "description": "查询某城市的天气",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"},
            },
            "required": ["city"],
        },
    }]
    resp = await llm.chat_completion(
        system="你是助手。需要查询天气时必须调用 get_weather 工具。",
        messages=[{"role": "user", "content": "北京今天天气怎么样?"}],
        tools=tools,
        max_tokens=500,
    )
    assert resp.stop_reason == "tool_use"
    assert len(resp.tool_calls) >= 1

    call = resp.tool_calls[0]
    assert isinstance(call, LLMToolCall)
    assert call.name == "get_weather"
    assert call.id  # 非空字符串
    assert "city" in call.input  # input 是 dict 且包含必填字段


async def test_tool_use_input_is_dict(llm):
    """tool_call.input 必须是 dict(不能是字符串 / None)。"""
    tools = [{
        "name": "echo",
        "description": "echo 输入字符串",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
    }]
    resp = await llm.chat_completion(
        system="必须调用 echo 工具回答。",
        messages=[{"role": "user", "content": "请 echo 'hello'"}],
        tools=tools,
        max_tokens=300,
    )
    if resp.tool_calls:
        for call in resp.tool_calls:
            assert isinstance(call.input, dict)


# ============================================================
# 场景 3: 配置覆盖 —— 显式参数优先于 settings
# ============================================================

async def test_explicit_model_override():
    """构造时显式传 model 应该覆盖 settings.EXTERNAL_MODEL。"""
    if not settings.EXTERNAL_API_KEY:
        pytest.skip("EXTERNAL_API_KEY not set in .env")

    custom = OrchestratorLLMClient(model="custom-fake-model")
    assert custom._model == "custom-fake-model"
