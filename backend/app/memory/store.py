"""基于内存的会话存储，支持 LRU 淘汰 + 最大轮次数截断。"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

# 一条消息保留的最大轮次（user+assistant 各算 1 条，tool 消息跟随）
MAX_TURNS = 50

# 最多同时保活的 session 数
MAX_SESSIONS = 200

# session 空闲多久后过期（秒）—— 默认 4 小时
SESSION_TTL_SECONDS = 4 * 3600


class ConversationStore:
    """线程安全的 LRU 会话存储。"""

    def __init__(
        self,
        max_turns: int = MAX_TURNS,
        max_sessions: int = MAX_SESSIONS,
        ttl: int = SESSION_TTL_SECONDS,
    ):
        self._max_turns = max_turns
        self._max_sessions = max_sessions
        self._ttl = ttl
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
        """当 HumanMessage 条数 > max_turns 时，从头部裁剪到 max_turns 以内。"""
        msgs = entry["messages"]
        # 计算 HumanMessage 数量
        human_count = sum(1 for m in msgs if isinstance(m, HumanMessage))
        if human_count <= self._max_turns:
            return
        # 找到要保留的第一条 HumanMessage 的索引
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
