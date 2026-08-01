# app/meta/crypto.py —— 主密钥自举：环境变量优先，否则自动生成并落盘（本地零配置也能跑）
import os
from pathlib import Path
from cryptography.fernet import Fernet

# 用 __file__ 推导 backend/ 绝对路径，避免从不同工作目录启动时密钥文件分裂
_BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
_DEFAULT_SECRET_FILE = str(_BASE_DIR / "data" / ".master_key")

def _load_master_key() -> bytes:
    env_key = os.getenv("AGENT_MASTER_KEY")          # 部署方可显式指定
    if env_key:
        return env_key.encode()
    secret_file = Path(os.getenv("AGENT_SECRET_FILE", _DEFAULT_SECRET_FILE))
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if secret_file.exists():
        return secret_file.read_bytes().strip()
    key = Fernet.generate_key()                       # 首次启动自动生成
    secret_file.write_bytes(key)
    try: secret_file.chmod(0o600)                     # 仅本人可读
    except Exception: pass
    return key

_fernet = Fernet(_load_master_key())

def encrypt(plain: str) -> str:  return _fernet.encrypt(plain.encode()).decode()
def decrypt(token: str) -> str:  return _fernet.decrypt(token.encode()).decode()
def mask(plain: str) -> str:     # 回显脱敏：sk-****1234
    if not plain: return ""
    return plain[:4] + "****" + plain[-4:] if len(plain) > 8 else "****"