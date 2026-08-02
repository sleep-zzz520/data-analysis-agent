"""密钥加密（meta/crypto.py）+ 配置加密存储（meta/store.py）单测。"""
import json

import pytest

from app.meta import crypto
from app.meta import store


# ── crypto ────────────────────────────────────────────────────────────────────
def test_encrypt_decrypt_roundtrip():
    token = crypto.encrypt("sk-1234567890")
    assert token != "sk-1234567890"          # 已加密
    assert crypto.decrypt(token) == "sk-1234567890"


def test_encrypt_same_plain_different_cipher():
    assert crypto.encrypt("x") != crypto.encrypt("x")  # Fernet 随机 IV


def test_mask():
    assert crypto.mask("sk-1234567890") == "sk-1****7890"
    assert crypto.mask("short") == "****"
    assert crypto.mask("") == ""


# ── meta store：LLM 配置 ──────────────────────────────────────────────────────
def test_save_llm_returns_masked_view(isolated_storage):
    v = store.save_llm_config({"name": "qwen", "provider": "qwen", "model_name": "qwen-max",
                               "api_key": "sk-top-secret-123"})
    assert v["api_key_masked"] == crypto.mask("sk-top-secret-123")
    assert "api_key" not in v and "api_key_enc" not in v


def test_save_llm_persists_cipher_to_disk(isolated_storage):
    store.save_llm_config({"name": "qwen", "api_key": "sk-plain-777"})
    raw = json.loads(isolated_storage.joinpath("llm_configs.json").read_text())
    assert raw[0]["api_key_enc"] != "sk-plain-777"
    assert "api_key" not in raw[0]


def test_get_llm_secret_returns_plain(isolated_storage):
    cfg_id = store.save_llm_config({"name": "qwen", "api_key": "sk-secret-1"})["id"]
    secret = store.get_llm_secret(cfg_id)
    assert secret["api_key"] == "sk-secret-1"


def test_llm_default_mutual_exclusion(isolated_storage):
    store.save_llm_config({"name": "a", "is_default": True})
    store.save_llm_config({"name": "b", "is_default": True})
    items = store.list_llm_configs()
    defaults = [i for i in items if i["is_default"]]
    assert len(defaults) == 1 and defaults[0]["name"] == "b"


def test_llm_delete(isolated_storage):
    cfg_id = store.save_llm_config({"name": "a"})["id"]
    assert store.delete_llm_config(cfg_id) is True
    assert store.delete_llm_config(cfg_id) is False  # 再删不存在


def test_llm_update_preserves_id(isolated_storage):
    cfg_id = store.save_llm_config({"name": "a", "api_key": "sk-1"})["id"]
    v = store.save_llm_config({"id": cfg_id, "name": "a2", "api_key": "sk-2"})
    assert v["id"] == cfg_id and len(store.list_llm_configs()) == 1


def test_llm_migration_plain_to_encrypted(isolated_storage):
    isolated_storage.joinpath("llm_configs.json").write_text(
        json.dumps([{"id": 1, "name": "old", "api_key": "sk-legacy"}], ensure_ascii=False))
    items = store.list_llm_configs()
    assert items[0]["api_key_masked"] == crypto.mask("sk-legacy")
    raw = json.loads(isolated_storage.joinpath("llm_configs.json").read_text())
    assert "api_key" not in raw[0] and "api_key_enc" in raw[0]  # 磁盘明文已清除


# ── meta store：DB 配置 ───────────────────────────────────────────────────────
def test_db_config_crud(isolated_storage):
    v = store.save_db_config({"name": "订单库", "db_type": "mysql", "host": "127.0.0.1",
                              "port": 3306, "username": "root", "password": "pwd-secret-9",
                              "default_schema": "share-order"})
    assert v["password_masked"] == crypto.mask("pwd-secret-9")
    assert "password" not in v and "password_enc" not in v
    assert store.get_db_secret(v["id"])["password"] == "pwd-secret-9"
    assert store.get_db_config(v["id"])["name"] == "订单库"
    assert store.delete_db_config(v["id"]) is True
    assert store.get_db_config(v["id"]) is None


def test_db_migration(isolated_storage):
    isolated_storage.joinpath("db_configs.json").write_text(
        json.dumps([{"id": 1, "name": "old", "password": "pw-legacy"}], ensure_ascii=False))
    items = store.list_db_configs()
    assert items[0]["password_masked"] == crypto.mask("pw-legacy")
    raw = json.loads(isolated_storage.joinpath("db_configs.json").read_text())
    assert "password" not in raw[0] and "password_enc" in raw[0]
