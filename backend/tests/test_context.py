"""上下文压缩（memory/store.py 的 token 估算与预算裁剪）单测。"""
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from app.memory.store import estimate_tokens, budget_history


# ── token 估算 ────────────────────────────────────────────────────────────────
def test_estimate_tokens_basic():
    assert estimate_tokens("") == 0
    assert estimate_tokens(None) == 0
    assert estimate_tokens("a") >= 1


def test_estimate_tokens_cjk_heavier():
    # 中文按 ~1.5 token/字，应显著高于同长度 ASCII
    assert estimate_tokens("你" * 100) > estimate_tokens("a" * 100)


def test_estimate_tokens_monotonic():
    assert estimate_tokens("你好世界") > estimate_tokens("你好")
    assert estimate_tokens("hello world") > estimate_tokens("hello")


# ── 预算裁剪 ──────────────────────────────────────────────────────────────────
def _msgs(*texts):
    return [HumanMessage(content=t) for t in texts]


def test_budget_history_keeps_recent():
    msgs = _msgs("短" * 10, "短" * 10, "短" * 10, "短" * 10)
    out = budget_history(msgs, budget=estimate_tokens("短" * 10) + 5)  # 只能装下 1 条多一点
    assert len(out) <= 2
    assert out[-1].content == "短" * 10  # 保留最近的


def test_budget_history_keeps_order():
    msgs = _msgs("长" * 2000, "短")
    out = budget_history(msgs, budget=100)
    assert [m.content for m in out] == ["短"]  # 长消息超预算被裁，保留最近


def test_budget_history_at_least_one():
    msgs = _msgs("很长" * 10000)
    out = budget_history(msgs, budget=10)
    assert len(out) == 1  # 至少保留一条


def test_budget_history_does_not_mutate_input():
    msgs = _msgs("短" * 10, "短" * 10, "短" * 10, "短" * 10)
    before = list(msgs)
    budget_history(msgs, budget=1)
    assert msgs == before


def test_budget_history_zero_or_empty():
    assert budget_history([], 100) == []
    msgs = _msgs("a")
    assert budget_history(msgs, 0) == msgs  # 预算 0 → 原样


def test_budget_history_budget_includes_system_prompt():
    # 模拟 chat 接口用法：预算扣除 system prompt 后再裁历史
    system = SystemMessage(content="你" * 100)          # ≈150 token
    history = _msgs("你" * 100, "你" * 100, "你" * 100)  # 各 ≈150 token，共 450
    budget = 400
    out = budget_history(history, budget - estimate_tokens(system.content))
    assert len(out) < 3  # 预算不足 → 头部被裁
    assert out[-1].content == "你" * 100  # 保留最近
    used = estimate_tokens(system.content) + sum(estimate_tokens(m.content) for m in out)
    assert used <= budget + estimate_tokens("你" * 100)  # 含最后一条可略超


def test_budget_history_works_with_all_message_types():
    msgs = [
        SystemMessage(content="sys"),
        HumanMessage(content="q1"),
        ToolMessage(content="tool out", tool_call_id="t1"),
        AIMessage(content="a1"),
        HumanMessage(content="q2"),
    ]
    out = budget_history(msgs, budget=100)
    assert out[-1].content == "q2"
