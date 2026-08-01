from __future__ import annotations
import asyncio, re, json, io, uuid, threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional, List
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import (
    HumanMessage, AIMessage, AIMessageChunk, ToolMessage, SystemMessage,
)
from app.meta.store import get_llm_secret, get_db_secret
from app.core.factories import build_llm, build_engine          # ← 用你原版 factories，函数名兼容
from app.tools.agent_tools import make_tools
from app.agent.graph import make_graph
from app.errors.classifier import classify_any                  # ← 追加进来的兜底分发
from app.db.schema import list_tables
from app.memory import get_history, save_messages, clear_session
from app.agent.graph import _filter_new_messages
from app.agent.prompts import SYSTEM_PROMPT, CONVERSATION_HINT
# ── 对话记录持久化（SQLite 镜像，不影响现有记忆系统）─────────────────────────
from app.persistence import (
    persist_messages,
    load_session as db_load_session,
    list_sessions as db_list_sessions,
    delete_session as db_delete_session,
    rename_session as db_rename_session,
    get_display_messages,
    get_session_info,
    save_upload,
    get_upload,
)

router = APIRouter()

# 上传文件落盘目录 + DataFrame 懒加载缓存（避免每次请求重复解析）
_BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/
_UPLOAD_DIR = _BACKEND_DIR / "data" / "uploads"
_file_df_cache: "OrderedDict[str, pd.DataFrame]" = OrderedDict()
_file_df_cache_lock = threading.Lock()
_FILE_DF_CACHE_MAX = 12


def _load_uploaded_dfs(file_ids: List) -> dict:
    """按 file_id 加载上传文件 DataFrame（磁盘 + LRU 缓存）。"""
    dfs: dict = {}
    for fid in file_ids:
        with _file_df_cache_lock:
            df = _file_df_cache.get(fid)
        if df is not None:
            meta = get_upload(str(fid))
            if meta:
                dfs[meta["name"]] = df
            continue
        meta = get_upload(str(fid))
        if meta is None:
            continue
        try:
            ext = Path(meta["path"]).suffix.lower()
            if ext == ".csv":
                df = pd.read_csv(meta["path"])
            else:
                df = pd.read_excel(meta["path"])
        except Exception:
            continue
        with _file_df_cache_lock:
            _file_df_cache[fid] = df
            if len(_file_df_cache) > _FILE_DF_CACHE_MAX:
                _file_df_cache.popitem(last=False)
        dfs[meta["name"]] = df
    return dfs

# 每个 session 一个 asyncio 锁：串行化同一会话的对话处理，
# 避免并发请求交错读写内存/SQLite 导致消息错乱（串话、重复）。
_chat_locks: dict = {}
_chat_locks_guard = asyncio.Lock()

async def _session_lock(sid: str) -> asyncio.Lock:
    async with _chat_locks_guard:
        lock = _chat_locks.get(sid)
        if lock is None:
            lock = asyncio.Lock()
            _chat_locks[sid] = lock
        return lock

def _release_session_lock(sid: str) -> None:
    """会话被删除时释放其锁（避免字典无限增长）。"""
    _chat_locks.pop(sid, None)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    llm_config_id: int
    db_config_id: int
    file_ids: List = []

_CHART_RE = re.compile(r"<!--CHART:(.*?)-->", re.S)
_TABLE_RE = re.compile(r"<!--TABLE:(.*?)-->", re.S)
_IMAGE_RE = re.compile(r"<!--IMAGE_BASE64:(.*?)-->", re.S)

def _extract(messages):
    """从工具结果中提取本轮所有图表/表格/SQL（支持一轮多个，不再覆盖）。"""
    visuals: List[dict] = []   # [{chart, image}]
    tables: List[dict] = []
    sql = None
    for m in messages:
        if isinstance(m, ToolMessage) and m.content:
            item: dict = {}
            mc = _CHART_RE.search(m.content)
            if mc:
                try: item["chart"] = json.loads(mc.group(1))
                except Exception: pass
            mi = _IMAGE_RE.search(m.content)
            if mi:
                item["image"] = mi.group(1)
            if item:
                visuals.append(item)
            for mt in _TABLE_RE.finditer(m.content):
                try: tables.append(json.loads(mt.group(1)))
                except Exception: pass
        if isinstance(m, AIMessage):
            for tc in (getattr(m, "tool_calls", None) or []):
                if tc.get("name") in ("query_mysql", "run_sql"):
                    sql = tc.get("args", {}).get("sql") or sql
    return visuals, tables, sql

