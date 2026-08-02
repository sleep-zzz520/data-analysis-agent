"""pytest 全局配置。

关键点：
- 必须在导入任何 app 模块之前设置 AGENT_MASTER_KEY，
  因为 app.meta.crypto 在 import 时就会加载主密钥（否则会读写真实 backend/data/.master_key）。
- isolated_storage fixture 把所有落盘点（SQLite、配置 JSON、JWT 密钥）重定向到 pytest 临时目录，
  保证测试绝不触碰真实 backend/data/。
"""
import os
import sys
from pathlib import Path

from cryptography.fernet import Fernet

# 合法的 Fernet 密钥（32 字节 url-safe base64）；必须是合法格式否则 crypto 导入即失败
os.environ.setdefault("AGENT_MASTER_KEY", Fernet.generate_key().decode())

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth as auth_mod  # noqa: E402
from app import persistence as persistence_mod  # noqa: E402
from app.meta import store as meta_store_mod  # noqa: E402


@pytest.fixture()
def isolated_storage(tmp_path, monkeypatch):
    """把 persistence SQLite、meta store JSON、JWT 密钥全部重定向到临时目录。"""
    monkeypatch.setattr(persistence_mod, "_DB_DIR", tmp_path)
    monkeypatch.setattr(persistence_mod, "_DB_PATH", tmp_path / "chat_history.db")
    monkeypatch.setattr(meta_store_mod, "_LLM_FILE", tmp_path / "llm_configs.json")
    monkeypatch.setattr(meta_store_mod, "_DB_FILE", tmp_path / "db_configs.json")
    monkeypatch.setattr(auth_mod, "_SECRET_FILE", tmp_path / ".jwt_secret")
    return tmp_path


@pytest.fixture()
def client(isolated_storage):
    """FastAPI TestClient（认证/配置接口集成测试用）。"""
    from app.main import app
    with TestClient(app) as c:
        yield c
