"""token 用量计量与预算管控（精打细算）。

- usage_logs 表：每轮 LLM 调用的 input/output token 与成本估算（含会话/用户/模型维度）
- usage_settings 表：预算配置（daily_budget_usd / monthly_budget_usd），0 或空 = 不限
- 价格表按 provider+model 匹配，未知模型用兜底价并标记 estimate=True
- 预算检查：chat 入口调用 check_budget() 限流；record 时按阈值打告警日志
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional

from app import persistence
from app.core.logging import get_logger

logger = get_logger("usage")
_lock = threading.Lock()

_CREATE = """
CREATE TABLE IF NOT EXISTS usage_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    DEFAULT (datetime('now','localtime')),
    user_id       INTEGER,
    username      TEXT,
    session_id    TEXT,
    llm_config_id INTEGER,
    provider      TEXT,
    model         TEXT,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL    NOT NULL DEFAULT 0,
    estimate      INTEGER NOT NULL DEFAULT 0   -- 1 = 未知模型按兜底价估算
);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage_logs(ts);
CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_logs(user_id);
CREATE TABLE IF NOT EXISTS usage_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# 价格表：$/1M tokens，格式 {provider: {model: (input_price, output_price)}}
# 数据为公开价格的大致值，随服务商调价更新；未知模型走 DEFAULT_PRICE 并标记估算
PRICING: dict = {
    "openai": {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-3.5-turbo": (0.50, 1.50),
    },
    "anthropic": {
        "claude-3-5-sonnet": (3.00, 15.00),
        "claude-3-5-haiku": (0.80, 4.00),
        "claude-3-haiku": (0.25, 1.25),
        "claude-sonnet-4": (3.00, 15.00),
        "claude-opus-4": (15.00, 75.00),
    },
    "qwen": {
        "qwen-max": (2.40, 9.60),
        "qwen-plus": (0.80, 2.00),
        "qwen-turbo": (0.30, 0.60),
    },
}
DEFAULT_PRICE = (3.00, 15.00)  # 未知模型兜底

# 告警阈值（相对预算）：80% warn，100%+ error
WARN_RATIO = 0.8

# 周期常量
PERIOD_DAY = "day"
PERIOD_MONTH = "month"


def _connect() -> sqlite3.Connection:
    persistence._DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(persistence._DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(_CREATE)
    conn.commit()
    return conn


# ── 成本估算 ──────────────────────────────────────────────────────────────────
def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int):
    """返回 (cost_usd, is_estimate)。未知模型按兜底价并标记估算。"""
    in_p, out_p = (PRICING.get((provider or "").lower(), {}) or {}).get(model) or DEFAULT_PRICE
    cost = (input_tokens / 1_000_000 * in_p) + (output_tokens / 1_000_000 * out_p)
    is_estimate = model not in (PRICING.get((provider or "").lower(), {}) or {})
    return round(cost, 6), is_estimate


# ── 提取 usage（纯函数，可单测）──────────────────────────────────────────────
def extract_usage(messages) -> tuple[int, int]:
    """从一轮对话的消息列表累计所有 AIMessage 的 usage_metadata（input/output tokens）。"""
    inp = out = 0
    for m in messages:
        um = getattr(m, "usage_metadata", None) or {}
        inp += int(um.get("input_tokens") or 0)
        out += int(um.get("output_tokens") or 0)
    return inp, out


# ── 记录 ──────────────────────────────────────────────────────────────────────
def record_usage(user_id: Optional[int], username: Optional[str], session_id: Optional[str],
                 llm_config_id: Optional[int], provider: str, model: str,
                 input_tokens: int, output_tokens: int) -> dict:
    """写入一条用量记录并返回。顺带做预算告警检查（超阈值打日志）。"""
    cost, estimate = estimate_cost(provider, model, input_tokens, output_tokens)
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "INSERT INTO usage_logs(user_id, username, session_id, llm_config_id, "
                "provider, model, input_tokens, output_tokens, cost_usd, estimate) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (user_id, username, session_id, llm_config_id, provider, model,
                 input_tokens, output_tokens, cost, int(estimate)),
            )
            conn.commit()
            rec = {"id": cur.lastrowid, "input_tokens": input_tokens, "output_tokens": output_tokens,
                   "cost_usd": cost, "estimate": estimate}
        finally:
            conn.close()
    _check_and_warn_budget()
    return rec


# ── 预算 ──────────────────────────────────────────────────────────────────────
def get_setting(key: str, default: str = "") -> str:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT value FROM usage_settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default
        finally:
            conn.close()


def set_setting(key: str, value: str) -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute("INSERT OR REPLACE INTO usage_settings(key, value) VALUES (?,?)", (key, value))
            conn.commit()
        finally:
            conn.close()


