"""审计日志（audit）单测 + 各接入点留痕验证。"""
import io
import json

import pandas as pd
import pytest

from app.audit import (
    record, list_audit, count_by_action,
    A_SQL_QUERY, A_CONFIG_CHANGE, A_USER_ACTION, A_SESSION_ACTION, A_FILE_UPLOAD,
)
from app.tools.agent_tools import make_tools
from app.tools.file_tool import make_file_tools


# ── 核心模块 ──────────────────────────────────────────────────────────────────
def test_record_and_list(isolated_storage):
    record(A_USER_ACTION, 1, "alice", {"action": "login"})
    record(A_USER_ACTION, 2, "bob", {"action": "login"})
    rows = list_audit()
    assert len(rows) == 2
    assert rows[0]["username"] == "bob"          # 倒序
    assert rows[0]["detail"]["action"] == "login"
    assert rows[0]["action"] == A_USER_ACTION


def test_list_filters(isolated_storage):
    record(A_USER_ACTION, 1, "alice", {"action": "login"})
    record(A_CONFIG_CHANGE, 1, "alice", {"type": "llm", "action": "create"})
    record(A_SQL_QUERY, 1, "alice", {"sql": "SELECT 1"})
    only_config = list_audit(action=A_CONFIG_CHANGE)
    assert len(only_config) == 1 and only_config[0]["action"] == A_CONFIG_CHANGE
    only_alice = list_audit(username="alice")
    assert len(only_alice) == 3
    assert list_audit(username="nobody") == []
    assert list_audit(limit=2, username="alice")  # 分页不报错


def test_list_limits_500(isolated_storage):
    for i in range(505):
        record(A_USER_ACTION, 1, "a", {"i": i})
    assert len(list_audit(limit=500)) == 500  # 上限
    assert len(list_audit()) == 100           # 默认 100


def test_detail_no_secret_policy(isolated_storage):
    """审计 detail 不应含明文密钥（合规）。"""
    record(A_CONFIG_CHANGE, 1, "admin", {"type": "llm", "name": "qwen"})
    row = list_audit()[0]
    assert "api_key" not in json.dumps(row["detail"]) and "password" not in json.dumps(row["detail"])


def test_count_by_action(isolated_storage):
    record(A_USER_ACTION, 1, "a", {})
    record(A_USER_ACTION, 1, "a", {})
    record(A_SQL_QUERY, 1, "a", {})
    counts = count_by_action()
    assert counts[A_USER_ACTION] == 2 and counts[A_SQL_QUERY] == 1


# ── SQL 留痕（工具层）────────────────────────────────────────────────────────
def test_query_mysql_writes_audit(isolated_storage, monkeypatch):
    def fake_read_sql(sql, engine):
        return pd.DataFrame({"city": ["北京"], "sales": [1]})
    monkeypatch.setattr(pd, "read_sql", fake_read_sql)
    ctx = {"user_id": 7, "username": "alice", "session_id": "s-1"}
    tools = {t.name: t for t in make_tools(engine=None, audit_ctx=ctx)}
    tools["query_mysql"].invoke({"sql": "SELECT * FROM t"})
    rows = list_audit(action=A_SQL_QUERY)
    assert len(rows) == 1
    d = rows[0]["detail"]
    assert d["sql"].endswith("LIMIT 500") and d["rows"] == 1 and d["source"] == "mysql"
    assert rows[0]["user_id"] == 7 and rows[0]["username"] == "alice"
    assert d["session_id"] == "s-1"


def test_query_mysql_no_audit_without_ctx(isolated_storage, monkeypatch):
    monkeypatch.setattr(pd, "read_sql", lambda sql, engine: pd.DataFrame({"a": [1]}))
    tools = {t.name: t for t in make_tools(engine=None)}  # 不传 audit_ctx
    tools["query_mysql"].invoke({"sql": "SELECT * FROM t"})
    assert list_audit() == []  # 向后兼容：无上下文不记录


def test_query_file_writes_audit(isolated_storage):
    df = pd.DataFrame({"a": [1, 2, 3]})
    ctx = {"user_id": 7, "username": "alice", "session_id": "s-1"}
    tools = {t.name: t for t in make_file_tools({"f.csv": df}, audit_ctx=ctx)}
    tools["query_file"].invoke({"file": "f.csv", "sql": "SELECT a FROM df"})
    rows = list_audit(action=A_SQL_QUERY)
    assert rows[0]["detail"]["source"] == "file:f.csv"
    assert rows[0]["detail"]["rows"] == 3


# ── API 接入点（集成）────────────────────────────────────────────────────────
def _register(client, name, pwd="pass1234"):
    return client.post("/api/auth/register", json={"username": name, "password": pwd}).json()["token"]


