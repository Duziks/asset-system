# -*- coding: utf-8 -*-
"""企业信息管理模块: 录入/维护/查询/股权/文档/证照"""
import json
import os
import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from auth import get_current_user, log_action, require_roles
from db import UPLOAD_DIR, ex, q, q1

router = APIRouter(prefix="/api/companies", tags=["企业信息管理"])


class CompanyBody(BaseModel):
    name: str
    credit_code: str | None = None
    ctype: str = "参股"
    legal_rep: str = ""
    phone: str = ""
    email: str = ""
    reg_capital: float = 0
    address: str = ""
    founded_date: str | None = None
    biz_scope: str = ""
    industry: str = ""
    scale: str = ""
    emp_count: int = 0
    assets: float = 0
    revenue: float = 0
    profit: float = 0
    holder_ratio: float = 0
    audit_cycle: int = 1
    ext: dict = {}


class ExtBody(BaseModel):
    ext: dict


class EquityBody(BaseModel):
    shareholder: str
    ratio: float = 0
    method: str = "货币出资"
    invest_time: str | None = None
    remark: str = ""


class CertBody(BaseModel):
    cert_name: str
    cert_no: str = ""
    expire_date: str
    status: str = "有效"


def _calc_cert_status(expire_date: str) -> str:
    try:
        d = datetime.strptime(expire_date, "%Y-%m-%d")
        days = (d - datetime.now()).days
    except ValueError:
        return "有效"
    if days < 0:
        return "已过期"
    if days <= 90:
        return "即将到期"
    return "有效"


def _audit_overdue(c: dict) -> bool:
    """审计是否逾期: 按审计周期(年)与上次审计日期判断"""
    if not c.get("last_audit_date"):
        return True
    try:
        last = datetime.strptime(c["last_audit_date"], "%Y-%m-%d")
    except ValueError:
        return True
    due = last.year + c.get("audit_cycle", 1)
    return datetime.now().year > due or (datetime.now().year == due and datetime.now().month > last.month)


def _with_flags(c: dict) -> dict:
    if c.get("ext"):
        try:
            c["ext"] = json.loads(c["ext"]) if isinstance(c["ext"], str) else c["ext"]
        except (json.JSONDecodeError, TypeError):
            c["ext"] = {}
    c["audit_overdue"] = _audit_overdue(c)
    c["risk_count"] = q1("SELECT COUNT(*) n FROM risk_alerts WHERE company_id=? AND status='未处理'", (c["id"],))["n"]
    c["cert_expiring"] = q1("""SELECT COUNT(*) n FROM certificates WHERE company_id=? AND status IN ('即将到期','已过期')""",
                            (c["id"],))["n"]
    return c


@router.get("")
def list_companies(keyword: str = "", ctype: str = "", scale: str = "", status: str = "",
                   page: int = 1, size: int = 10, audit_overdue: str = "",
                   user: dict = Depends(get_current_user)):
    sql, params = "SELECT * FROM companies WHERE deleted=0", []
    if keyword:
        sql += " AND (name LIKE ? OR legal_rep LIKE ? OR credit_code LIKE ? OR industry LIKE ?)"
        params += [f"%{keyword}%"] * 4
    if ctype:
        sql += " AND ctype=?"
        params.append(ctype)
    if scale:
        sql += " AND scale=?"
        params.append(scale)
    if status:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY ctype DESC, id"
    rows = q(sql, params)
    rows = [_with_flags(c) for c in rows]
    if audit_overdue == "1":
        rows = [c for c in rows if c["audit_overdue"]]
    if user["role"] == "company" and user["company_id"]:
        rows = [c for c in rows if c["id"] == user["company_id"]]
    total = len(rows)
    rows = rows[(page - 1) * size: page * size]
    return {"total": total, "items": rows}


@router.get("/all")
def all_companies(user: dict = Depends(get_current_user)):
    """下拉选项用(不分页)"""
    return q("SELECT id,name,ctype FROM companies WHERE deleted=0 ORDER BY id")


@router.get("/{cid}")
def company_detail(cid: int, user: dict = Depends(get_current_user)):
    c = q1("SELECT * FROM companies WHERE id=? AND deleted=0", (cid,))
    if not c:
        raise HTTPException(404, "企业不存在")
    if user["role"] == "company" and user["company_id"] != cid:
        raise HTTPException(403, "只能查看本企业信息")
    c = _with_flags(c)
    c["equity"] = q("SELECT * FROM equity WHERE company_id=? ORDER BY ratio DESC", (cid,))
    c["documents"] = q("SELECT id,name,category,file_name,uploaded_by,created_at FROM documents WHERE company_id=?", (cid,))
    c["certificates"] = q("SELECT * FROM certificates WHERE company_id=? ORDER BY expire_date", (cid,))
    return c


