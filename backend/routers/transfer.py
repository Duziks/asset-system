# -*- coding: utf-8 -*-
"""成果转化模块: 成果登记与发布 / 对接与合作管理 / 转化过程跟踪"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_user, log_action, require_roles
from db import ex, q, q1

router = APIRouter(prefix="/api/transfer", tags=["成果转化"])


class AchievementBody(BaseModel):
    name: str
    field: str = ""
    features: str = ""
    innovation: str = ""
    prospect: str = ""
    owner: str = ""


class CoopBody(BaseModel):
    achievement_id: int
    company_id: int | None = None
    intent: str = ""


class TrackBody(BaseModel):
    stage: str
    progress: str = ""
    fund_used: float = 0
    problems: str = ""


@router.get("/achievements")
def list_achievements(status: str = "", user: dict = Depends(get_current_user)):
    sql = """SELECT a.*, c.name company_name FROM achievements a
           LEFT JOIN companies c ON c.id=a.company_id WHERE 1=1"""
    params = []
    if status:
        sql += " AND a.status=?"
        params.append(status)
    if user["role"] == "company" and user["company_id"]:
        sql += " AND (a.company_id=? OR a.status='已发布')"
        params.append(user["company_id"])
    rows = q(sql + " ORDER BY a.created_at DESC", params)
    for r in rows:
        r["coops"] = q("SELECT * FROM cooperations WHERE achievement_id=?", (r["id"],))
    return rows


@router.post("/achievements")
def add_achievement(body: AchievementBody, request: Request, user: dict = Depends(get_current_user)):
    aid = ex("""INSERT INTO achievements(name,field,features,innovation,prospect,owner,company_id,status,created_at)
              VALUES(?,?,?,?,?,?,?,'待审核',?)""",
             (body.name, body.field, body.features, body.innovation, body.prospect, body.owner,
              user["company_id"] if user["role"] == "company" else None,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "成果转化", "登记成果", body.name, request)
    return {"id": aid}


@router.post("/achievements/{aid}/review")
def review(aid: int, request: Request, approve: bool = True, publish: bool = False,
           user: dict = Depends(require_roles("admin", "secretary", "chairman"))):
    st = "转化中" if publish else ("已发布" if approve else "已退回")
    ex("UPDATE achievements SET status=? WHERE id=?", (st, aid))
    log_action(user, "成果转化", "审核成果", f"#{aid} -> {st}", request)
    return {"ok": True, "status": st}


@router.post("/cooperations")
def apply_coop(body: CoopBody, request: Request, user: dict = Depends(get_current_user)):
    a = q1("SELECT name,status FROM achievements WHERE id=?", (body.achievement_id,))
    if not a:
        raise HTTPException(404, "成果不存在")
    if a["status"] != "已发布":
        raise HTTPException(400, "该成果未发布，暂不能申请合作")
    cid = body.company_id or user["company_id"]
    coop_id = ex("""INSERT INTO cooperations(achievement_id,company_id,applicant,intent,status,created_at)
                  VALUES(?,?,?,?, '意向沟通', ?)""",
                 (body.achievement_id, cid, user["name"], body.intent,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    ex("UPDATE achievements SET status='转化中' WHERE id=?", (body.achievement_id,))
    log_action(user, "成果转化", "发起合作意向", f"成果#{body.achievement_id}", request)
    return {"id": coop_id}


@router.get("/cooperations")
def list_coops(user: dict = Depends(get_current_user)):
    return q("""SELECT co.*, a.name ach_name, c.name company_name,
              (SELECT GROUP_CONCAT(stage || ':' || progress, ' | ') FROM transfer_tracks t WHERE t.coop_id=co.id) tracks
              FROM cooperations co
              JOIN achievements a ON a.id=co.achievement_id
              LEFT JOIN companies c ON c.id=co.company_id
              ORDER BY co.created_at DESC""")


@router.put("/cooperations/{coop_id}/status")
def set_coop_status(coop_id: int, request: Request, status: str, agreement: str = "",
                    user: dict = Depends(require_roles("admin", "secretary", "supervisor", "chairman"))):
    if status not in ("意向沟通", "洽谈中", "已签约", "已完成"):
        raise HTTPException(400, "无效状态")
    ex("UPDATE cooperations SET status=?, agreement=CASE WHEN ?<>'' THEN ? ELSE agreement END WHERE id=?",
       (status, agreement, agreement, coop_id))
    if status == "已签约":
        co = q1("SELECT achievement_id FROM cooperations WHERE id=?", (coop_id,))
        ex("UPDATE achievements SET status='转化中' WHERE id=?", (co["achievement_id"],))
    if status == "已完成":
        co = q1("SELECT achievement_id FROM cooperations WHERE id=?", (coop_id,))
        ex("UPDATE achievements SET status='已转化' WHERE id=?", (co["achievement_id"],))
    log_action(user, "成果转化", "更新合作状态", f"coop#{coop_id} -> {status}", request)
    return {"ok": True}


@router.post("/cooperations/{coop_id}/tracks")
def add_track(coop_id: int, body: TrackBody, request: Request,
              user: dict = Depends(require_roles("admin", "secretary", "supervisor"))):
    tid = ex("""INSERT INTO transfer_tracks(coop_id,stage,progress,fund_used,problems,update_time)
              VALUES(?,?,?,?,?,?)""",
             (coop_id, body.stage, body.progress, body.fund_used, body.problems,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "成果转化", "更新转化进度", f"coop#{coop_id} {body.stage}", request)
    return {"id": tid}