def test_auth_actions_audited(client):
    token = _register(client, "alice")                      # register → audit
    h = {"Authorization": f"Bearer {token}"}
    client.post("/api/auth/login", json={"username": "alice", "password": "pass1234"})  # login
    client.post("/api/auth/change-password",
                json={"old_password": "pass1234", "new_password": "newpass123"}, headers=h)  # change-password
    rows = list_audit(action=A_USER_ACTION)
    actions = [r["detail"].get("action") for r in rows]
    assert actions == ["change_password", "login", "register"]  # 倒序
    assert rows[-1]["username"] == "alice"


def test_role_change_audited(client):
    admin_token = _register(client, "admin1")
    user_token = _register(client, "worker1")
    admin_h = {"Authorization": f"Bearer {admin_token}"}
    users = client.get("/api/auth/users", headers=admin_h).json()
    worker = next(u for u in users if u["username"] == "worker1")
    client.put(f"/api/auth/users/{worker['id']}", json={"role": "admin"}, headers=admin_h)
    row = list_audit(action=A_USER_ACTION)[0]
    assert row["detail"]["action"] == "set_role" and row["detail"]["role"] == "admin"
    assert row["detail"]["target_user_id"] == worker["id"]
    _ = user_token  # 仅避免未使用告警


def test_config_change_audited(client, isolated_storage):
    token = _register(client, "boss")  # 第一个用户 = admin
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/config/llm", json={"name": "qwen", "provider": "qwen",
                                             "model_name": "qwen-max", "api_key": "sk-secret-x"}, headers=h)
    assert r.status_code == 200
    client.post("/api/config/db", json={"name": "订单库", "db_type": "mysql", "host": "127.0.0.1",
                                        "port": 3306, "username": "root", "password": "pw-secret"}, headers=h)
    rows = list_audit(action=A_CONFIG_CHANGE)
    assert len(rows) == 2
    llm = next(r for r in rows if r["detail"]["type"] == "llm")
    assert llm["detail"]["action"] == "create" and llm["detail"]["name"] == "qwen"
    # 合规：审计里无明文 key/password
    assert "sk-secret-x" not in json.dumps(rows) and "pw-secret" not in json.dumps(rows)
    # 删除也要留痕
    cfg_id = client.get("/api/config/llm", headers=h).json()[0]["id"]
    client.delete(f"/api/config/llm/{cfg_id}", headers=h)
    assert list_audit(action=A_CONFIG_CHANGE)[0]["detail"]["action"] == "delete"


def test_upload_audited(client, isolated_storage, monkeypatch, tmp_path):
    import app.api.chat_api as chat_api_mod
    monkeypatch.setattr(chat_api_mod, "_UPLOAD_DIR", tmp_path / "uploads")
    token = _register(client, "alice")
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/upload", files={"file": ("成绩.csv", io.BytesIO("a,b\n1,2\n".encode()), "text/csv")}, headers=h)
    assert r.status_code == 200
    rows = list_audit(action=A_FILE_UPLOAD)
    assert rows[0]["detail"]["name"] == "成绩.csv"
    assert rows[0]["detail"]["rows"] == 1


def test_session_actions_audited(client):
    token = _register(client, "alice")
    h = {"Authorization": f"Bearer {token}"}
    client.put("/api/sessions/s-1", json={"title": "新标题"}, headers=h)   # 不存在 → 404，无审计
    assert list_audit(action=A_SESSION_ACTION) == []
    # 造一个属于 alice（id=1）的会话再改名/删除
    from langchain_core.messages import HumanMessage
    from app.persistence import persist_messages
    persist_messages("s-1", [HumanMessage(content="q", id="m1")], user_id=1)
    client.put("/api/sessions/s-1", json={"title": "新标题"}, headers=h)
    client.delete("/api/sessions/s-1", headers=h)
    actions = [r["detail"].get("action") for r in list_audit(action=A_SESSION_ACTION)]
    assert actions == ["delete", "rename"]


# ── 管理查看接口 ──────────────────────────────────────────────────────────────
def test_audit_api_admin_only(client):
    admin_token = _register(client, "boss")      # 第一个注册 → admin
    user_token = _register(client, "worker")     # 第二个 → user
    user_h = {"Authorization": f"Bearer {user_token}"}
    admin_h = {"Authorization": f"Bearer {admin_token}"}
    assert client.get("/api/audit", headers=user_h).status_code == 403
    assert client.get("/api/audit", headers=admin_h).status_code == 200
    assert client.get("/api/audit").status_code == 401  # 未登录


def test_audit_api_admin_can_view(client):
    admin_token = _register(client, "boss")  # 第一个 = admin
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.get("/api/audit", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1 and body[0]["action"] == A_USER_ACTION  # register 已留痕
    # 过滤 + 概览
    assert client.get("/api/audit", params={"action": A_USER_ACTION}, headers=h).status_code == 200
    ov = client.get("/api/audit/overview", headers=h)
    assert ov.status_code == 200
    assert A_USER_ACTION in ov.json()
