"""Conversation memory — 按 session 管理多轮对话历史消息。"""
from app.memory.store import ConversationStore

# 全局单例，进程级内存
_store = ConversationStore()


def get_history(session_id: str) -> list:
    """获取指定 session 的完整消息历史（LangChain Message 对象列表）。"""
    return _store.get(session_id)


def save_messages(session_id: str, messages: list) -> None:
    """将本轮完整消息（含 tool 调用）保存到 session。"""
    _store.save(session_id, messages)


def clear_session(session_id: str) -> None:
    """清除指定 session 的历史。"""
    _store.clear(session_id)
