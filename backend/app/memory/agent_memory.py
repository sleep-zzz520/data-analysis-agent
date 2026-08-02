"""Agent 长期记忆（跨会话事实 / 会话摘要 / 相关历史检索）。

记忆是 Agent 能力的核心（简历亮点）：
1. 长期记忆 user_memories：跨会话记住用户偏好/常用库/约定，LLM 提取 + 节流
2. 会话摘要 session_summaries：历史太长时用结构化摘要快速定位（省 token）
3. 记忆检索：按用户问题关键词从消息表检索相关历史，按需注入（不整段重放）

成本控制：提取/摘要都用极简 prompt 的 LLM 调用，且按 轮次/时间 节流，
避免每轮对话都烧额外 token（精打细算）。
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from typing import Optional

from langchain_core.messages import SystemMessage

from app import persistence

# RLock：summary_due 等函数存在"外层持锁再调内部持锁函数"的嵌套，
# 普通 Lock 不可重入会导致同线程自死锁
_lock = threading.RLock()

# 节流参数
MEMORY_SIGNAL_WORDS = ("常用", "喜欢", "偏好", "每次", "总是", "以后", "记得", "我希望", "我想要", "不要用", "统一用")
_EXTRACT_MIN_INTERVAL = 600      # 同一会话两次记忆提取的最小间隔（秒）
_SUMMARY_EVERY_TURNS = 5         # 每 N 轮（human 消息）更新一次摘要
_MAX_KEYWORDS = 4                # 检索关键词上限
_RETRIEVE_LIMIT = 6              # 检索注入的消息条数

_CREATE = """
CREATE TABLE IF NOT EXISTS user_memories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    username      TEXT,
    key           TEXT NOT NULL,
    value         TEXT NOT NULL,
    source_session TEXT,
    created_at    TEXT DEFAULT (datetime('now','localtime')),
    updated_at    TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(user_id, key)
);
CREATE TABLE IF NOT EXISTS session_summaries (
    session_id    TEXT PRIMARY KEY,
    summary       TEXT NOT NULL,
    turn          INTEGER NOT NULL DEFAULT 0,   -- 生成摘要时的 human 轮数
    updated_at    TEXT DEFAULT (datetime('now','localtime'))
);
"""

# 会话级提取节流（内存态，重启丢失可接受）
_extract_log: dict = {}


def _connect() -> sqlite3.Connection:
    persistence._DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(persistence._DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.executescript(_CREATE)
    conn.commit()
    return conn


# ── 长期记忆 ──────────────────────────────────────────────────────────────────
def _has_memory_signal(text: str) -> bool:
    return any(w in (text or "") for w in MEMORY_SIGNAL_WORDS)


def _extract_rate_limited(session_id: str) -> bool:
    """同一会话两次提取的最小间隔控制。"""
    now = time.time()
    last = _extract_log.get(session_id, 0)
    if now - last < _EXTRACT_MIN_INTERVAL:
        return True  # 被限流
    _extract_log[session_id] = now
    return False


def extract_and_store_memories(llm, user_id: int, username: Optional[str],
                               session_id: str, user_text: str, reply: str) -> list:
    """从本轮对话提取长期记忆（LLM + 信号词触发 + 时间节流）。返回新增/更新条数。"""
    if not _has_memory_signal(user_text) or _extract_rate_limited(session_id):
        return 0
    from app.agent.prompts import MEMORY_EXTRACT_PROMPT
    prompt = MEMORY_EXTRACT_PROMPT.format(user_text=(user_text or "")[:800], reply=(reply or "")[:500])
    try:
        out = llm.invoke([SystemMessage(content=prompt)]).content
    except Exception:  # noqa: BLE001 —— 记忆提取失败不影响主流程
        return 0
    try:
        items = json.loads(str(out or "[]"))
        if not isinstance(items, list):
            return 0
    except (json.JSONDecodeError, TypeError):
        return 0
    saved = 0
    for it in items:
        key = str((it or {}).get("key", "")).strip()[:50]
        value = str((it or {}).get("value", "")).strip()[:300]
        if key and value:
            if _upsert_memory(user_id, username, key, value, session_id):
                saved += 1
    return saved


def _upsert_memory(user_id: int, username: Optional[str], key: str, value: str,
                   session_id: Optional[str]) -> bool:
    with _lock:
        conn = _connect()
        try:
            cur = conn.execute(
                "INSERT INTO user_memories(user_id, username, key, value, source_session) "
                "VALUES (?,?,?,?,?) ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, "
                "updated_at=datetime('now','localtime')",
                (user_id, username, key, value, session_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def get_user_memories(user_id: int) -> list[dict]:
    with _lock:
        conn = _connect()
        try:
            return [dict(r) for r in conn.execute(
                "SELECT key, value, updated_at FROM user_memories WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,))]
        finally:
            conn.close()


# ── 会话摘要 ──────────────────────────────────────────────────────────────────
def _human_turn_count(session_id: str) -> int:
    with _lock:
        conn = _connect()
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM messages WHERE session_id=? AND role='user'",
                (session_id,)).fetchone()[0]
        finally:
            conn.close()


def summary_due(session_id: str) -> bool:
    """距上次摘要是否已超过 SUMMARY_EVERY_TURNS 轮。"""
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT turn FROM session_summaries WHERE session_id=?", (session_id,)).fetchone()
            last_turn = row["turn"] if row else 0
            return _human_turn_count(session_id) - last_turn >= _SUMMARY_EVERY_TURNS
        finally:
            conn.close()


def generate_summary(llm, session_id: str, history_messages: list) -> Optional[str]:
    """用 LLM 把对话历史压缩为结构化摘要并落库。"""
    from app.agent.prompts import SUMMARY_PROMPT
    # 只取最近一部分历史做摘要（控制输入）
    tail = history_messages[-12:]
    text = "\n".join(f"[{getattr(m, 'type', '?')}] {str(getattr(m, 'content', ''))[:300]}" for m in tail)
    if not text.strip():
        return None
    try:
        summary = str(llm.invoke([SystemMessage(content=SUMMARY_PROMPT.format(history=text[:3000]))]).content).strip()
    except Exception:  # noqa: BLE001
        return None
    if not summary:
        return None
    turn = _human_turn_count(session_id)
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO session_summaries(session_id, summary, turn) VALUES (?,?,?) "
                "ON CONFLICT(session_id) DO UPDATE SET summary=excluded.summary, turn=excluded.turn, "
                "updated_at=datetime('now','localtime')",
                (session_id, summary[:1000], turn))
            conn.commit()
        finally:
            conn.close()
    return summary


def get_summary(session_id: str) -> Optional[str]:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT summary FROM session_summaries WHERE session_id=?", (session_id,)).fetchone()
            return row["summary"] if row else None
        finally:
            conn.close()


# ── 相关历史检索（关键词，纯规则零成本）───────────────────────────────────────
def _keywords(query: str) -> list:
    """提取检索关键词：2+ 长度 CJK 片段 + 3+ 长度英文单词。"""
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", query or "")
    en = re.findall(r"[a-zA-Z_]{3,}", query or "")
    # 去掉纯停用词
    stop = {"什么", "怎么", "为什么", "可以", "一个", "那个", "这个", "分析", "一下", "帮我", "数据"}
    cjk = [w for w in cjk if w not in stop]
    return (cjk + en)[:_MAX_KEYWORDS]


def retrieve_relevant(session_id: str, query: str, limit: int = _RETRIEVE_LIMIT) -> list[dict]:
    """按关键词从消息表检索相关历史（user/assistant 消息），按最近优先。"""
    words = _keywords(query)
    if not words:
        return []
    with _lock:
        conn = _connect()
        try:
            conds = " OR ".join(["content LIKE ?"] * len(words))
            params = [session_id] + [f"%{w}%" for w in words]
            rows = conn.execute(
                f"SELECT role, content FROM messages WHERE session_id=? AND ({conds}) "
                f"AND role IN ('user','assistant') ORDER BY seq DESC LIMIT ?",
                tuple(params + [limit])).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []  # messages 表不存在（新库）→ 无相关历史
        finally:
            conn.close()


# ── 注入：构造记忆上下文（供 chat 输入拼接）──────────────────────────────────
def build_memory_context(user_id: int, session_id: str, query: str) -> Optional[str]:
    """拼装 长期记忆 + 会话摘要 + 相关历史 为一段注入文本；无内容返回 None。"""
    parts = []
    mems = get_user_memories(user_id)
    if mems:
        lines = "\n".join(f"- {m['key']}：{m['value']}" for m in mems[:10])
        parts.append(f"【长期记忆（用户偏好/约定）】\n{lines}")
    summary = get_summary(session_id)
    if summary:
        parts.append(f"【本会话历史摘要】\n{summary}")
    hits = retrieve_relevant(session_id, query)
    if hits:
        lines = "\n".join(f"[{h['role']}] {str(h['content'])[:200]}" for h in hits)
        parts.append(f"【与当前问题相关的历史对话】\n{lines}")
    return "\n\n".join(parts) if parts else None
