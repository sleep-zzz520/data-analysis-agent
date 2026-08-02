"""基于内存的会话存储，支持 LRU 淘汰 + token 预算制截断。"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

# 上下文 token 预算（输入历史 + 当前消息的总预算，近似值，无 tokenizer 依赖）
MAX_TOKENS = 8000

# 兜底：消息绝对轮数上限（防止极端短消息导致预算内无限堆积；预算优先）
MAX_TURNS = 200

# 最多同时保活的 session 数
MAX_SESSIONS = 200

# session 空闲多久后过期（秒）—— 默认 4 小时
SESSION_TTL_SECONDS = 4 * 3600


def estimate_tokens(text) -> int:
    """近似 token 估算：中文约 1 字≈1.5 token，其余约 4 字符≈1 token。

    无 tokenizer 依赖的保守估算（偏大，宁可多裁）；纯函数可单测。
    """
    if not text:
        return 0
    # CJK 字符计 1.5，其余按 4 字符/token（ASCII 平均偏保守）
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return max(1, int(cjk * 1.5 + other / 4))


def budget_history(messages: list, budget: int) -> list:
    """按 token 预算从头部裁剪历史，保留最近的会话内容。

    返回新的消息列表（不修改入参）；至少保留最后一条消息，避免空历史。
    """
    if budget <= 0 or not messages:
        return messages
    keep: list = []
    used = 0
    for m in reversed(messages):
        cost = estimate_tokens(getattr(m, "content", None) or "")
        if keep and used + cost > budget:
            break
        keep.insert(0, m)
        used += cost
    return keep


class ConversationStore:
    """线程安全的 LRU 会话存储。"""

    def __init__(
        self,
        max_turns: int = MAX_TURNS,
        max_sessions: int = MAX_SESSIONS,
        ttl: int = SESSION_TTL_SECONDS,
        max_tokens: int = MAX_TOKENS,
    ):
        self._max_turns = max_turns
        self._max_sessions = max_sessions
        self._ttl = ttl
        self._max_tokens = max_tokens
        # key: session_id, value: {"messages": [...], "last_access": timestamp}
        self._data: OrderedDict[str, dict] = OrderedDict()
        self._lock = threading.Lock()

    # ── public ──────────────────────────────────────────────────────────────

    def get(self, session_id: str) -> list:
        """返回该 session 的消息列表；不存在则返回空列表。"""
        with self._lock:
            entry = self._data.get(session_id)
            if entry is None:
                return []
            if time.time() - entry["last_access"] > self._ttl:
                del self._data[session_id]
                return []
            self._data.move_to_end(session_id)  # LRU 刷新
            entry["last_access"] = time.time()
            return list(entry["messages"])  # 返回副本

    def save(self, session_id: str, messages: list) -> None:
        """
        追加本轮新消息到 session 历史，超出 max_turns 时从头部裁剪。
        messages 应包含本轮完整的 user→tool→assistant 链。
        """
        with self._lock:
            entry = self._data.get(session_id)
            if entry is None:
                entry = {"messages": [], "last_access": time.time()}
                self._data[session_id] = entry

            # 追加新消息
            entry["messages"].extend(messages)
            entry["last_access"] = time.time()

            # 超出 max_turns 时按 HumanMessage 为边界从头部裁剪
            self._trim(entry)

            # LRU 淘汰过多 session
            self._data.move_to_end(session_id)
            while len(self._data) > self._max_sessions:
                self._data.popitem(last=False)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._data.pop(session_id, None)

    def clear_all(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        with self._lock:
            return {
                "active_sessions": len(self._data),
                "max_sessions": self._max_sessions,
                "max_turns": self._max_turns,
            }

    # ── internal ─────────────────────────────────────────────────────────────

    def _trim(self, entry: dict) -> None:
        """按 token 预算从头部裁剪（保留最近的会话内容）；轮数上限兜底。"""
        msgs = entry["messages"]

        # 1) token 预算优先：总估算超预算时从头部删消息，直到预算内
        total = sum(estimate_tokens(getattr(m, "content", None) or "") for m in msgs)
        while total > self._max_tokens and len(msgs) > 1:
            total -= estimate_tokens(getattr(msgs[0], "content", None) or "")
            msgs.pop(0)

        # 2) 轮数兜底：HumanMessage 条数 > max_turns 时仍裁剪（极端短消息场景）
        human_count = sum(1 for m in msgs if isinstance(m, HumanMessage))
        if human_count <= self._max_turns:
            return
        to_remove = human_count - self._max_turns
        removed = 0
        cut_idx = 0
        for i, m in enumerate(msgs):
            if isinstance(m, HumanMessage):
                removed += 1
                if removed > to_remove:
                    cut_idx = i
                    break
        entry["messages"] = msgs[cut_idx:]
