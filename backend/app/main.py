"""DataAnalysis Agent – 入口"""
import os, sys, traceback, importlib

# 让 backend/ 进 sys.path（无论从哪里启动）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import setup_logging, get_logger
from app.core.middleware import ObservabilityMiddleware

setup_logging()  # 结构化 JSON 日志（LOG_JSON=0 可切人类可读格式）
logger = get_logger("main")

app = FastAPI(title="DataAnalysis Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 可观测性中间件：记录每个请求耗时/状态码 + 聚合指标（放最后注册 = 最外层先执行）
app.add_middleware(ObservabilityMiddleware)


# ── 动态挂载业务路由 ──────────────────────────────────────────
def _try_include(mod_path: str, desc: str):
    try:
        m = importlib.import_module(mod_path)
        router = getattr(m, "router", None)
        if router is not None:
            app.include_router(router)
            logger.info("router_mounted", extra={"desc": desc})
        else:
            logger.warning("router_skipped_no_router", extra={"desc": desc})
    except Exception:
        logger.error("router_mount_failed", extra={"desc": desc}, exc_info=True)


_try_include("app.api.chat_api", "/api/chat & /api/upload & /api/schema")
_try_include("app.api.config_api", "/api/config")
_try_include("app.api.auth_api", "/api/auth")
_try_include("app.api.health_api", "/api/health & /api/health/ready & /api/metrics")


# ── 启动自检 ──────────────────────────────────────────────────
@app.on_event("startup")
def _check():
    paths = set()
    logger.info("routes_registered", extra={"count": len(app.routes)})
    for r in app.routes:
        p = getattr(r, "path", None)
        if p:
            paths.add(p)
            logger.debug("route", extra={"methods": sorted(getattr(r, "methods", set()) or set()), "path": p})
    if "/api/chat" not in paths:
        logger.error("route_missing", extra={"path": "/api/chat"})
    else:
        logger.info("route_ok", extra={"path": "/api/chat"})
    if "/api/config/llm" not in paths:
        logger.error("route_missing", extra={"path": "/api/config/llm"})
    else:
        logger.info("route_ok", extra={"path": "/api/config/llm"})


if __name__ == "__main__":
    import uvicorn
    logger.info("startup", extra={"python": sys.executable})
    uvicorn.run(app, host="0.0.0.0", port=8000)