def get_budget_config() -> dict:
    return {
        "daily_budget_usd": float(get_setting("daily_budget_usd") or 0),
        "monthly_budget_usd": float(get_setting("monthly_budget_usd") or 0),
    }


def set_budget_config(daily: float = 0, monthly: float = 0) -> dict:
    set_setting("daily_budget_usd", str(max(0.0, daily)))
    set_setting("monthly_budget_usd", str(max(0.0, monthly)))
    return get_budget_config()


def _period_cost(period: str) -> float:
    """当前周期累计成本（day=今天，month=本月）。"""
    if period == PERIOD_DAY:
        where = "date(ts) = date('now','localtime')"
    else:
        where = "strftime('%Y-%m', ts) = strftime('%Y-%m','now','localtime')"
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(f"SELECT COALESCE(SUM(cost_usd),0) AS c FROM usage_logs WHERE {where}").fetchone()
            return round(row["c"], 6)
        finally:
            conn.close()


def _fmt_usd(x: float) -> str:
    """金额显示：小金额保留足够精度，大金额两位小数。"""
    return f"{x:.4f}" if x < 1 else f"{x:.2f}"


def check_budget() -> tuple[bool, str]:
    """chat 入口限流检查。返回 (是否允许, 拒绝原因/空串)。预算为 0 表示不限。"""
    cfg = get_budget_config()
    daily, monthly = cfg["daily_budget_usd"], cfg["monthly_budget_usd"]
    if daily > 0:
        used = _period_cost(PERIOD_DAY)
        if used >= daily:
            return False, f"今日预算已用完（{_fmt_usd(used)}/{_fmt_usd(daily)} USD），请明日再试或联系管理员调整预算"
    if monthly > 0:
        used = _period_cost(PERIOD_MONTH)
        if used >= monthly:
            return False, f"本月预算已用完（{_fmt_usd(used)}/{_fmt_usd(monthly)} USD），请联系管理员调整预算"
    return True, ""


def _check_and_warn_budget() -> None:
    """记录后检查预算占用比例，按阈值打告警日志（预算告警）。"""
    cfg = get_budget_config()
    for key, period in (("daily_budget_usd", PERIOD_DAY), ("monthly_budget_usd", PERIOD_MONTH)):
        limit = cfg[key]
        if limit <= 0:
            continue
        used = _period_cost(period)
        ratio = used / limit
        if ratio >= 1.0:
            logger.error("budget_exceeded", extra={"period": period, "used": used, "limit": limit})
        elif ratio >= WARN_RATIO:
            logger.warning("budget_warning", extra={"period": period, "used": used, "limit": limit,
                                                    "ratio": round(ratio, 3)})


# ── 报表查询（管理端）────────────────────────────────────────────────────────
def _query(sql: str, params: tuple = ()) -> list[dict]:
    with _lock:
        conn = _connect()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()


def summary_by_day(days: int = 7) -> list[dict]:
    return _query(
        "SELECT date(ts) AS day, COUNT(*) AS calls, SUM(input_tokens) AS input_tokens, "
        "SUM(output_tokens) AS output_tokens, ROUND(SUM(cost_usd),4) AS cost_usd "
        "FROM usage_logs WHERE ts >= datetime('now','localtime', ?) "
        "GROUP BY date(ts) ORDER BY day",
        (f"-{int(days)} days",),
    )


def summary_by_user(days: int = 7) -> list[dict]:
    return _query(
        "SELECT COALESCE(username,'?') AS username, COUNT(*) AS calls, "
        "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, "
        "ROUND(SUM(cost_usd),4) AS cost_usd "
        "FROM usage_logs WHERE ts >= datetime('now','localtime', ?) "
        "GROUP BY username ORDER BY cost_usd DESC",
        (f"-{int(days)} days",),
    )


def summary_by_model(days: int = 7) -> list[dict]:
    return _query(
        "SELECT provider, model, COUNT(*) AS calls, SUM(input_tokens) AS input_tokens, "
        "SUM(output_tokens) AS output_tokens, ROUND(SUM(cost_usd),4) AS cost_usd "
        "FROM usage_logs WHERE ts >= datetime('now','localtime', ?) "
        "GROUP BY provider, model ORDER BY cost_usd DESC",
        (f"-{int(days)} days",),
    )


def list_logs(limit: int = 100, user_id: Optional[int] = None) -> list[dict]:
    limit = max(1, min(limit, 500))
    sql = ("SELECT id, ts, user_id, username, session_id, provider, model, "
           "input_tokens, output_tokens, cost_usd, estimate FROM usage_logs")
    params: list = []
    if user_id is not None:
        sql += " WHERE user_id=?"
        params.append(user_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return _query(sql, tuple(params))
