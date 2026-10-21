# -*- coding: utf-8 -*-
"""企业目标考核模块: 指标设定 / 过程监控 / 考核评价"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_user, log_action, require_roles
from db import ex, q, q1

router = APIRouter(prefix="/api/assessment", tags=["企业目标考核"])


class KpiBody(BaseModel):
    company_id: int
    year: int = 2026
    name: str
    category: str = "财务指标"
    target: float = 0
    unit: str = ""
    weight: float = 0
    standard: str = ""


class RecordBody(BaseModel):
    period: str = "Q3"
    value: float = 0
    comment: str = ""


class EvalBody(BaseModel):
    company_id: int
    year: int = 2026
    total_score: float
    grade: str = "良好"
    comment: str = ""


@router.get("/indicators")
def indicators(company_id: int = 0, year: int = 2026, user: dict = Depends(get_current_user)):
    if user["role"] == "company" and user["company_id"]:
        company_id = user["company_id"]
    sql = """SELECT k.*, c.name company_name FROM kpi_indicators k
           JOIN companies c ON c.id=k.company_id WHERE k.year=?"""
    params = [year]
    if company_id:
        sql += " AND k.company_id=?"
        params.append(company_id)
    rows = q(sql + " ORDER BY k.company_id, k.id", params)
    for r in rows:
        recs = q("SELECT * FROM kpi_records WHERE indicator_id=? ORDER BY id", (r["id"],))
        acc = sum(x["value"] or 0 for x in recs)
        r["accumulated"] = acc
        r["progress"] = round(acc / r["target"] * 100, 1) if r["target"] else 0
        r["records"] = recs
    return rows


@router.post("/indicators")
def add_indicator(body: KpiBody, request: Request, user: dict = Depends(require_roles("admin", "supervisor", "chairman"))):
    kid = ex("""INSERT INTO kpi_indicators(company_id,year,name,category,target,unit,weight,standard)
              VALUES(?,?,?,?,?,?,?,?)""",
             (body.company_id, body.year, body.name, body.category, body.target, body.unit,
              body.weight, body.standard))
    log_action(user, "企业目标考核", "设定指标", body.name, request)
    return {"id": kid}


@router.delete("/indicators/{kid}")
def del_indicator(kid: int, request: Request, user: dict = Depends(require_roles("admin", "supervisor"))):
    ex("DELETE FROM kpi_records WHERE indicator_id=?", (kid,))
    ex("DELETE FROM kpi_indicators WHERE id=?", (kid,))
    return {"ok": True}


@router.post("/indicators/{kid}/records")
def add_record(kid: int, body: RecordBody, request: Request,
               user: dict = Depends(require_roles("admin", "supervisor", "secretary"))):
    k = q1("SELECT target FROM kpi_indicators WHERE id=?", (kid,))
    if not k:
        raise HTTPException(404, "指标不存在")
    progress = round(body.value / k["target"] * 100, 1) if k["target"] else 0
    rid = ex("""INSERT INTO kpi_records(indicator_id,period,value,progress,comment,record_time)
              VALUES(?,?,?,?,?,?)""",
             (kid, body.period, body.value, progress, body.comment,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "企业目标考核", "录入过程数据", f"指标#{kid} {body.period}", request)
    return {"id": rid, "progress": progress}


@router.get("/evaluations")
def evaluations(year: int = 2025, user: dict = Depends(get_current_user)):
    sql = """SELECT e.*, c.name company_name FROM kpi_evaluations e
           JOIN companies c ON c.id=e.company_id WHERE e.year=?"""
    params = [year]
    if user["role"] == "company" and user["company_id"]:
        sql += " AND e.company_id=?"
        params.append(user["company_id"])
    return q(sql + " ORDER BY e.total_score DESC", params)


@router.post("/evaluations")
def add_evaluation(body: EvalBody, request: Request, user: dict = Depends(require_roles("admin", "supervisor", "chairman"))):
    eid = ex("""INSERT INTO kpi_evaluations(company_id,year,total_score,grade,comment,evaluator,created_at)
              VALUES(?,?,?,?,?,?,?)""",
             (body.company_id, body.year, body.total_score, body.grade, body.comment, user["name"],
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "企业目标考核", "考核评价", f"企业#{body.company_id} {body.year}年 {body.total_score}分", request)
    return {"id": eid}