@router.post("")
def create_company(body: CompanyBody, request: Request, user: dict = Depends(require_roles("admin", "secretary"))):
    if q1("SELECT id FROM companies WHERE name=? AND deleted=0", (body.name,)):
        raise HTTPException(400, "企业名称已存在")
    if body.credit_code and q1("SELECT id FROM companies WHERE credit_code=? AND deleted=0", (body.credit_code,)):
        raise HTTPException(400, "统一社会信用代码已存在")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cid = ex("""INSERT INTO companies(name,credit_code,ctype,legal_rep,phone,email,reg_capital,address,founded_date,
              biz_scope,industry,scale,emp_count,assets,revenue,profit,holder_ratio,audit_cycle,ext,created_by,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
             (body.name, body.credit_code, body.ctype, body.legal_rep, body.phone, body.email, body.reg_capital,
              body.address, body.founded_date, body.biz_scope, body.industry, body.scale, body.emp_count,
              body.assets, body.revenue, body.profit, body.holder_ratio, body.audit_cycle,
              json.dumps(body.ext, ensure_ascii=False), user["name"], now))
    log_action(user, "企业信息管理", "录入企业", body.name, request)
    return {"id": cid}


@router.put("/{cid}")
def update_company(cid: int, body: CompanyBody, request: Request, user: dict = Depends(get_current_user)):
    c = q1("SELECT * FROM companies WHERE id=? AND deleted=0", (cid,))
    if not c:
        raise HTTPException(404, "企业不存在")
    if user["role"] == "company" and user["company_id"] != cid:
        raise HTTPException(403, "只能维护本企业信息")
    ex("""UPDATE companies SET name=?,credit_code=?,ctype=?,legal_rep=?,phone=?,email=?,reg_capital=?,address=?,
        founded_date=?,biz_scope=?,industry=?,scale=?,emp_count=?,assets=?,revenue=?,profit=?,holder_ratio=?,
        audit_cycle=?,ext=? WHERE id=?""",
       (body.name, body.credit_code, body.ctype, body.legal_rep, body.phone, body.email, body.reg_capital,
        body.address, body.founded_date, body.biz_scope, body.industry, body.scale, body.emp_count,
        body.assets, body.revenue, body.profit, body.holder_ratio, body.audit_cycle,
        json.dumps(body.ext, ensure_ascii=False), cid))
    log_action(user, "企业信息管理", "修改企业信息", body.name, request)
    return {"ok": True}


@router.post("/{cid}/ext")
def submit_ext(cid: int, body: ExtBody, request: Request, user: dict = Depends(get_current_user)):
    """企业用户提交扩展信息(知识产权/科研项目/荣誉等) -> 待管理员审核"""
    if user["role"] == "company" and user["company_id"] != cid:
        raise HTTPException(403, "只能提交本企业信息")
    c = q1("SELECT * FROM companies WHERE id=? AND deleted=0", (cid,))
    if not c:
        raise HTTPException(404, "企业不存在")
    old = json.loads(c["ext"]) if c["ext"] and isinstance(c["ext"], str) else (c["ext"] or {})
    merged = {**old, **body.ext, "ext_status": "待审核", "ext_submitted_by": user["name"]}
    ex("UPDATE companies SET ext=? WHERE id=?", (json.dumps(merged, ensure_ascii=False), cid))
    log_action(user, "企业信息管理", "提交扩展信息", c["name"], request)
    return {"ok": True, "need_review": user["role"] == "company"}


@router.post("/{cid}/ext/review")
def review_ext(cid: int, request: Request, approve: bool = True,
               user: dict = Depends(require_roles("admin", "secretary"))):
    c = q1("SELECT ext FROM companies WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404, "企业不存在")
    ext = json.loads(c["ext"]) if c["ext"] and isinstance(c["ext"], str) else {}
    ext["ext_status"] = "已审核" if approve else "已退回"
    ex("UPDATE companies SET ext=? WHERE id=?", (json.dumps(ext, ensure_ascii=False), cid))
    log_action(user, "企业信息管理", "审核扩展信息", f"企业#{cid} {'通过' if approve else '退回'}", request)
    return {"ok": True}


@router.delete("/{cid}")
def delete_company(cid: int, reason: str, request: Request, user: dict = Depends(require_roles("admin"))):
    c = q1("SELECT name FROM companies WHERE id=? AND deleted=0", (cid,))
    if not c:
        raise HTTPException(404, "企业不存在")
    ex("UPDATE companies SET deleted=1, delete_reason=?, status='注销' WHERE id=?", (reason, cid))
    log_action(user, "企业信息管理", "删除企业", f"{c['name']} 原因:{reason}", request)
    return {"ok": True}


# ---------- 股权 ----------
@router.post("/{cid}/equity")
def add_equity(cid: int, body: EquityBody, request: Request, user: dict = Depends(require_roles("admin", "secretary"))):
    eid = ex("INSERT INTO equity(company_id,shareholder,ratio,method,invest_time,remark) VALUES(?,?,?,?,?,?)",
             (cid, body.shareholder, body.ratio, body.method, body.invest_time, body.remark))
    log_action(user, "企业信息管理", "登记股权", f"企业#{cid} {body.shareholder} {body.ratio}%", request)
    return {"id": eid}


@router.delete("/{cid}/equity/{eid}")
def del_equity(cid: int, eid: int, request: Request, user: dict = Depends(require_roles("admin", "secretary"))):
    ex("DELETE FROM equity WHERE id=? AND company_id=?", (eid, cid))
    log_action(user, "企业信息管理", "删除股权记录", f"equity#{eid}", request)
    return {"ok": True}


# ---------- 文档资料 ----------
@router.post("/{cid}/documents")
async def upload_doc(cid: int, file: UploadFile = File(...), name: str = Form(""), category: str = Form("其他"),
                     request: Request = None, user: dict = Depends(get_current_user)):
    c = q1("SELECT name FROM companies WHERE id=? AND deleted=0", (cid,))
    if not c:
        raise HTTPException(404, "企业不存在")
    if user["role"] == "company" and user["company_id"] != cid:
        raise HTTPException(403, "只能上传本企业文档")
    save_dir = os.path.join(UPLOAD_DIR, str(cid))
    os.makedirs(save_dir, exist_ok=True)
    fname = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    fpath = os.path.join(save_dir, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    did = ex("""INSERT INTO documents(company_id,name,category,file_name,file_path,uploaded_by,created_at)
              VALUES(?,?,?,?,?,?,?)""",
             (cid, name or file.filename, category, file.filename, fpath, user["name"],
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "企业信息管理", "上传文档", f"{c['name']} - {name or file.filename}", request)
    return {"id": did}


@router.get("/{cid}/documents/{did}/download")
def download_doc(cid: int, did: int, user: dict = Depends(get_current_user)):
    d = q1("SELECT * FROM documents WHERE id=? AND company_id=?", (did, cid))
    if not d or not os.path.exists(d["file_path"]):
        raise HTTPException(404, "文件不存在")
    from fastapi.responses import FileResponse
    return FileResponse(d["file_path"], filename=d["file_name"])


@router.delete("/{cid}/documents/{did}")
def delete_doc(cid: int, did: int, request: Request, user: dict = Depends(get_current_user)):
    d = q1("SELECT * FROM documents WHERE id=? AND company_id=?", (did, cid))
    if not d:
        raise HTTPException(404, "文档不存在")
    if os.path.exists(d["file_path"]):
        os.remove(d["file_path"])
    ex("DELETE FROM documents WHERE id=?", (did,))
    log_action(user, "企业信息管理", "删除文档", d["name"], request)
    return {"ok": True}


# ---------- 证照 ----------
@router.post("/{cid}/certificates")
def add_cert(cid: int, body: CertBody, request: Request, user: dict = Depends(require_roles("admin", "secretary"))):
    st = _calc_cert_status(body.expire_date)
    did = ex("INSERT INTO certificates(company_id,cert_name,cert_no,expire_date,status) VALUES(?,?,?,?,?)",
             (cid, body.cert_name, body.cert_no, body.expire_date, st))
    log_action(user, "企业规范提醒", "登记证照", body.cert_name, request)
    return {"id": did, "status": st}


@router.delete("/{cid}/certificates/{cert_id}")
def del_cert(cid: int, cert_id: int, request: Request, user: dict = Depends(require_roles("admin", "secretary"))):
    ex("DELETE FROM certificates WHERE id=? AND company_id=?", (cert_id, cid))
    return {"ok": True}
