# -*- coding: utf-8 -*-
"""数据库连接、表结构与种子数据"""
import os
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(DATA_DIR, "asset.db")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def q(sql, params=()):
    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def q1(sql, params=()):
    rows = q(sql, params)
    return rows[0] if rows else None


def ex(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,                -- admin/chairman/secretary/supervisor/employee/company
    role_name TEXT NOT NULL,
    company_id INTEGER,
    dept TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    status INTEGER DEFAULT 1,          -- 1启用 0停用
    must_change_pwd INTEGER DEFAULT 1, -- 首次登录需改密
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS tokens (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, username TEXT, ip TEXT, action TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, username TEXT, module TEXT, action TEXT, detail TEXT, ip TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, parent_id INTEGER, leader TEXT DEFAULT '', duty TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    credit_code TEXT UNIQUE,
    ctype TEXT DEFAULT '参股',          -- 全资/控股/参股
    legal_rep TEXT, phone TEXT, email TEXT,
    reg_capital REAL, address TEXT,
    founded_date TEXT, biz_scope TEXT,
    industry TEXT, scale TEXT,
    emp_count INTEGER DEFAULT 0,
    assets REAL DEFAULT 0, revenue REAL DEFAULT 0, profit REAL DEFAULT 0,
    holder_ratio REAL DEFAULT 0,       -- 学校持股比例
    status TEXT DEFAULT '正常',         -- 正常/注销/风险关注
    ext TEXT DEFAULT '{}',             -- 扩展信息 JSON: 知识产权/科研项目/荣誉等
    last_audit_date TEXT,
    audit_cycle INTEGER DEFAULT 1,     -- 审计周期(年)
    deleted INTEGER DEFAULT 0,
    delete_reason TEXT,
    created_by TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS equity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    shareholder TEXT NOT NULL, ratio REAL, method TEXT, invest_time TEXT, remark TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    name TEXT NOT NULL, category TEXT DEFAULT '其他',
    file_name TEXT, file_path TEXT,
    uploaded_by TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS certificates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    cert_name TEXT NOT NULL, cert_no TEXT, expire_date TEXT, status TEXT DEFAULT '有效'
);
CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, category TEXT, content TEXT, publish_date TEXT, source TEXT
);
CREATE TABLE IF NOT EXISTS rule_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, content TEXT, remind_date TEXT, target TEXT, status TEXT DEFAULT '待处理'
);
CREATE TABLE IF NOT EXISTS risk_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER, rtype TEXT, level TEXT, content TEXT,
    status TEXT DEFAULT '未处理', created_at TEXT
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    atype TEXT NOT NULL,               -- 设备采购/出差申请/费用报销/用印申请/合同审批
    title TEXT NOT NULL, reason TEXT,
    amount REAL DEFAULT 0,
    applicant_id INTEGER, applicant TEXT, company_id INTEGER,
    status TEXT DEFAULT '待审批',       -- 待主管审批/待董事长审批/已通过/已驳回
    current_node TEXT DEFAULT '部门主管',
    created_at TEXT, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS approval_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    approval_id INTEGER NOT NULL, approver TEXT, approver_role TEXT,
    action TEXT, comment TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS kpi_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL, year INTEGER NOT NULL,
    name TEXT NOT NULL, category TEXT DEFAULT '财务指标',  -- 财务/非财务
    target REAL, unit TEXT, weight REAL DEFAULT 0, standard TEXT
);
CREATE TABLE IF NOT EXISTS kpi_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_id INTEGER NOT NULL, period TEXT, value REAL, progress REAL,
    comment TEXT, record_time TEXT
);
CREATE TABLE IF NOT EXISTS kpi_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER, year INTEGER, total_score REAL, grade TEXT,
    comment TEXT, evaluator TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, field TEXT, features TEXT, innovation TEXT,
    prospect TEXT, owner TEXT, company_id INTEGER,
    status TEXT DEFAULT '待审核',        -- 待审核/已发布/转化中/已转化
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS cooperations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id INTEGER NOT NULL, company_id INTEGER,
    applicant TEXT, intent TEXT, agreement TEXT,
    status TEXT DEFAULT '意向沟通',      -- 意向沟通/洽谈中/已签约/已完成
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS transfer_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coop_id INTEGER NOT NULL, stage TEXT, progress TEXT,
    fund_used REAL DEFAULT 0, problems TEXT, update_time TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, content TEXT,
    channel TEXT DEFAULT '系统',         -- 系统/邮件/短信
    receiver TEXT, receiver_role TEXT,
    status TEXT DEFAULT '未读', created_at TEXT
);
CREATE TABLE IF NOT EXISTS msg_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL, channel TEXT DEFAULT '邮件', subject TEXT, content TEXT
);
CREATE TABLE IF NOT EXISTS perm_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL, perms TEXT DEFAULT '', description TEXT
);
CREATE TABLE IF NOT EXISTS user_groups (
    user_id INTEGER NOT NULL, group_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, group_id)
);
CREATE TABLE IF NOT EXISTS menus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, key TEXT UNIQUE NOT NULL, icon TEXT,
    sort INTEGER DEFAULT 0, visible INTEGER DEFAULT 1, layout TEXT DEFAULT 'sidebar'
);
CREATE TABLE IF NOT EXISTS handovers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user TEXT, to_user TEXT, scope TEXT, detail TEXT,
    status TEXT DEFAULT '已完成', created_at TEXT
);
"""

# ---------------- 种子数据 ----------------
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def hash_pwd(raw: str, salt: str = "hawei") -> str:
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", (salt + raw).encode(), b"asset_salt", 60000).hex()


COMPANY_SEED = [
    # name, ctype, legal_rep, industry, scale, emp, reg_capital, assets, revenue, profit, holder_ratio, months_ago
    ("威海哈威科技园发展有限公司", "全资", "王安", "科技服务", "大型", 156, 5000, 12800, 4600, 520, 100, 96),
    ("威海哈威光电技术有限公司", "控股", "李明远", "光电子", "中型", 88, 2000, 5600, 3100, 280, 55, 82),
    ("哈工大威海智能装备有限公司", "参股", "张建国", "智能制造", "中型", 120, 3000, 7200, 5800, 460, 30, 70),
    ("威海海洋监测设备有限公司", "参股", "刘志强", "仪器仪表", "小型", 45, 800, 1900, 1400, 120, 25, 64),
    ("威海新材料研究院有限公司", "参股", "陈思远", "新材料", "中型", 76, 2500, 4800, 2600, 180, 20, 58),
    ("哈威软件技术有限公司", "参股", "赵启明", "软件信息", "小型", 62, 600, 1500, 2100, 210, 35, 52),
    ("威海环保节能科技有限公司", "参股", "孙立军", "节能环保", "小型", 38, 500, 1100, 860, 60, 15, 47),
    ("哈威精密机械制造有限公司", "参股", "周文斌", "机械制造", "中型", 95, 1800, 4200, 3600, 250, 40, 43),
    ("威海生物制药开发有限公司", "参股", "吴春华", "生物医药", "小型", 52, 1200, 2600, 1500, 90, 22, 38),
    ("哈威电子信息有限公司", "参股", "郑海涛", "电子信息", "小型", 41, 700, 1600, 1200, 75, 18, 34),
    ("威海机器人科技有限公司", "参股", "冯国栋", "智能制造", "小型", 34, 500, 950, 780, 45, 12, 30),
    ("哈威新能源开发有限公司", "参股", "褚天宇", "新能源", "中型", 70, 2200, 5000, 2900, 160, 28, 26),
    ("威海电子商务有限公司", "参股", "卫红梅", "电子商务", "小型", 48, 400, 900, 1800, 130, 10, 23),
    ("哈威教育培训有限公司", "参股", "蒋文静", "教育培训", "小型", 29, 300, 600, 950, 85, 8, 20),
    ("威海大数据服务有限公司", "参股", "沈兆丰", "软件信息", "小型", 36, 450, 1000, 1300, 95, 15, 17),
    ("哈威人工智能研究院", "参股", "韩雪莹", "人工智能", "小型", 44, 800, 1700, 1100, 70, 20, 14),
    ("威海先进复合材料公司", "参股", "曹志刚", "新材料", "小型", 33, 550, 1250, 900, 55, 14, 11),
    ("哈威医疗器械有限公司", "参股", "谢雨欣", "医疗器械", "小型", 40, 900, 2000, 1350, 110, 16, 8),
    ("威海智能交通科技有限公司", "参股", "罗俊峰", "智能交通", "小型", 27, 350, 700, 560, 30, 10, 6),
    ("哈威农业科技公司", "参股", "范文博", "现代农业", "小型", 22, 250, 480, 380, 18, 6, 4),
    ("威海文化创意有限公司", "参股", "秦丽娜", "文化创意", "小型", 19, 200, 400, 520, 40, 8, 2),
    ("哈威检验检测有限公司", "参股", "何俊杰", "检验检测", "小型", 31, 380, 850, 700, 52, 12, 1),
]

CERT_SEED = [
    ("威海哈威科技园发展有限公司", "高新技术企业证书", "GR202337000123", 2),   # 2个月后到期
    ("威海哈威科技园发展有限公司", "营业执照", "91371000MA3XXXXX01", 60),
    ("威海哈威光电技术有限公司", "经营许可证", "EW202437000456", 1),
    ("威海哈威光电技术有限公司", "专利证书(发明)", "ZL202310123456.7", 36),
    ("哈工大威海智能装备有限公司", "ISO9001质量体系认证", "Q202437000789", 3),
    ("哈威软件技术有限公司", "软件企业认定证书", "RQ202337000321", -1),        # 已过期(风险)
    ("威海生物制药开发有限公司", "药品生产许可证", "YP202437000888", 5),
    ("威海环保节能科技有限公司", "节能产品认证", "JN202337000666", 1),
]

POLICY_SEED = [
    ("关于促进企业数字化转型的指导意见", "国家政策", "推动企业加快数字化转型，加强资产信息化管理，提升资产使用效率与监管水平。", "2025-01-15", "国务院办公厅"),
    ("国有资产管理办法（修订版）", "资产管理", "规范国有资产配置、使用、处置等各环节管理，强化资产保值增值考核。", "2025-02-20", "财政部"),
    ("高校所属企业体制改革相关政策解读", "行业监管", "明确高校资产经营公司职责边界，防止连带责任，规范校办企业运营监管。", "2025-03-10", "教育部"),
    ("税收优惠政策调整通知", "税收政策", "高新技术企业减按15%税率征收企业所得税，研发费用加计扣除比例提高至100%。", "2025-04-01", "税务总局"),
    ("关于加强校办企业审计监督的实施意见", "审计监督", "校办企业应按期开展年度审计，逾期未审计企业将被纳入重点监管名单。", "2025-04-20", "省审计厅"),
]

RISK_SEED = [
    (6, "工商异常", "高", "未按规定期限公示年度报告，被列入经营异常名录", "未处理"),
    (13, "法律纠纷", "中", "存在一起合同纠纷诉讼案件，正在审理中", "未处理"),
    (19, "行政处罚", "低", "消防检查发现隐患，已责令限期整改", "处理中"),
]

APPROVAL_SEED = [
    ("设备采购", "直播实训设备采购(电商实验室与校办电商公司共用)", 68000, 6, "待董事长审批", "待董事长审批"),
    ("设备采购", "办公电脑采购10台", 45000, 7, "待主管审批", "部门主管"),
    ("用印申请", "项目合作协议用印", 0, 8, "待主管审批", "部门主管"),
    ("合同审批", "智能装备产线扩建合同", 320000, 3, "待董事长审批", "待董事长审批"),
    ("费用报销", "参加行业展会差旅费", 3800, 6, "已通过", "已办结"),
    ("出差申请", "赴上海对接科技成果转化事宜", 0, 7, "已通过", "已办结"),
]

KPI_SEED = [
    # company_idx, name, category, target, unit, weight
    (0, "营业收入", "财务指标", 5000, "万元", 30),
    (0, "利润总额", "财务指标", 600, "万元", 25),
    (0, "国有资产保值增值率", "财务指标", 105, "%", 20),
    (0, "科技成果转化项目数", "非财务指标", 5, "项", 15),
    (0, "接收学生实习人数", "非财务指标", 80, "人", 10),
    (1, "营业收入", "财务指标", 3500, "万元", 40),
    (1, "利润总额", "财务指标", 320, "万元", 30),
    (1, "研发投入占比", "非财务指标", 8, "%", 30),
    (2, "营业收入", "财务指标", 6500, "万元", 35),
    (2, "利润总额", "财务指标", 500, "万元", 25),
    (2, "新增知识产权数量", "非财务指标", 12, "件", 20),
    (2, "人才培养引进", "非财务指标", 15, "人", 20),
]

ACHIEVEMENT_SEED = [
    ("高精度海洋浮标监测系统", "海洋工程", "基于北斗通信的多参数海洋环境实时监测浮标，测量精度达行业领先水平", "采用自校准传感器阵列，数据可靠率99.5%", "可广泛应用于海洋牧场、港口监测", "张建国教授团队", "已发布"),
    ("锂电池健康状态在线评估技术", "新能源", "基于阻抗谱的锂电池SOH在线无损评估方法", "评估误差<3%，无需拆解电池包", "新能源汽车、储能电站运维", "李明远团队", "转化中"),
    ("工业机器人视觉引导抓取系统", "智能制造", "融合深度学习的机器人无序分拣视觉系统", "抓取成功率99.2%，节拍0.8秒/件", "3C制造、物流分拣场景", "王磊博士团队", "已发布"),
    ("功能海洋食品精深加工技术", "生物技术", "从海藻中提取岩藻黄素的高效绿色工艺", "提取率提升40%，成本降低25%", "功能食品、化妆品原料", "刘明教授团队", "待审核"),
]

USER_SEED = [
    # username, pwd, name, role, role_name, dept, company_idx
    ("admin", "admin123", "系统管理员", "admin", "管理员", "信息中心", None),
    ("chairman", "chair123", "王安", "chairman", "董事长", "总经理办公室", None),
    ("secretary", "secret123", "林秘书", "secretary", "秘书", "综合管理部", None),
    ("supervisor", "super123", "赵主管", "supervisor", "主管", "企业管理部", None),
    ("employee", "emp123", "小刘", "employee", "员工", "企业管理部", None),
    ("company", "comp123", "李明远", "company", "企业用户", "威海哈威光电技术有限公司", 1),
]

MENU_SEED = [
    ("综合数据看板", "dashboard", "monitor", 1),
    ("企业信息报表", "report", "table", 2),
    ("企业信息管理", "company", "building", 3),
    ("企业规范提醒", "remind", "bell", 4),
    ("业务审批", "approval", "stamp", 5),
    ("企业目标考核", "assessment", "trophy", 6),
    ("成果转化", "transfer", "bulb", 7),
    ("平台管理", "platform", "setting", 8),
]


def seed():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] > 0:
        conn.close()
        return

    # 部门
    depts = [("总经理办公室", None, "王安", "战略决策与重大事项审批"),
             ("企业管理部", None, "赵主管", "校办企业日常管理与考核"),
             ("财务部", None, "钱会计", "财务核算与资金监管"),
             ("审计法务部", None, "孙审计", "内部审计与合规风控"),
             ("科研合作部", None, "周老师", "科技成果转化与校企合作"),
             ("信息中心", None, "系统管理员", "信息化建设与运维")]
    for d in depts:
        cur.execute("INSERT INTO departments(name,parent_id,leader,duty) VALUES(?,?,?,?)", d)

    # 企业
    for i, c in enumerate(COMPANY_SEED):
        name, ctype, legal, industry, scale, emp, reg, assets, rev, profit, ratio, months = c
        founded = (datetime.now() - timedelta(days=months * 30 + 15)).strftime("%Y-%m-%d")
        # 审计: 部分企业逾期未审计
        last_audit = (datetime.now() - timedelta(days=460 if i in (2, 5, 9, 13, 17) else 120)).strftime("%Y-%m-%d")
        cycle = 2 if i in (2, 5, 9) else 1
        ext = {"ip_count": 8 + i, "projects": 2 + i % 4, "honors": i % 3,
               "rd_invest": round(rev * 0.05, 1), "subsidy": round(assets * 0.02, 1)}
        cur.execute("""INSERT INTO companies(name,credit_code,ctype,legal_rep,phone,email,reg_capital,address,
            founded_date,biz_scope,industry,scale,emp_count,assets,revenue,profit,holder_ratio,status,ext,
            last_audit_date,audit_cycle,created_by,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, f"91371000MA{i:05d}X"[:18], ctype, legal, f"0631-5687{100+i:03d}",
                     f"contact{i}@hawei-hitwh.com", reg, f"威海市文化西路2号哈工大科技园{i}号楼",
                     founded, f"{industry}相关业务", industry, scale, emp, assets, rev, profit, ratio,
                     "正常", str(ext).replace("'", '"'), last_audit, cycle, "secretary", NOW))
        # 股权结构
        cur.execute("INSERT INTO equity(company_id,shareholder,ratio,method,invest_time,remark) VALUES(?,?,?,?,?,?)",
                    (i + 1, "威海哈威资产经营有限责任公司", ratio, "货币出资", founded, "学校资产经营公司持股"))
        other = 100 - ratio
        if other > 0:
            cur.execute("INSERT INTO equity(company_id,shareholder,ratio,method,invest_time,remark) VALUES(?,?,?,?,?,?)",
                        (i + 1, "社会投资方/自然人股东", other, "货币出资", founded, "外部股东"))

    # 证照
    for name, cert, no, months_left in CERT_SEED:
        idx = next(i for i, c in enumerate(COMPANY_SEED) if c[0] == name)
        expire = (datetime.now() + timedelta(days=months_left * 30)).strftime("%Y-%m-%d")
        status = "已过期" if months_left < 0 else ("即将到期" if months_left <= 3 else "有效")
        cur.execute("INSERT INTO certificates(company_id,cert_name,cert_no,expire_date,status) VALUES(?,?,?,?,?)",
                    (idx + 1, cert, no, expire, status))

    # 政策法规
    for p in POLICY_SEED:
        cur.execute("INSERT INTO policies(title,category,content,publish_date,source) VALUES(?,?,?,?,?)", p)

    # 制度提醒
    rules = [("月度财务结账提醒", "每月25日前完成当月费用报销流程，财务部26日起结账", "2026-10-25", "财务部/各企业"),
             ("校办企业年度审计提醒", "列入年度审计计划的企业请于11月底前完成审计并提交报告", "2026-11-30", "审计法务部"),
             ("新员工入职流程提醒", "招聘新员工须遵循招聘流程与标准，报人事备案", "2026-10-30", "各部门")]
    for r in rules:
        cur.execute("INSERT INTO rule_reminders(title,content,remind_date,target) VALUES(?,?,?,?)", r)

    # 风险
    for r in RISK_SEED:
        cur.execute("INSERT INTO risk_alerts(company_id,rtype,level,content,status,created_at) VALUES(?,?,?,?,?,?)",
                    (r[0], r[1], r[2], r[3], r[4], NOW))

    # 用户
    for u in USER_SEED:
        username, pwd, name, role, role_name, dept, cidx = u
        cid = (cidx + 1) if cidx is not None else None
        cur.execute("""INSERT INTO users(username,password,name,role,role_name,company_id,dept,phone,email,status,must_change_pwd,created_at)
            VALUES(?,?,?,?,?,?,?,?,'',1,0,?)""",
                    (username, hash_pwd(pwd), name, role, role_name, cid, dept, f"138000011{len(username)%100:02d}", NOW))
    # 再给几家参股企业配企业用户
    for i in (0, 2, 5):
        c = COMPANY_SEED[i]
        cur.execute("""INSERT INTO users(username,password,name,role,role_name,company_id,dept,phone,email,status,must_change_pwd,created_at)
            VALUES(?,?,?,?,?,?,?,'','',1,0,?)""",
                    (f"ent{i+1}", hash_pwd("ent123"), c[2], "company", "企业用户", i + 1, c[0], NOW))

    # 审批流程
    for atype, title, amount, cidx, status, node in APPROVAL_SEED:
        cid = cidx
        cur.execute("""INSERT INTO approvals(atype,title,reason,amount,applicant_id,applicant,company_id,status,current_node,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (atype, title, f"{atype}事由说明，相关明细见附件材料。", amount, 5, "小刘", cid, status, node, NOW))
    cur.execute("""INSERT INTO approval_logs(approval_id,approver,approver_role,action,comment,created_at)
        VALUES(1,'赵主管','主管','通过','情况属实，同意采购，报董事长终审。',?)""", (NOW,))
    cur.execute("""INSERT INTO approval_logs(approval_id,approver,approver_role,action,comment,created_at)
        VALUES(3,'王安','董事长','通过','同意报销。',?)""", (NOW,))
    cur.execute("""INSERT INTO approval_logs(approval_id,approver,approver_role,action,comment,created_at)
        VALUES(4,'王安','董事长','通过','同意出差。',?)""", (NOW,))

    # KPI
    for cidx, name, cat, target, unit, weight in KPI_SEED:
        cid = cidx + 1
        cur.execute("""INSERT INTO kpi_indicators(company_id,year,name,category,target,unit,weight,standard)
            VALUES(?,?,?,?,?,?,?,?)""", (cid, 2026, name, cat, target, unit, weight, "按季度分解目标值"))
        iid = cur.lastrowid
        cur.execute("INSERT INTO kpi_records(indicator_id,period,value,progress,comment,record_time) VALUES(?,?,?,?,?,?)",
                    (iid, "Q1", round(target * 0.22, 1), 22, "一季度完成情况", NOW))
        cur.execute("INSERT INTO kpi_records(indicator_id,period,value,progress,comment,record_time) VALUES(?,?,?,?,?,?)",
                    (iid, "Q2", round(target * 0.28, 1), 50, "上半年累计", NOW))

    # 评价
    cur.execute("INSERT INTO kpi_evaluations(company_id,year,total_score,grade,comment,evaluator,created_at) VALUES(?,?,?,?,?,?,?)",
                (1, 2025, 91.5, "优秀", "全面完成各项考核指标，资产保值增值成效显著", "校办企业管理委员会", NOW))
    cur.execute("INSERT INTO kpi_evaluations(company_id,year,total_score,grade,comment,evaluator,created_at) VALUES(?,?,?,?,?,?,?)",
                (2, 2025, 85.0, "良好", "营收未达预期，研发投入保持增长", "校办企业管理委员会", NOW))

    # 成果
    for name, field, feat, innov, prospect, owner, status in ACHIEVEMENT_SEED:
        cur.execute("""INSERT INTO achievements(name,field,features,innovation,prospect,owner,status,created_at)
            VALUES(?,?,?,?,?,?,?,?)""", (name, field, feat, innov, prospect, owner, status, NOW))
    cur.execute("INSERT INTO cooperations(achievement_id,company_id,applicant,intent,agreement,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (2, 3, "哈工大威海智能装备有限公司", "拟将该技术应用于储能电站运维业务", "技术许可合同(草拟中)", "洽谈中", NOW))
    cur.execute("INSERT INTO cooperations(achievement_id,company_id,applicant,intent,agreement,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (3, 9, "威海电子商务有限公司", "仓储物流自动分拣改造", "技术开发合同", "已签约", NOW))
    cur.execute("INSERT INTO transfer_tracks(coop_id,stage,progress,fund_used,problems,update_time) VALUES(?,?,?,?,?,?)",
                (1, "技术开发", "视觉算法适配完成60%，设备联调下月启动", 35.0, "场地改造进度滞后", NOW))
    cur.execute("INSERT INTO transfer_tracks(coop_id,stage,progress,fund_used,problems,update_time) VALUES(?,?,?,?,?,?)",
                (2, "中试验证", "锂电池SOH评估模块已完成实验室验证", 58.0, "无", NOW))

    # 消息与模板
    msgs = [("关于开展2026年度校办企业审计的通知", "请各列入计划的企业于11月30日前完成审计并提交报告。", "系统", "all"),
            ("高新技术企业证书即将到期提醒", "威海哈威科技园发展有限公司的高新技术企业证书将于2个月后到期，请及时办理续期。", "邮件", "ent1"),
            ("风险提示：企业列入经营异常名录", "哈威软件技术有限公司因未按期公示年报被列入经营异常名录，请尽快处理。", "短信", "chairman")]
    for t, c, ch, rcv in msgs:
        cur.execute("INSERT INTO messages(title,content,channel,receiver,status,created_at) VALUES(?,?,?,?, '未读', ?)", (t, c, ch, rcv, NOW))
    cur.execute("INSERT INTO msg_templates(name,channel,subject,content) VALUES(?,?,?,?)",
                ("审计到期提醒模板", "邮件", "【资产经营公司】审计任务到期提醒", "尊敬的{企业名称}：贵司年度审计任务即将到期({到期日期})，请及时安排审计并提交报告。"))
    cur.execute("INSERT INTO msg_templates(name,channel,subject,content) VALUES(?,?,?,?)",
                ("证照到期提醒模板", "短信", "证照到期提醒", "{企业名称}的{证照名称}将于{到期日期}到期，请及时办理续期。"))

    # 权限组
    groups = [("系统管理员组", "all", "拥有系统所有功能的操作权限"),
              ("董事长组", "dashboard,report,company:view,approval:chair,assessment,transfer,remind", "重大事项终审权"),
              ("秘书组", "dashboard,report,company:manage,approval:launch,remind:manage,transfer:manage", "企业信息录入维护与提醒发布"),
              ("主管组", "dashboard,report,company:view,approval:dept,assessment:manage", "部门审批与考核管理"),
              ("员工组", "report,approval:launch", "报表查询与业务申请"),
              ("企业用户组", "company:self,approval:launch,remind:self,transfer:apply", "本企业信息与业务申请")]
    for g in groups:
        cur.execute("INSERT INTO perm_groups(name,perms,description) VALUES(?,?,?)", g)
    cur.execute("INSERT INTO user_groups(user_id,group_id) VALUES(1,1)")
    cur.execute("INSERT INTO user_groups(user_id,group_id) VALUES(2,2)")
    cur.execute("INSERT INTO user_groups(user_id,group_id) VALUES(3,3)")
    cur.execute("INSERT INTO user_groups(user_id,group_id) VALUES(4,4)")
    cur.execute("INSERT INTO user_groups(user_id,group_id) VALUES(5,5)")

    # 菜单
    for name, key, icon, sort in MENU_SEED:
        cur.execute("INSERT INTO menus(name,key,icon,sort,visible) VALUES(?,?,?,?,1)", (name, key, icon, sort))

    # 历史月度企业增量 (近24个月注册累计, 供趋势图)
    conn.commit()
    conn.close()
    print("数据库初始化完成: ", DB_PATH)


if __name__ == "__main__":
    seed()
