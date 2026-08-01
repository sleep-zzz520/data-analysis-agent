"""用户认证：密码哈希(pbkdf2) + JWT 签发/校验。"""
from __future__ import annotations

import hashlib, os, time
from pathlib import Path
from typing import Optional

import jwt

_BASE_DIR = Path(__file__).resolve().parents[1]  # backend/
_SECRET_FILE = _BASE_DIR / "data" / ".jwt_secret"
_TOKEN_TTL = 7 * 24 * 3600  # 7 天


def _load_secret() -> str:
    """JWT 签名密钥，首次启动自动生成。"""
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_text().strip()
    _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    secret = os.urandom(32).hex()
    _SECRET_FILE.write_text(secret)
    _SECRET_FILE.chmod(0o600)
    return secret


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """pbkdf2 加盐哈希，格式: salt$hex。"""
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hash_password(password, salt) == stored


def create_token(user_id: int, username: str, role: str = "user") -> str:
    return jwt.encode(
        {"uid": user_id, "username": username, "role": role, "exp": int(time.time()) + _TOKEN_TTL},
        _load_secret(), algorithm="HS256",
    )


def decode_token(token: str) -> Optional[dict]:
    """校验 token，返回 payload；无效/过期返回 None。"""
    try:
        return jwt.decode(token, _load_secret(), algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
