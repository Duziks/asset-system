# -*- coding: utf-8 -*-
"""登录与鉴权模块: 登录/登出/改密/用户管理/组织架构"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import (ROLE_MENUS, ROLE_NAMES, client_ip, create_token, get_current_user,
                  hash_pwd, log_action, remove_token, require_roles)
from db import ex, q, q1

router = APIRouter(prefix="/api/auth", tags=["登录鉴权"])


class LoginBody(BaseModel):
    username: str
    password: str


class PwdBody(BaseModel):
    old_password: str
    new_password: str


class UserBody(BaseModel):
    username: str
    password: str
    name: str
    role: str
    dept: str = ""
    phone: str = ""
    email: str = ""
    company_id: int | None = None


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    dept: str | None = None
    phone: str | None = None
    email: str | None = None
    company_id: int | None = None
    status: int | None = None


class DeptBody(BaseModel):
    name: str
    parent_id: int | None = None
    leader: str = ""
    duty: str = ""


def record_login(uid, username, ip, action):
    ex("INSERT INTO login_logs(user_id,username,ip,action,created_at) VALUES(?,?,?,?,?)",
       (uid, username, ip, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))


@router.post("/login")
def login(body: LoginBody, request: Request):
    u = q1("SELECT * FROM users WHERE username=?", (body.username,))
    ip = client_ip(request)
    if not u or u["password"] != hash_pwd(body.password):
        record_login(u["id"] if u else None, body.username, ip, "登录失败")
        raise HTTPException(400, "用户名或密码错误")
    if not u["status"]:
        raise HTTPException(403, "账号已停用，请联系管理员")
    token = create_token(u["id"])
    record_login(u["id"], u["name"], ip, "登录成功")
    company = q1("SELECT id,name FROM companies WHERE id=?", (u["company_id"],)) if u["company_id"] else None
    return {"token": token, "must_change_pwd": bool(u["must_change_pwd"]),
            "user": {"id": u["id"], "username": u["username"], "name": u["name"],
                     "role": u["role"], "role_name": ROLE_NAMES.get(u["role"], u["role"]),
                     "dept": u["dept"], "company": company,
                     "menus": ROLE_MENUS.get(u["role"], [])}}


@router.post("/logout")
def logout(request: Request, user: dict = Depends(get_current_user)):
    remove_token(user["token"])
    return {"ok": True}


@router.post("/change-password")
def change_pwd(body: PwdBody, request: Request, user: dict = Depends(get_current_user)):
    if user["password"] != hash_pwd(body.old_password):
        raise HTTPException(400, "原密码错误")
    if len(body.new_password) < 6:
        raise HTTPException(400, "新密码长度至少6位")
    ex("UPDATE users SET password=?, must_change_pwd=0 WHERE id=?", (hash_pwd(body.new_password), user["id"]))
    log_action(user, "登录鉴权", "修改密码", user["username"], request)
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    company = q1("SELECT id,name,ctype FROM companies WHERE id=?", (user["company_id"],)) if user["company_id"] else None
    groups = q("""SELECT g.* FROM perm_groups g JOIN user_groups ug ON ug.group_id=g.id WHERE ug.user_id=?""",
               (user["id"],))
    return {"id": user["id"], "username": user["username"], "name": user["name"], "role": user["role"],
            "role_name": ROLE_NAMES.get(user["role"], user["role"]), "dept": user["dept"],
            "company": company, "menus": ROLE_MENUS.get(user["role"], []),
            "perm_groups": [g["name"] for g in groups]}


# ---------- 用户管理 (管理员) ----------
@router.get("/users")
def list_users(keyword: str = "", role: str = "", user: dict = Depends(require_roles("admin"))):
    sql, params = "SELECT u.*, c.name AS company_name FROM users u LEFT JOIN companies c ON c.id=u.company_id WHERE 1=1", []
    if keyword:
        sql += " AND (u.username LIKE ? OR u.name LIKE ?)"
        params += [f"%{keyword}%", f"%{keyword}%"]
    if role:
        sql += " AND u.role=?"
        params.append(role)
    sql += " ORDER BY u.id"
    rows = q(sql, params)
    for r in rows:
        r.pop("password", None)
    return rows


@router.post("/users")
def create_user(body: UserBody, request: Request, user: dict = Depends(require_roles("admin"))):
    if body.role not in ROLE_NAMES:
        raise HTTPException(400, "无效角色")
    if q1("SELECT id FROM users WHERE username=?", (body.username,)):
        raise HTTPException(400, "用户名已存在")
    if body.role == "company" and not body.company_id:
        raise HTTPException(400, "企业用户必须关联企业")
    uid = ex("""INSERT INTO users(username,password,name,role,role_name,company_id,dept,phone,email,status,must_change_pwd,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,1,1,?)""",
             (body.username, hash_pwd(body.password), body.name, body.role, ROLE_NAMES[body.role],
              body.company_id, body.dept, body.phone, body.email,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_action(user, "登录鉴权", "新增用户", f"{body.username}({ROLE_NAMES[body.role]})", request)
    return {"id": uid}


@router.put("/users/{uid}")
def update_user(uid: int, body: UserUpdate, request: Request, user: dict = Depends(require_roles("admin"))):
    old = q1("SELECT * FROM users WHERE id=?", (uid,))
    if not old:
        raise HTTPException(404, "用户不存在")
    sets, params = [], []
    for f, v in body.dict(exclude_none=True).items():
        if f == "role":
            sets.append("role_name=?")
            params.append(ROLE_NAMES.get(v, v))
        sets.append(f"{f}=?")
        params.append(v)
    if sets:
        params.append(uid)
        ex(f"UPDATE users SET {', '.join(sets)} WHERE id=?", params)
    log_action(user, "登录鉴权", "修改用户", old["username"], request)
    return {"ok": True}


@router.post("/users/{uid}/reset-password")
def reset_pwd(uid: int, request: Request, user: dict = Depends(require_roles("admin"))):
    old = q1("SELECT username FROM users WHERE id=?", (uid,))
    if not old:
        raise HTTPException(404, "用户不存在")
    new_pwd = "hw" + str(int(datetime.now().timestamp()))[-6:]
    ex("UPDATE users SET password=?, must_change_pwd=1 WHERE id=?", (hash_pwd(new_pwd), uid))
    log_action(user, "登录鉴权", "重置密码", old["username"], request)
    return {"new_password": new_pwd}


@router.delete("/users/{uid}")
def delete_user(uid: int, request: Request, user: dict = Depends(require_roles("admin"))):
    if uid == user["id"]:
        raise HTTPException(400, "不能删除自己")
    old = q1("SELECT username FROM users WHERE id=?", (uid,))
    if not old:
        raise HTTPException(404, "用户不存在")
    ex("DELETE FROM users WHERE id=?", (uid,))
    ex("DELETE FROM user_groups WHERE user_id=?", (uid,))
    log_action(user, "登录鉴权", "删除用户", old["username"], request)
    return {"ok": True}


# ---------- 组织架构 ----------
@router.get("/departments")
def list_departments(user: dict = Depends(get_current_user)):
    return q("SELECT * FROM departments ORDER BY id")


@router.post("/departments")
def create_dept(body: DeptBody, request: Request, user: dict = Depends(require_roles("admin", "chairman"))):
    did = ex("INSERT INTO departments(name,parent_id,leader,duty) VALUES(?,?,?,?)",
             (body.name, body.parent_id, body.leader, body.duty))
    log_action(user, "登录鉴权", "新增部门", body.name, request)
    return {"id": did}


@router.get("/roles")
def list_roles(user: dict = Depends(get_current_user)):
    return [{"key": k, "name": v} for k, v in ROLE_NAMES.items()]
