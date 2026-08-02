"""结构化日志：标准库 logging + JSON 格式输出（无第三方依赖）。

用法：
    from app.core.logging import setup_logging, get_logger
    setup_logging()                          # 启动时调用一次
    logger = get_logger("chat")
    logger.info("chat_start", extra={"session_id": sid, "user": uid})

extra 中的自定义字段会原样进 JSON（如 method/path/status/duration_ms），
方便后续接日志采集（ELK / Loki）与告警。
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

# LogRecord 自带属性：extra 里若使用同名键会冲突，这里收集后跳过
_RESERVED_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class JsonFormatter(logging.Formatter):
    """单行 JSON 日志：ts / level / logger / msg / exc / 自定义 extra 字段。"""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        for k, v in record.__dict__.items():
            if k not in _RESERVED_ATTRS and not k.startswith("_"):
                try:
                    json.dumps(v)          # 只带可序列化字段，避免脏数据撑爆日志
                    data[k] = v
                except (TypeError, ValueError):
                    data[k] = repr(v)
        return json.dumps(data, ensure_ascii=False, default=str)


class PlainFormatter(logging.Formatter):
    """本地调试用的人类可读格式（LOG_JSON=0 时生效）。"""

    def format(self, record: logging.LogRecord) -> str:
        base = f"[{record.levelname}] {record.name}: {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging(level: str = None, json_logs: bool = None, stream=None) -> None:
    """配置 root logger。可被环境变量覆盖：LOG_LEVEL、LOG_JSON（默认 JSON=1）。

    - level:     "DEBUG"/"INFO"/"WARNING"...
    - json_logs: True → JsonFormatter；False → 人类可读格式
    - stream:    输出流，默认 sys.stdout（测试可传入 StringIO）
    幂等：重复调用会清掉旧 handlers。
    """
    level = level or os.getenv("LOG_LEVEL", "INFO")
    if json_logs is None:
        json_logs = os.getenv("LOG_JSON", "1") != "0"
    stream = stream or sys.stdout

    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter() if json_logs else PlainFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # 第三方库的噪音日志压低，避免刷屏
    for noisy in ("uvicorn.access", "httpx", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
