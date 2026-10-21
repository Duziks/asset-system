# -*- coding: utf-8 -*-
"""认证鉴权: Token 会话、RBAC 权限、操作审计"""
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps

from fastapi import Depends, HTTPException, Request

from db import ex, q, q1

SALT = "hawei"
TOKEN_DAYS = 7

# 角色权限映射 (菜单可见性)
ROLE_MENUS = {
    "admin": ["dashboard", "report", "company", "remind", "approval", "assessment", "transfer", "platform"],
    "chairman": ["dashboard", "report", "company", "remind", "approval", "assessment", "transfer"],
    "secretary": ["dashboard", "report", "company", "remind", "approval", "transfer"],
    "supervisor": ["dashboard", "report", "company", "approval", "assessment", "remind"],
    "employee": ["report", "approval"],
    "company": ["report", "company", "remind", "approval", "transfer"],
}

ROLE_NAMES = {"admin": "管理员", "chairman": "董事长", "secretary": "秘书",
              "supervisor": "主管", "employee": "员工", "company": "企业用户"}


def hash_pwd(raw: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", (SALT + raw).encode(), b"asset_salt", 60000).hex()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def create_token(user_id: int) -> str:
    token = secrets.token_hex(32)
    expires = (datetime.now() + timedelta(days=TOKEN_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    ex("INSERT INTO tokens(token,user_id,expires_at) VALUES(?,?,?)", (token, user_id, expires))
    return token


def remove_token(token: str):
    ex("DELETE FROM tokens WHERE token=?", (token,))


def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else request.query_params.get("token", "")
    if not token:
        raise HTTPException(401, "未登录或凭证缺失")
    row = q1("""SELECT t.token, u.* FROM tokens t JOIN users u ON u.id=t.user_id
              WHERE t.token=? AND t.expires_at > ?""", (token, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    if not row:
        raise HTTPException(401, "登录已失效，请重新登录")
    if not row["status"]:
        raise HTTPException(403, "账号已停用")
    row["token"] = token
    return row


def require_roles(*roles):
    def dep(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, f"无权访问，需要角色: {'/'.join(roles)}")
        return user
    return dep


def log_action(user: dict, module: str, action: str, detail: str = "", request: Request = None):
    ip = client_ip(request) if request else ""
    ex("""INSERT INTO audit_logs(user_id,username,module,action,detail,ip,created_at)
         VALUES(?,?,?,?,?,?,?)""",
       (user["id"], user["name"], module, action, detail, ip,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
