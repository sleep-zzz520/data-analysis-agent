"""token 用量报表与预算配置接口（管理端，仅管理员）。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth_api import get_current_user
from app.usage import (
    summary_by_day, summary_by_user, summary_by_model, list_logs,
    get_budget_config, set_budget_config,
)

router = APIRouter(prefix="/api/usage", tags=["usage"])


def _require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(403, "仅管理员可查看用量报表")


@router.get("/summary")
def api_summary(days: int = 7, user: dict = Depends(get_current_user)):
    """按天汇总：调用次数 / input / output token / 成本。"""
    _require_admin(user)
    return summary_by_day(days=max(1, min(days, 90)))


@router.get("/by_user")
def api_by_user(days: int = 7, user: dict = Depends(get_current_user)):
    """按用户汇总（成本降序）。"""
    _require_admin(user)
    return summary_by_user(days=max(1, min(days, 90)))


@router.get("/by_model")
def api_by_model(days: int = 7, user: dict = Depends(get_current_user)):
    """按模型汇总（成本降序）。"""
    _require_admin(user)
    return summary_by_model(days=max(1, min(days, 90)))


@router.get("/logs")
def api_logs(limit: int = 100, user: dict = Depends(get_current_user)):
    """用量明细（倒序）。"""
    _require_admin(user)
    return list_logs(limit=limit)


class BudgetConfigReq(BaseModel):
    daily_budget_usd: float = 0
    monthly_budget_usd: float = 0


@router.get("/config")
def api_get_budget(user: dict = Depends(get_current_user)):
    """读取预算配置（0 = 不限）。"""
    _require_admin(user)
    return get_budget_config()


@router.put("/config")
def api_set_budget(req: BudgetConfigReq, user: dict = Depends(get_current_user)):
    """设置预算：daily_budget_usd / monthly_budget_usd（USD，0 表示不限）。"""
    _require_admin(user)
    return set_budget_config(req.daily_budget_usd, req.monthly_budget_usd)
