"""审计日志查看接口（合规）：仅管理员可查询，只读。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth_api import get_current_user
from app.audit import list_audit, count_by_action

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可查看审计日志")


@router.get("")
def api_list_audit(limit: int = 100, action: Optional[str] = None, username: Optional[str] = None,
                   user: dict = Depends(get_current_user)):
    """审计记录列表（倒序）。action 取值：sql_query/config_change/user_action/session_action/file_upload。"""
    _require_admin(user)
    return list_audit(limit=limit, action=action, username=username)


@router.get("/overview")
def api_audit_overview(hours: int = 24, user: dict = Depends(get_current_user)):
    """最近 N 小时各动作计数（合规概览）。"""
    _require_admin(user)
    return count_by_action(limit_hours=hours)
