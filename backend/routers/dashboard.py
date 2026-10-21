# -*- coding: utf-8 -*-
"""企业数据展示模块: 综合数据看板 / 企业信息报表 / 企业增量统计"""
import json

from fastapi import APIRouter, Depends

from auth import get_current_user
from db import q, q1

router = APIRouter(prefix="/api/dashboard", tags=["企业数据展示"])


@router.get("/overview")
def overview(user: dict = Depends(get_current_user)):
    """指标卡: 企业数/资产总额/营收/利润/员工总数/风险/待审批/逾期审计"""
    if user["role"] == "company" and user["company_id"]:
        w, params = f"id={user['company_id']}", []
    else:
        w, params = "deleted=0", []
    cs = q(f"SELECT * FROM companies WHERE {w}", params)
    total_assets = sum(c["assets"] or 0 for c in cs)
    total_rev = sum(c["revenue"] or 0 for c in cs)
    total_profit = sum(c["profit"] or 0 for c in cs)
    total_emp = sum(c["emp_count"] or 0 for c in cs)
    by_type = {"全资": 0, "控股": 0, "参股": 0}
    for c in cs:
        by_type[c["ctype"]] = by_type.get(c["ctype"], 0) + 1
    overdue = sum(1 for c in cs if _overdue(c))
    risk_open = q1("SELECT COUNT(*) n FROM risk_alerts WHERE status='未处理'")["n"]
    pending = q1("SELECT COUNT(*) n FROM approvals WHERE status LIKE '待%'")["n"]
    return {
        "company_count": len(cs), "by_type": by_type,
        "total_assets": round(total_assets, 1), "total_revenue": round(total_rev, 1),
        "total_profit": round(total_profit, 1), "total_emp": total_emp,
        "overdue_audit": overdue, "risk_open": risk_open, "pending_approvals": pending,
    }


def _overdue(c) -> bool:
    if not c["last_audit_date"]:
        return True
    from datetime import datetime
    try:
        last = datetime.strptime(c["last_audit_date"], "%Y-%m-%d")
    except ValueError:
        return True
    due = last.year + (c["audit_cycle"] or 1)
    return datetime.now().year > due


@router.get("/trend")
def increase_trend(user: dict = Depends(get_current_user)):
    """企业增量统计: 按注册月份统计累计/新增"""
    cs = q("SELECT founded_date FROM companies WHERE deleted=0 AND founded_date IS NOT NULL")
    monthly = {}
    for c in cs:
        ym = (c["founded_date"] or "")[:7]
        if ym:
            monthly[ym] = monthly.get(ym, 0) + 1
    keys = sorted(monthly.keys())[-24:]
    add = [monthly[k] for k in keys]
    cum, s = [], 0
    total_before = sum(v for k, v in monthly.items() if k < keys[0]) if keys else 0
    for a in add:
        s += a
        cum.append(total_before + s)
    return {"months": keys, "added": add, "cumulative": cum}


@router.get("/type-distribution")
def type_dist(user: dict = Depends(get_current_user)):
    rows = q("""SELECT industry, COUNT(*) n, SUM(revenue) rev FROM companies
              WHERE deleted=0 GROUP BY industry ORDER BY n DESC""")
    return rows


@router.get("/top-companies")
def top_companies(user: dict = Depends(get_current_user)):
    """营收/利润 TOP8"""
    return {"revenue": q("SELECT name, revenue v FROM companies WHERE deleted=0 ORDER BY revenue DESC LIMIT 8"),
            "profit": q("SELECT name, profit v FROM companies WHERE deleted=0 ORDER BY profit DESC LIMIT 8")}


@router.get("/emp-structure")
def emp_structure(user: dict = Depends(get_current_user)):
    rows = q("SELECT scale, SUM(emp_count) n FROM companies WHERE deleted=0 GROUP BY scale")
    return rows


@router.get("/report")
def report(keyword: str = "", ctype: str = "", page: int = 1, size: int = 10,
           user: dict = Depends(get_current_user)):
    """企业信息报表: 分页 + 检索 + 导出源数据"""
    sql, params = "SELECT * FROM companies WHERE deleted=0", []
    if keyword:
        sql += " AND (name LIKE ? OR legal_rep LIKE ? OR phone LIKE ?)"
        params += [f"%{keyword}%"] * 3
    if ctype:
        sql += " AND ctype=?"
        params.append(ctype)
    sql += " ORDER BY id"
    rows = q(sql, params)
    if user["role"] == "company" and user["company_id"]:
        rows = [r for r in rows if r["id"] == user["company_id"]]
    total = len(rows)
    items = rows[(page - 1) * size: page * size]
    for it in items:
        try:
            it["ext"] = json.loads(it["ext"]) if it["ext"] else {}
        except (json.JSONDecodeError, TypeError):
            it["ext"] = {}
    return {"total": total, "items": items}
