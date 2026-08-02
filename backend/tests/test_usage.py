"""token 用量计量与预算管控（app/usage）单测 + 接口集成测试。"""
import pytest
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from app.usage import (
    estimate_cost, extract_usage, record_usage, list_logs,
    get_budget_config, set_budget_config, check_budget,
    summary_by_day, summary_by_user, summary_by_model,
    DEFAULT_PRICE,
)


# ── 成本估算 ──────────────────────────────────────────────────────────────────
def test_estimate_cost_known_model():
    # gpt-4o: $2.5/$10 每 1M token；1M input + 1M output = $12.5
    cost, estimate = estimate_cost("openai", "gpt-4o", 1_000_000, 1_000_000)
    assert cost == pytest.approx(12.5, abs=1e-4)
    assert estimate is False


def test_estimate_cost_provider_case_insensitive():
    cost, _ = estimate_cost("OpenAI", "gpt-4o", 1_000_000, 0)
    assert cost == pytest.approx(2.5, abs=1e-4)


def test_estimate_cost_unknown_model_fallback():
    cost, estimate = estimate_cost("openai", "some-future-model", 1_000_000, 1_000_000)
    assert estimate is True
    assert cost == pytest.approx((DEFAULT_PRICE[0] + DEFAULT_PRICE[1]) / 1_000_000 * 1_000_000, abs=1e-3)


def test_estimate_cost_zero_tokens():
    cost, estimate = estimate_cost("qwen", "qwen-max", 0, 0)
    assert cost == 0.0


# ── usage 提取（纯函数）──────────────────────────────────────────────────────
def test_extract_usage_accumulates_aimessages():
    msgs = [
        SystemMessage(content="sys"),
        HumanMessage(content="hi"),
        AIMessage(content="a", usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}),
        AIMessage(content="b", usage_metadata={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60}),
    ]
    assert extract_usage(msgs) == (150, 30)


def test_extract_usage_no_metadata():
    assert extract_usage([HumanMessage(content="x"), AIMessage(content="y")]) == (0, 0)


# ── 记录与查询 ────────────────────────────────────────────────────────────────
def test_record_and_list(isolated_storage):
    rec = record_usage(1, "alice", "s1", 2, "openai", "gpt-4o", 1000, 500)
    assert rec["cost_usd"] == pytest.approx(1000 / 1e6 * 2.5 + 500 / 1e6 * 10, abs=1e-5)
    rows = list_logs()
    assert len(rows) == 1
    assert rows[0]["username"] == "alice" and rows[0]["model"] == "gpt-4o"


def test_list_logs_filter_user(isolated_storage):
    record_usage(1, "alice", "s1", 1, "openai", "gpt-4o", 10, 10)
    record_usage(2, "bob", "s2", 1, "openai", "gpt-4o", 10, 10)
    assert len(list_logs(user_id=1)) == 1


def test_summary_grouping(isolated_storage):
    record_usage(1, "alice", "s1", 1, "openai", "gpt-4o", 100, 100)
    record_usage(1, "alice", "s2", 1, "openai", "gpt-4o-mini", 50, 50)
    by_user = summary_by_user(days=7)
    assert by_user[0]["username"] == "alice" and by_user[0]["calls"] == 2
    by_model = summary_by_model(days=7)
    assert {m["model"] for m in by_model} == {"gpt-4o", "gpt-4o-mini"}
    by_day = summary_by_day(days=7)
    assert len(by_day) == 1 and by_day[0]["calls"] == 2


# ── 预算配置与限流 ────────────────────────────────────────────────────────────
def test_budget_config_default_unlimited(isolated_storage):
    cfg = get_budget_config()
    assert cfg == {"daily_budget_usd": 0.0, "monthly_budget_usd": 0.0}
    assert check_budget() == (True, "")


def test_budget_check_daily(isolated_storage):
    set_budget_config(daily=0.000001)  # 极小的日预算
    record_usage(1, "alice", "s1", 1, "openai", "gpt-4o", 100, 100)
    ok, reason = check_budget()
    assert ok is False and "今日预算" in reason


def test_budget_check_monthly(isolated_storage):
    set_budget_config(monthly=0.000001)
    record_usage(1, "alice", "s1", 1, "openai", "gpt-4o", 100, 100)
    ok, reason = check_budget()
    assert ok is False and "本月预算" in reason


def test_budget_check_under_limit(isolated_storage):
    set_budget_config(daily=100.0, monthly=100.0)
    record_usage(1, "alice", "s1", 1, "openai", "gpt-4o", 100, 100)
    assert check_budget() == (True, "")


def test_set_budget_config_roundtrip(isolated_storage):
    cfg = set_budget_config(daily=5.5, monthly=50)
    assert cfg == {"daily_budget_usd": 5.5, "monthly_budget_usd": 50.0}
    assert get_budget_config() == cfg


# ── 接口（集成）───────────────────────────────────────────────────────────────
def _register(client, name, pwd="pass1234"):
    return client.post("/api/auth/register", json={"username": name, "password": pwd}).json()["token"]


def test_usage_api_admin_only(client):
    admin_token = _register(client, "boss")
    user_token = _register(client, "worker")
    admin_h = {"Authorization": f"Bearer {admin_token}"}
    user_h = {"Authorization": f"Bearer {user_token}"}
    for path in ("/api/usage/summary", "/api/usage/by_user", "/api/usage/by_model",
                 "/api/usage/logs", "/api/usage/config"):
        assert client.get(path, headers=user_h).status_code == 403, path
        assert client.get(path, headers=admin_h).status_code == 200, path
    assert client.get("/api/usage/summary").status_code == 401


def test_usage_config_api(isolated_storage, client):
    admin_token = _register(client, "boss")
    admin_h = {"Authorization": f"Bearer {admin_token}"}
    r = client.put("/api/usage/config", json={"daily_budget_usd": 10, "monthly_budget_usd": 100}, headers=admin_h)
    assert r.status_code == 200
    assert r.json() == {"daily_budget_usd": 10.0, "monthly_budget_usd": 100.0}


def test_usage_api_reflects_records(client, isolated_storage):
    admin_token = _register(client, "boss")
    admin_h = {"Authorization": f"Bearer {admin_token}"}
    # 直接写入一条用量记录（绕过 LLM 调用）
    record_usage(1, "boss", "s1", 1, "openai", "gpt-4o", 1000, 500)
    body = client.get("/api/usage/summary", headers=admin_h).json()
    assert body[0]["calls"] == 1 and body[0]["cost_usd"] > 0
    logs = client.get("/api/usage/logs", headers=admin_h).json()
    assert logs[0]["username"] == "boss" and logs[0]["input_tokens"] == 1000