# ── 辅助：若内存 store 无该 session 但 SQLite 有，则从 SQLite 恢复 ──────────
def _ensure_loaded(sid: str) -> None:
    """保证内存 store 中有该 session 的历史（从 SQLite 懒加载）。"""
    if get_history(sid):
        return
    db_msgs = db_load_session(sid)
    if db_msgs:
        save_messages(sid, db_msgs)


@router.post("/api/chat")
async def chat(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    lock = await _session_lock(sid)
    async with lock:  # 同一会话串行处理，避免并发交错
        try:
            llm = build_llm(get_llm_secret(req.llm_config_id))
            db_cfg = get_db_secret(req.db_config_id)
            engine = build_engine(db_cfg)
            # 上传文件 → DataFrame 字典（供 file_tool 真实查询，磁盘+LRU）
            uploaded_files = _load_uploaded_dfs(req.file_ids)
            tools = make_tools(engine, db_cfg.get("default_schema"), files=uploaded_files)
            graph = make_graph(llm, tools)

            ctx = ""
            for fid in req.file_ids:
                meta = get_upload(str(fid))
                if meta:
                    ctx += f"\n[用户上传文件 {meta['name']}] 列：{meta['columns']} 预览行：{meta['preview_rows']}\n"
            user_text = (ctx + "\n" + req.message) if ctx else req.message

            # ── 多轮对话：先从 SQLite 懒加载（服务重启后自动恢复）───────────────
            _ensure_loaded(sid)
            history = get_history(sid)
            input_messages = [
                SystemMessage(content=SYSTEM_PROMPT + "\n\n" + CONVERSATION_HINT)
            ] + history + [HumanMessage(content=user_text)]

            result = await asyncio.to_thread(graph.invoke, {"messages": input_messages})
            result_messages = result["messages"]

            # 提取本轮新增消息并保存到内存记忆（包括用户输入和 Agent 回复）
            new_msgs = _filter_new_messages(input_messages, result_messages)
            user_msg = HumanMessage(content=user_text, id=str(uuid.uuid4()))
            for m in new_msgs:
                if not getattr(m, "id", None):
                    m.id = str(uuid.uuid4())  # 稳定 ID，供 SQLite 幂等去重
            save_messages(sid, [user_msg] + new_msgs)

            # ── 持久化：把内存 store 的完整历史同步到 SQLite（幂等去重）────
            persist_messages(sid, get_history(sid))

            msgs = result_messages
            visuals, tables, sql = _extract(msgs)
            reply = msgs[-1].content if isinstance(msgs[-1], AIMessage) else ""
            # chart/table 字段保留兼容（取最后一个），前端主用 visuals/tables 数组
            return {
                "reply": reply,
                "visuals": visuals,
                "tables": tables,
                "chart": visuals[-1].get("chart") if visuals else None,
                "table": tables[-1] if tables else None,
                "sql": sql,
                "session_id": sid,
            }
        except Exception as e:
            return {"reply": None, "chart": None, "table": None, "sql": None, "session_id": sid, "error": classify_any(e)}


def _sse(obj: dict) -> str:
    """SSE 事件帧。"""
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式对话接口（SSE）。

    事件类型（JSON 的 type 字段）：
      - delta: {"type":"delta","text":"..."}      回复文本增量
      - done:  {"type":"done","reply","chart","table","sql","session_id"}  最终结果
      - error: {"type":"error","error":{...},"session_id"}                 异常
    """
    sid = req.session_id or str(uuid.uuid4())
    lock = await _session_lock(sid)

    async def gen():
        async with lock:  # 同一会话串行处理，避免并发交错
            try:
                llm = build_llm(get_llm_secret(req.llm_config_id))
                db_cfg = get_db_secret(req.db_config_id)
                engine = build_engine(db_cfg)
                # 上传文件 → DataFrame 字典（供 file_tool 真实查询）
                uploaded_files = {}
                uploaded_files = _load_uploaded_dfs(req.file_ids)
                tools = make_tools(engine, db_cfg.get("default_schema"), files=uploaded_files)
                graph = make_graph(llm, tools)

                ctx = ""
                for fid in req.file_ids:
                    meta = get_upload(str(fid))
                    if meta:
                        ctx += f"\n[用户上传文件 {meta['name']}] 列：{meta['columns']} 预览行：{meta['preview_rows']}\n"
                user_text = (ctx + "\n" + req.message) if ctx else req.message

                _ensure_loaded(sid)
                history = get_history(sid)
                input_messages = [
                    SystemMessage(content=SYSTEM_PROMPT + "\n\n" + CONVERSATION_HINT)
                ] + history + [HumanMessage(content=user_text)]

                # 双流模式：
                #  - "messages"：token 级文本 → 推送给前端（打字机效果）
                #  - "updates" ：每步完整消息 → 本地收集，用于保存/提取图表
                all_new: List = []
                async for mode, data in graph.astream(
                    {"messages": input_messages},
                    stream_mode=["messages", "updates"],
                ):
                    if mode == "messages":
                        chunk, _meta = data
                        if isinstance(chunk, AIMessageChunk) and chunk.content:
                            yield _sse({"type": "delta", "text": chunk.content})
                    elif mode == "updates":
                        for _node, val in data.items():
                            msgs = val.get("messages") or []
                            if msgs:
                                all_new.extend(msgs)

                # ── 保存（内存 + SQLite），与同步接口一致 ────────────────
                user_msg = HumanMessage(content=user_text, id=str(uuid.uuid4()))
                for m in all_new:
                    if not getattr(m, "id", None):
                        m.id = str(uuid.uuid4())
                save_messages(sid, [user_msg] + list(all_new))
                persist_messages(sid, get_history(sid))

                # ── 提取图表/SQL，发送最终结果 ────────────────────────────
                result_messages = list(input_messages) + list(all_new)
                visuals, tables, sql = _extract(result_messages)
                reply = ""
                for m in reversed(result_messages):
                    if isinstance(m, AIMessage) and m.content:
                        reply = m.content
                        break
                yield _sse({
                    "type": "done",
                    "reply": reply,
                    "visuals": visuals,
                    "tables": tables,
                    "chart": visuals[-1].get("chart") if visuals else None,
                    "table": tables[-1] if tables else None,
                    "sql": sql,
                    "session_id": sid,
                })
            except Exception as e:
                yield _sse({"type": "error", "error": classify_any(e), "session_id": sid})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    name = file.filename or "file"
    raw = await file.read()
    ext = name.rsplit(".", 1)[-1].lower()
    try:
        if ext == "csv":
            df = pd.read_csv(io.BytesIO(raw))
        elif ext in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            raise ValueError(f"暂不支持 .{ext}，请上传 csv/xlsx")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败：{e}")
    fid = str(uuid.uuid4())
    # 文件本体落盘（重启不丢），元信息写入 SQLite
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = _UPLOAD_DIR / f"{fid}.{ext}"
    file_path.write_bytes(raw)
    cols = list(df.columns)
    d2 = df.head(5)
    preview = d2.where(d2.notna(), None).values.tolist()
    save_upload(fid, name, str(file_path), cols, preview)
    return {"file_id": fid, "columns": cols, "preview_rows": preview}


@router.delete("/api/chat/{session_id}")
def clear_chat(session_id: str):
    """清除指定会话的对话历史（前端点击「新对话」时可调用）。"""
    clear_session(session_id)
    return {"ok": True}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  对话记录持久化 API（会话列表 / 历史详情 / 删除）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/api/sessions")
def api_list_sessions(limit: int = 50):
    """列出所有历史会话（含标题、最后更新时间、消息条数）。"""
    return db_list_sessions(limit)


@router.get("/api/sessions/{session_id}")
def api_get_session(session_id: str):
    """获取指定会话的元信息 + 显示用消息列表。"""
    info = get_session_info(session_id)
    if info is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    info["messages"] = get_display_messages(session_id)
    return info


@router.delete("/api/sessions/{session_id}")
def api_delete_session(session_id: str):
    """从 SQLite 永久删除指定会话及其所有消息。"""
    # 同时清除内存 store（若还在）
    clear_session(session_id)
    _release_session_lock(session_id)
    deleted = db_delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


class RenameRequest(BaseModel):
    title: str


@router.put("/api/sessions/{session_id}")
def api_rename_session(session_id: str, req: RenameRequest):
    """重命名会话标题。"""
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    if len(title) > 60:
        raise HTTPException(status_code=400, detail="标题过长（最多 60 字）")
    if not db_rename_session(session_id, title):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True, "session_id": session_id, "title": title}


@router.get("/api/schema")
def get_schema(db_config_id: int, schema: Optional[str] = None):
    try:
        db_cfg = get_db_secret(db_config_id)
        engine = build_engine(db_cfg)
        return {"tables": list_tables(engine, schema or db_cfg.get("default_schema"))}
    except Exception as e:
        err = classify_any(e)
        raise HTTPException(status_code=400, detail=f"{err['message']} {err['suggestion']}")
