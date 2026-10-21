# -*- coding: utf-8 -*-
"""平台管理模块: 菜单管理/授权管理/安全审计/工作交接/消息提醒"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import ROLE_MENUS, get_current_user, log_action, require_roles
from db import ex, q, q1

router = APIRouter(prefix="/api/platform", tags=["平台管理"])


# ---------- 菜单管理 ----------
@router.get("/menus")
def menus(user: dict = Depends(get_current_user)):
    rows = q("SELECT * FROM menus ORDER BY sort")
    allowed = ROLE_MENUS.get(user["role"], [])
    return [r for r in rows if r["key"] in allowed]


@router.get("/menus/all")
def all_menus(user: dict = Depends(require_roles("admin"))):
    return q("SELECT * FROM menus ORDER BY sort")


@router.put("/menus/{mid}")
def update_menu(mid: int, request: Request, visible: int | None = None, sort: int | None = None,
                name: str | None = None, user: dict = Depends(require_roles("admin"))):
    sets, params = [], []
    if visible is not None:
        sets.append("visible=?")
        params.append(visible)
    if sort is not None:
        sets.append("sort=?")
        params.append(sort)
    if name:
        sets.append("name=?")
        params.append(name)
    if sets:
        params.append(mid)
        ex(f"UPDATE menus SET {', '.join(sets)} WHERE id=?", params)
    log_action(user, "平台管理", "修改菜单", f"menu#{mid}", request)
    return {"ok": True}


# ---------- 授权管理 (权限组) ----------
@router.get("/groups")
def groups(user: dict = Depends(require_roles("admin"))):
    gs = q("SELECT * FROM perm_groups ORDER BY id")
    for g in gs:
        g["members"] = q("""SELECT u.id, u.name, u.role FROM user_groups ug
                          JOIN users u ON u.id=ug.user_id WHERE ug.group_id=?""", (g["id"],))
    return gs


@router.post("/groups")
def add_group(request: Request, name: str, perms: str = "", description: str = "",
              user: dict = Depends(require_roles("admin"))):
    if q1("SELECT id FROM perm_groups WHERE name=?", (name,)):
        raise HTTPException(400, "权限组已存在")
    gid = ex("INSERT INTO perm_groups(name,perms,description) VALUES(?,?,?)", (name, perms, description))
    log_action(user, "平台管理", "新增权限组", name, request)
    return {"id": gid}


@router.put("/groups/{gid}/perms")
def set_perms(gid: int, request: Request, perms: str, user: dict = Depends(require_roles("admin"))):
    ex("UPDATE perm_groups SET perms=? WHERE id=?", (perms, gid))
    log_action(user, "平台管理", "调整权限组授权", f"#{gid}", request)
    return {"ok": True}


@router.post("/groups/{gid}/members/{uid}")
def add_member(gid: int, uid: int, request: Request, user: dict = Depends(require_roles("admin"))):
    ex("INSERT OR IGNORE INTO user_groups(user_id,group_id) VALUES(?,?)", (uid, gid))
    log_action(user, "平台管理", "用户加入权限组", f"user#{uid}->group#{gid}", request)
    return {"ok": True}


@router.delete("/groups/{gid}/members/{uid}")
def remove_member(gid: int, uid: int, request: Request, user: dict = Depends(require_roles("admin"))):
    ex("DELETE FROM user_groups WHERE user_id=? AND group_id=?", (uid, gid))
    return {"ok": True}


# ---------- 安全审计 ----------
@router.get("/audit-logs")
def audit_logs(request: Request, keyword: str = "", module: str = "", page: int = 1, size: int = 15,
               user: dict = Depends(require_roles("admin", "chairman"))):
    sql, params = "SELECT * FROM audit_logs WHERE 1=1", []
    if keyword:
        sql += " AND (username LIKE ? OR detail LIKE ? OR action LIKE ?)"
        params += [f"%{keyword}%"] * 3
    if module:
        sql += " AND module=?"
        params.append(module)
    total = q1(f"SELECT COUNT(*) n FROM ({sql})", params)["n"]
    rows = q(sql + " ORDER BY id DESC LIMIT ? OFFSET ?", params + [size, (page - 1) * size])
    log_action(user, "平台管理", "查询审计日志", "", request)
    return {"total": total, "items": rows}


@router.get("/login-logs")
def login_logs(request: Request, page: int = 1, size: int = 15,
               user: dict = Depends(require_roles("admin", "chairman"))):
    total = q1("SELECT COUNT(*) n FROM login_logs")["n"]
    rows = q("SELECT * FROM login_logs ORDER BY id DESC LIMIT ? OFFSET ?", (size, (page - 1) * size))
    return {"total": total, "items": rows}


# ---------- 工作交接 ----------
class HandoverBody(BaseModel):
    from_user: str
    to_user: str
    scope: str = "全部业务"


@router.post("/handover")
def handover(body: HandoverBody, request: Request, user: dict = Depends(require_roles("admin"))):
    src = q1("SELECT * FROM users WHERE username=?", (body.from_user,))
    dst = q1("SELECT * FROM users WHERE username=?", (body.to_user,))
    if not src or not dst:
        raise HTTPException(404, "交接双方用户不存在")
    moved_appr = 0
    if body.scope in ("全部业务", "审批事务"):
        rows = q("SELECT id FROM approvals WHERE applicant_id=? AND status NOT IN ('已通过','已驳回')", (src["id"],))
        for r in rows:
            ex("UPDATE approvals SET applicant_id=?, applicant=? WHERE id=?", (dst["id"], dst["name"], r["id"]))
        moved_appr = len(rows)
    # 权限组同步授权给交接人
    src_groups = q("SELECT group_id FROM user_groups WHERE user_id=?", (src["id"],))
    for g in src_groups:
        ex("INSERT OR IGNORE INTO user_groups(user_id,group_id) VALUES(?,?)", (dst["id"], g["group_id"]))
    hid = ex("""INSERT INTO handovers(from_user,to_user,scope,detail,status,created_at)
              VALUES(?,?,?,?, '已完成', ?)""",
             (src["name"], dst["name"], body.scope,
              f"转移在途审批{moved_appr}件，同步权限组{len(src_groups)}个", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "平台管理", "工作交接", f"{src['name']} -> {dst['name']}", request)
    return {"id": hid, "moved_approvals": moved_appr, "synced_groups": len(src_groups)}


@router.get("/handover")
def handover_list(user: dict = Depends(require_roles("admin"))):
    return q("SELECT * FROM handovers ORDER BY id DESC")


# ---------- 消息提醒 ----------
@router.get("/messages")
def my_messages(user: dict = Depends(get_current_user)):
    sql = "SELECT * FROM messages WHERE receiver=? OR receiver='all'"
    params = [user["role"]]
    if user["role"] == "company" and user["company_id"]:
        c = q1("SELECT username FROM users WHERE id=?", (user["id"],))
        sql += " OR receiver=?"
        params.append(c["username"] if c else "")
    rows = q(sql + " ORDER BY id DESC LIMIT 50", params)
    unread = sum(1 for r in rows if r["status"] == "未读")
    return {"unread": unread, "items": rows}


@router.put("/messages/{mid}/read")
def read_msg(mid: int, user: dict = Depends(get_current_user)):
    ex("UPDATE messages SET status='已读' WHERE id=?", (mid,))
    return {"ok": True}


@router.post("/messages/send")
def send_msg(request: Request, title: str, content: str, channel: str = "系统",
             receiver_role: str = "all", user: dict = Depends(require_roles("admin", "secretary"))):
    """消息群发: 系统/邮件/短信(模拟)"""
    receiver = "all" if receiver_role == "all" else receiver_role
    ex("""INSERT INTO messages(title,content,channel,receiver,status,created_at)
        VALUES(?,?,?,?, '未读', ?)""",
       (title, content, channel, receiver, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "平台管理", f"发送{channel}消息", title, request)
    return {"ok": True}


@router.get("/templates")
def templates(user: dict = Depends(require_roles("admin", "secretary"))):
    return q("SELECT * FROM msg_templates ORDER BY id")


@router.post("/templates")
def add_template(request: Request, name: str, channel: str = "邮件", subject: str = "", content: str = "",
                 user: dict = Depends(require_roles("admin", "secretary"))):
    tid = ex("INSERT INTO msg_templates(name,channel,subject,content) VALUES(?,?,?,?)",
             (name, channel, subject, content))
    log_action(user, "平台管理", "新增消息模板", name, request)
    return {"id": tid}
