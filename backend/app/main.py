"""DataAnalysis Agent – 入口"""
import os, sys, traceback, importlib

# 让 backend/ 进 sys.path（无论从哪里启动）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="DataAnalysis Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


# ── 动态挂载业务路由 ──────────────────────────
def _try_include(mod_path: str, desc: str):
    try:
        m = importlib.import_module(mod_path)
        router = getattr(m, "router", None)
        if router is not None:
            app.include_router(router)
            print(f"[ok] 已挂载 {desc}")
        else:
            print(f"[skip] {desc}：模块里没有 router")
    except Exception:
        print(f"[skip] {desc} 未挂载 →")
        traceback.print_exc()


_try_include("app.api.chat_api", "/api/chat & /api/upload & /api/schema")
_try_include("app.api.config_api", "/api/config")
_try_include("app.api.auth_api", "/api/auth")


# ── 启动自检 ──────────────────────────────────
@app.on_event("startup")
def _check():
    paths = set()
    print("----- 已注册路由 -----")
    for r in app.routes:
        p = getattr(r, "path", None)
        if p:
            paths.add(p)
            print("  ", getattr(r, "methods", set()), p)
    print("----------------------")
    if "/api/chat" not in paths:
        print("❌ /api/chat 未注册，往上翻报错")
    else:
        print("✅ /api/chat 已就绪")
    if "/api/config/llm" not in paths:
        print("❌ /api/config/llm 未注册，往上翻报错")
    else:
        print("✅ /api/config/llm 已就绪")


if __name__ == "__main__":
    import uvicorn
    print("PYTHON =", sys.executable)
    uvicorn.run(app, host="0.0.0.0", port=8000)