# -*- coding: utf-8 -*-
"""企业规范提醒模块: 法规政策/制度执行/证照到期/审计提醒/风险提示"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_user, log_action, require_roles
from db import ex, q, q1

router = APIRouter(prefix="/api/reminders", tags=["企业规范提醒"])


class PolicyBody(BaseModel):
    title: str
    category: str = "国家政策"
    content: str = ""
    source: str = ""


class RuleBody(BaseModel):
    title: str
    content: str = ""
    remind_date: str
    target: str = "全部企业"


@router.get("/policies")
def list_policies(user: dict = Depends(get_current_user)):
    return q("SELECT * FROM policies ORDER BY publish_date DESC")


@router.post("/policies")
def add_policy(body: PolicyBody, request: Request, user: dict = Depends(require_roles("admin", "secretary"))):
    pid = ex("""INSERT INTO policies(title,category,content,publish_date,source)
              VALUES(?,?,?,?,?)""",
             (body.title, body.category, body.content, datetime.now().strftime("%Y-%m-%d"), body.source))
    # 同步站内消息
    ex("""INSERT INTO messages(title,content,channel,receiver,status,created_at)
        VALUES(?,?,?,?, '未读', ?)""",
       (f"法规政策更新：{body.title}", body.content[:120], "系统", "all",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "企业规范提醒", "发布法规政策", body.title, request)
    return {"id": pid}


@router.delete("/policies/{pid}")
def del_policy(pid: int, request: Request, user: dict = Depends(require_roles("admin", "secretary"))):
    ex("DELETE FROM policies WHERE id=?", (pid,))
    return {"ok": True}


@router.get("/rules")
def list_rules(user: dict = Depends(get_current_user)):
    return q("SELECT * FROM rule_reminders ORDER BY remind_date")


@router.post("/rules")
def add_rule(body: RuleBody, request: Request, user: dict = Depends(require_roles("admin", "secretary"))):
    rid = ex("INSERT INTO rule_reminders(title,content,remind_date,target,status) VALUES(?,?,?,?,'待处理')",
             (body.title, body.content, body.remind_date, body.target))
    log_action(user, "企业规范提醒", "新增制度提醒", body.title, request)
    return {"id": rid}


@router.put("/rules/{rid}/done")
def finish_rule(rid: int, request: Request, user: dict = Depends(require_roles("admin", "secretary"))):
    ex("UPDATE rule_reminders SET status='已完成' WHERE id=?", (rid,))
    return {"ok": True}


@router.get("/certificates")
def cert_alerts(user: dict = Depends(get_current_user)):
    """证照到期提醒(3个月内到期或已过期)"""
    rows = q("""SELECT ct.*, c.name company_name FROM certificates ct
              JOIN companies c ON c.id=ct.company_id
              WHERE ct.status IN ('即将到期','已过期') AND c.deleted=0
              ORDER BY ct.expire_date""")
    return rows


@router.get("/audit-overdue")
def audit_overdue(user: dict = Depends(get_current_user)):
    """逾期未审计企业清单(每周自动遍历筛选, 到期日前30天预警)"""
    cs = q("SELECT * FROM companies WHERE deleted=0 AND status='正常'")
    now = datetime.now()
    out = []
    for c in cs:
        if not c["last_audit_date"]:
            out.append({**c, "due_date": "未审计", "overdue_days": 999})
            continue
        try:
            last = datetime.strptime(c["last_audit_date"], "%Y-%m-%d")
        except ValueError:
            continue
        due = last.replace(year=last.year + (c["audit_cycle"] or 1))
        days = (now - due).days
        if days >= -30:  # 到期前30天开始提醒
            out.append({**c, "due_date": due.strftime("%Y-%m-%d"), "overdue_days": days})
    out.sort(key=lambda x: -x["overdue_days"])
    return out


@router.post("/audit/{cid}/record")
def record_audit(cid: int, request: Request, result: str = "通过",
                 user: dict = Depends(require_roles("admin", "secretary", "supervisor"))):
    c = q1("SELECT name FROM companies WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "企业不存在")
    ex("UPDATE companies SET last_audit_date=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d"), cid))
    log_action(user, "企业规范提醒", "登记审计完成", c["name"], request)
    return {"ok": True}


@router.get("/risks")
def list_risks(status: str = "", user: dict = Depends(get_current_user)):
    sql = """SELECT ra.*, c.name company_name FROM risk_alerts ra
           JOIN companies c ON c.id=ra.company_id AND c.deleted=0"""
    params = []
    if status:
        sql += " WHERE ra.status=?"
        params.append(status)
    return q(sql + " ORDER BY ra.created_at DESC", params)


@router.put("/risks/{rid}/handle")
def handle_risk(rid: int, request: Request, user: dict = Depends(require_roles("admin", "secretary", "supervisor", "chairman"))):
    ex("UPDATE risk_alerts SET status='已处理' WHERE id=?", (rid,))
    log_action(user, "企业规范提醒", "处理风险告警", f"risk#{rid}", request)
    return {"ok": True}
