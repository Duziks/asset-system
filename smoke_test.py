# -*- coding: utf-8 -*-
"""API 冒烟测试"""
import json
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000/api"
TOKENS = {}
PASS, FAIL = 0, []


def req(method, path, body=None, token=None, expect=200):
    url = BASE + urllib.parse.quote(path, safe="/?=&")
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r) as resp:
            code, payload = resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        code, payload = e.code, json.loads(e.read().decode())
    ok = code == expect
    global PASS
    if ok:
        PASS += 1
        print(f"  OK  {method} {path} -> {code}")
    else:
        FAIL.append((method, path, code, payload))
        print(f" FAIL {method} {path} -> {code} {payload}")
    return payload


print("== 登录鉴权 ==")
for role, u, p in [("admin", "admin", "admin123"), ("chairman", "chairman", "chair123"),
                   ("secretary", "secretary", "secret123"), ("supervisor", "supervisor", "super123"),
                   ("employee", "employee", "emp123"), ("company", "company", "comp123")]:
    d = req("POST", "/auth/login", {"username": u, "password": p})
    TOKENS[role] = d["token"]
req("POST", "/auth/login", {"username": "admin", "password": "wrong"}, expect=400)
me = req("GET", "/auth/me", token=TOKENS["company"])
assert me["company"]["name"].startswith("威海哈威光电"), me
req("GET", "/auth/me", expect=401)

print("== 数据看板 ==")
ov = req("GET", "/dashboard/overview", token=TOKENS["admin"])
assert ov["company_count"] == 22, ov["company_count"]
req("GET", "/dashboard/trend", token=TOKENS["admin"])
req("GET", "/dashboard/top-companies", token=TOKENS["admin"])
req("GET", "/dashboard/report?keyword=光电", token=TOKENS["admin"])
ov_c = req("GET", "/dashboard/overview", token=TOKENS["company"])
assert ov_c["company_count"] == 1, ov_c

print("== 企业信息管理 ==")
req("GET", "/companies?page=1&size=5", token=TOKENS["admin"])
req("GET", "/companies?audit_overdue=1", token=TOKENS["admin"])
req("GET", "/companies/1", token=TOKENS["admin"])
req("GET", "/companies/1", token=TOKENS["company"], expect=403)  # 非本企业
import time as _time
code = f"91371000TEST{int(_time.time())%1000000:06d}X"
new_c = req("POST", "/companies", {"name": f"测试新企业{int(_time.time())%100000}", "credit_code": code, "ctype": "参股"}, token=TOKENS["secretary"])
cid = new_c["id"]
req("PUT", f"/companies/{cid}", {"name": f"测试新企业{int(_time.time())%100000}", "credit_code": code, "ext": {"ip_count": 3}}, token=TOKENS["admin"])
req("POST", f"/companies/{cid}/ext", {"ext": {"honors": "省级专精特新"}}, token=TOKENS["company"], expect=403)
req("POST", "/companies/2/ext", {"ext": {"honors": "省级专精特新"}}, token=TOKENS["company"])
req("POST", f"/companies/{cid}/ext/review?approve=true", token=TOKENS["admin"])
req("POST", f"/companies/{cid}/equity", {"shareholder": "测试股东", "ratio": 10}, token=TOKENS["secretary"])
req("DELETE", f"/companies/{cid}?reason=测试注销", token=TOKENS["secretary"], expect=403)
req("DELETE", f"/companies/{cid}?reason=测试注销", token=TOKENS["admin"])

print("== 规范提醒 ==")
req("GET", "/reminders/policies", token=TOKENS["admin"])
req("GET", "/reminders/certificates", token=TOKENS["admin"])
ao = req("GET", "/reminders/audit-overdue", token=TOKENS["admin"])
assert len(ao) >= 2, ao
req("POST", "/reminders/audit/1/record", token=TOKENS["secretary"])
req("GET", "/reminders/risks", token=TOKENS["admin"])

print("== 业务审批 ==")
na = req("POST", "/approvals", {"atype": "设备采购", "title": "冒烟测试采购", "amount": 80000}, token=TOKENS["employee"])
aid = na["id"]
req("POST", f"/approvals/{aid}/action?act=通过&comment=同意", token=TOKENS["supervisor"])  # 8万 -> 转董事长
req("POST", f"/approvals/{aid}/action?act=通过", token=TOKENS["supervisor"], expect=400)  # 已流转
req("POST", f"/approvals/{aid}/action?act=通过&comment=终审同意", token=TOKENS["chairman"])
d = req("GET", f"/approvals/{aid}", token=TOKENS["admin"])
assert d["status"] == "已通过", d["status"]

print("== 目标考核 ==")
req("GET", "/assessment/indicators?company_id=1&year=2026", token=TOKENS["admin"])
req("POST", "/assessment/indicators", {"company_id": 1, "year": 2026, "name": "测试指标", "target": 100, "unit": "项"}, token=TOKENS["supervisor"])
req("GET", "/assessment/evaluations?year=2025", token=TOKENS["admin"])

print("== 成果转化 ==")
ach = req("GET", "/transfer/achievements", token=TOKENS["admin"])
pub = next(a for a in ach if a["status"] == "已发布")
co = req("POST", "/transfer/cooperations", {"achievement_id": pub["id"], "intent": "冒烟测试合作"}, token=TOKENS["company"])
req("POST", f"/transfer/cooperations/{co['id']}/tracks", {"stage": "洽谈", "progress": "初步沟通"}, token=TOKENS["secretary"])

print("== 平台管理 ==")
req("GET", "/auth/users", token=TOKENS["admin"])
req("GET", "/platform/menus", token=TOKENS["admin"])
req("GET", "/platform/groups", token=TOKENS["admin"])
req("GET", "/platform/audit-logs", token=TOKENS["admin"])
req("GET", "/platform/login-logs", token=TOKENS["admin"])
req("POST", "/platform/handover", {"from_user": "employee", "to_user": "supervisor", "scope": "全部业务"}, token=TOKENS["admin"])
msgs = req("GET", "/platform/messages", token=TOKENS["chairman"])
assert msgs["unread"] >= 1
req("POST", "/platform/messages/send?title=测试&content=测试消息&channel=邮件&receiver_role=all", token=TOKENS["secretary"])

print(f"\n通过 {PASS} 项, 失败 {len(FAIL)} 项")
for f in FAIL:
    print("FAIL:", f)
