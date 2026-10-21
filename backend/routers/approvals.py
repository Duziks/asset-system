# -*- coding: utf-8 -*-
"""业务审批模块: 设备采购/出差/报销/用印/合同
规则: 金额超过5万元 -> 部门主管审批后需董事长终审; 5万元以下主管审批即办结
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_user, log_action
from db import ex, q, q1

router = APIRouter(prefix="/api/approvals", tags=["业务审批"])

ATYPES = ["设备采购", "出差申请", "费用报销", "用印申请", "合同审批"]
THRESHOLD = 50000  # 董事长终审金额阈值(元)


class ApprovalBody(BaseModel):
    atype: str
    title: str
    reason: str = ""
    amount: float = 0
    company_id: int | None = None


@router.get("")
def my_approvals(user: dict = Depends(get_current_user)):
    """我发起的 + 待我审批的"""
    mine = q("""SELECT a.*, c.name company_name FROM approvals a
              LEFT JOIN companies c ON c.id=a.company_id
              WHERE a.applicant_id=? ORDER BY a.created_at DESC""", (user["id"],))
    todo = []
    if user["role"] == "supervisor":
        todo = q("SELECT a.*, c.name company_name FROM approvals a LEFT JOIN companies c ON c.id=a.company_id WHERE a.status='待主管审批' ORDER BY a.created_at")
    elif user["role"] == "chairman":
        todo = q("SELECT a.*, c.name company_name FROM approvals a LEFT JOIN companies c ON c.id=a.company_id WHERE a.status='待董事长审批' ORDER BY a.created_at")
    return {"mine": mine, "todo": todo}


@router.post("")
def submit(body: ApprovalBody, request: Request, user: dict = Depends(get_current_user)):
    if body.atype not in ATYPES:
        raise HTTPException(400, "无效的审批类型")
    if not body.title.strip():
        raise HTTPException(400, "标题不能为空")
    need_chair = body.amount > THRESHOLD
    node = "待董事长审批" if (need_chair and user["role"] == "supervisor") else \
           ("待主管审批" if user["role"] != "supervisor" else "待董事长审批" if need_chair else "待主管审批")
    status = "待董事长审批" if node == "待董事长审批" else "待主管审批"
    # 员工/企业用户发起 -> 主管; 主管发起超5万 -> 董事长; 主管发起5万内 -> 自主办结? 按文档仍需上级, 简化为主管发起直接待董事长(如有超额)否则待主管池由其他主管处理
    aid = ex("""INSERT INTO approvals(atype,title,reason,amount,applicant_id,applicant,company_id,status,current_node,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",
             (body.atype, body.title, body.reason, body.amount, user["id"], user["name"],
              body.company_id or user["company_id"], status, "部门主管" if status == "待主管审批" else "董事长",
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    ex("""INSERT INTO approval_logs(approval_id,approver,approver_role,action,comment,created_at)
        VALUES(?,?,?,?,?,?)""",
       (aid, user["name"], "申请人", "提交", f"{body.atype}申请提交，金额{body.amount:.2f}元" +
        ("，超5万元需董事长终审" if need_chair else ""), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "业务审批", "提交审批", f"{body.atype}:{body.title}", request)
    return {"id": aid, "status": status}


def _get(aid: int):
    a = q1("SELECT * FROM approvals WHERE id=?", (aid,))
    if not a:
        raise HTTPException(404, "审批单不存在")
    return a


@router.get("/{aid}")
def detail(aid: int, user: dict = Depends(get_current_user)):
    a = _get(aid)
    a["company_name"] = (q1("SELECT name FROM companies WHERE id=?", (a["company_id"],)) or {}).get("name")
    a["logs"] = q("SELECT * FROM approval_logs WHERE approval_id=? ORDER BY id", (aid,))
    return a


@router.post("/{aid}/action")
def action(aid: int, request: Request, act: str = "通过", comment: str = "",
           user: dict = Depends(get_current_user)):
    a = _get(aid)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if act not in ("通过", "驳回"):
        raise HTTPException(400, "无效操作")
    if user["role"] == "supervisor":
        if a["status"] != "待主管审批":
            raise HTTPException(400, "当前状态无需主管审批")
        if act == "通过":
            if a["amount"] > THRESHOLD:
                ex("UPDATE approvals SET status='待董事长审批', current_node='董事长' WHERE id=?", (aid,))
                comment = comment or "情况属实，同意，报董事长终审"
            else:
                ex("UPDATE approvals SET status='已通过', current_node='已办结', finished_at=? WHERE id=?", (now, aid))
        else:
            ex("UPDATE approvals SET status='已驳回', current_node='已办结', finished_at=? WHERE id=?", (now, aid))
    elif user["role"] == "chairman":
        if a["status"] != "待董事长审批":
            raise HTTPException(400, "当前无需董事长审批")
        st = "已通过" if act == "通过" else "已驳回"
        ex("UPDATE approvals SET status=?, current_node='已办结', finished_at=? WHERE id=?", (st, now, aid))
    else:
        raise HTTPException(403, "无审批权限")
    ex("""INSERT INTO approval_logs(approval_id,approver,approver_role,action,comment,created_at)
        VALUES(?,?,?,?,?,?)""",
       (aid, user["name"], "主管" if user["role"] == "supervisor" else "董事长", act, comment, now))
    log_action(user, "业务审批", f"审批{'通过' if act == '通过' else '驳回'}", f"#{aid} {a['title']}", request)
    return {"ok": True}
