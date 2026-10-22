/* 资产经营公司管理系统 - 前端 SPA */
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const money = (v) => Number(v || 0).toLocaleString("zh-CN", { maximumFractionDigits: 1 });
const wan = (v) => { v = Number(v || 0); return v >= 10000 ? (v / 10000).toFixed(1) + " 万" : v.toFixed(1); };

const S = { token: localStorage.getItem("ams_token") || "", user: null, view: "dashboard", charts: [] };

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (S.token) headers["Authorization"] = "Bearer " + S.token;
  const res = await fetch("/api" + path, { ...opts, headers, body: opts.body ? JSON.stringify(opts.body) : undefined });
  if (res.status === 401) { logout(true); throw new Error("登录已失效"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "请求失败");
  return data;
}

/* ---------- UI 基础 ---------- */
function toast(msg, type = "") {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast " + type;
  clearTimeout(t._tm); t._tm = setTimeout(() => t.classList.add("hidden"), 2600);
}
const UI = {
  openModal(title, bodyHtml, footHtml = "") {
    $("#modal-title").textContent = title;
    $("#modal-body").innerHTML = bodyHtml;
    $("#modal-foot").innerHTML = footHtml;
    $("#modal-mask").classList.remove("hidden");
  },
  closeModal() { $("#modal-mask").classList.add("hidden"); },
  confirm(msg, onOk) {
    UI.openModal("请确认", `<p style="line-height:1.8">${esc(msg)}</p>`,
      `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="cfm-ok">确定</button>`);
    $("#cfm-ok").onclick = async () => { UI.closeModal(); await onOk(); };
  },
  detail(title, rows) {
    const html = `<dl class="desc-list">` + rows.map(([k, v, full]) =>
      `<dt>${esc(k)}</dt><dd${full ? ' class="full"' : ""}>${v ?? "-"}</dd>`).join("") + `</dl>`;
    UI.openModal(title, html, `<button class="btn primary" onclick="UI.closeModal()">关闭</button>`);
  },
};
function chart(id, option) {
  const el = document.getElementById(id);
  if (!el) return;
  let inst = echarts.getInstanceByDom(el);
  if (!inst) inst = echarts.init(el);
  S.charts.push(inst);
  inst.setOption(option, true);
}
function disposeCharts() { S.charts.forEach((c) => { try { c.dispose(); } catch (e) {} }); S.charts = []; }

const TAG = (v) => {
  const map = { "已通过": "green", "正常": "green", "有效": "green", "已办结": "green", "已发布": "blue", "已转化": "green", "已签约": "green", "已完成": "green", "已审核": "green", "已读": "gray", "全资": "blue", "控股": "orange", "参股": "gray", "待审核": "orange", "即将到期": "orange", "转化中": "blue", "洽谈中": "blue", "意向沟通": "gray", "待处理": "orange", "未处理": "red", "已过期": "red", "已驳回": "red", "高": "red", "中": "orange", "低": "gray", "处理中": "orange", "已退回": "red", "注销": "gray" };
  return `<span class="tag ${map[v] || "gray"}">${esc(v)}</span>`;
};

/* ---------- 登录/登出 ---------- */
async function doLogin() {
  const username = $("#login-username").value.trim(), password = $("#login-password").value;
  const err = $("#login-error"); err.classList.add("hidden");
  try {
    const d = await api("/auth/login", { method: "POST", body: { username, password } });
    S.token = d.token; localStorage.setItem("ams_token", d.token);
    S.user = d.user;
    enterApp();
    if (d.must_change_pwd) $("#pwd-modal").classList.remove("hidden");
  } catch (e) { err.textContent = e.message; err.classList.remove("hidden"); }
}
function logout(silent) {
  if (!silent && S.token) api("/auth/logout", { method: "POST" }).catch(() => {});
  S.token = ""; S.user = null; localStorage.removeItem("ams_token");
  $("#app").classList.add("hidden"); $("#login-page").classList.remove("hidden");
  $("#login-password").value = "";
}
async function enterApp() {
  try { S.user = S.user || await api("/auth/me"); } catch (e) { return; }
  $("#login-page").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#user-name").textContent = S.user.name;
  $("#user-role").textContent = S.user.role_name;
  renderMenu(); switchView(S.user.role === "admin" ? "dashboard" : allowedViews()[0] || "report");
  refreshMsgBadge();
}
function allowedViews() {
  const base = S.user.menus || [];
  return base;
}
function refreshMsgBadge() {
  if (!S.user) return;
  api("/platform/messages").then((d) => {
    const b = $("#msg-count");
    if (d.unread > 0) { b.textContent = d.unread > 99 ? "99+" : d.unread; b.classList.remove("hidden"); }
    else b.classList.add("hidden");
  }).catch(() => {});
}

/* ---------- 菜单 ---------- */
const VIEW_META = {
  dashboard: ["综合数据看板", "📊"], report: ["企业信息报表", "📋"], company: ["企业信息管理", "🏢"],
  remind: ["企业规范提醒", "⚠️"], approval: ["业务审批", "🖊"], assessment: ["企业目标考核", "🎯"],
  transfer: ["成果转化", "💡"], platform: ["平台管理", "⚙️"],
};
const VIEWS = { dashboard: viewDashboard, report: viewReport, company: viewCompany, remind: viewRemind,
  approval: viewApproval, assessment: viewAssessment, transfer: viewTransfer, platform: viewPlatform };
async function renderMenu() {
  const menus = allowedViews();
  const sb = $("#sidebar"), tn = $("#topnav");
  const items = menus.map((k) => `<div class="menu-item" data-view="${k}">${VIEW_META[k]?.[1] || "•"} ${VIEW_META[k]?.[0] || k}</div>`).join("");
  sb.innerHTML = items;
  tn.innerHTML = items;
  $$(".menu-item").forEach((el) => el.onclick = () => switchView(el.dataset.view));
}
function switchView(v) {
  if (!allowedViews().includes(v)) v = allowedViews()[0];
  S.view = v; disposeCharts();
  $$(".menu-item").forEach((el) => el.classList.toggle("active", el.dataset.view === v));
  const V = VIEWS[v];
  $("#content").innerHTML = "";
  V && V($("#content"));
  window.scrollTo(0, 0);
}

/* ================= 视图: 综合数据看板 ================= */
function viewDashboard(root) {
  root.innerHTML = `
  <div class="page-head"><div><h2>综合数据看板</h2><div class="sub">校办企业运营全景 · 实时监控与决策支持</div></div></div>
  <div class="stat-grid" id="d-stats"></div>
  <div class="grid-2">
    <div class="card"><h3>企业增量统计(近24个月)</h3><div id="ch-trend" class="chart"></div></div>
    <div class="card"><h3>企业类型构成</h3><div id="ch-type" class="chart"></div></div>
  </div>
  <div class="grid-2">
    <div class="card"><h3>营业收入 TOP8 (万元)</h3><div id="ch-rev" class="chart"></div></div>
    <div class="card"><h3>利润总额 TOP8 (万元)</h3><div id="ch-profit" class="chart"></div></div>
  </div>
  <div class="grid-2">
    <div class="card"><h3>行业分布</h3><div id="ch-ind" class="chart"></div></div>
    <div class="card"><h3>企业规模分布(员工人数)</h3><div id="ch-scale" class="chart"></div></div>
  </div>
  <div class="grid-2">
    <div class="card"><h3>逾期未审计企业</h3><div id="d-overdue"></div></div>
    <div class="card"><h3>未处理风险告警</h3><div id="d-risk"></div></div>
  </div>`;
  api("/dashboard/overview").then((d) => {
    const cards = [
      ["在管企业总数", d.company_count + " 家", `全资${d.by_type["全资"]} · 控股${d.by_type["控股"]} · 参股${d.by_type["参股"]}`, "c1"],
      ["资产总额", wan(d.total_assets) + " 元", "校办企业资产合计", "c2"],
      ["年营收合计", wan(d.total_revenue) + " 元", "最近财务年度", "c3"],
      ["年利润合计", wan(d.total_profit) + " 元", "最近财务年度", "c6"],
      ["员工总人数", d.total_emp + " 人", "校办企业在职员工", "c5"],
      ["逾期未审计", d.overdue_audit + " 家", "需尽快安排审计", "c4"],
      ["未处理风险", d.risk_open + " 项", "工商异常/纠纷/处罚", "c4"],
      ["待办审批", d.pending_approvals + " 件", "在途审批流程", "c3"],
    ];
    $("#d-stats").innerHTML = cards.map(([l, n, t, c]) =>
      `<div class="stat-card ${c}"><div class="lbl">${l}</div><div class="num">${n}</div><div class="trend muted">${t}</div></div>`).join("");
  });
  api("/dashboard/trend").then((d) => chart("ch-trend", {
    tooltip: { trigger: "axis" }, legend: { data: ["新增企业", "累计企业"] },
    grid: { left: 40, right: 20, bottom: 30, top: 40 },
    xAxis: { type: "category", data: d.months },
    yAxis: [{ type: "value", name: "新增" }, { type: "value", name: "累计" }],
    series: [
      { name: "新增企业", type: "bar", data: d.added, itemStyle: { color: "#2563eb", borderRadius: [4, 4, 0, 0] } },
      { name: "累计企业", type: "line", yAxisIndex: 1, smooth: true, data: d.cumulative, itemStyle: { color: "#059669" } },
    ],
  }));
  api("/dashboard/overview").then((d) => chart("ch-type", {
    tooltip: { trigger: "item" }, legend: { bottom: 0 },
    series: [{ type: "pie", radius: ["40%", "68%"], center: ["50%", "44%"],
      data: Object.entries(d.by_type).map(([k, v]) => ({ name: k, value: v })),
      label: { formatter: "{b}: {c}家" } }],
  }));
  api("/dashboard/top-companies").then((d) => {
    const opt = (rows, color) => ({
      tooltip: {}, grid: { left: 130, right: 30, top: 10, bottom: 26 },
      xAxis: { type: "value" }, yAxis: { type: "category", data: rows.map((r) => r.name).reverse(), axisLabel: { width: 118, overflow: "truncate" } },
      series: [{ type: "bar", data: rows.map((r) => r.v).reverse(), itemStyle: { color, borderRadius: [0, 4, 4, 0] }, barWidth: 14 }],
    });
    chart("ch-rev", opt(d.revenue, "#2563eb"));
    chart("ch-profit", opt(d.profit, "#d97706"));
  });
  api("/dashboard/type-distribution").then((d) => chart("ch-ind", {
    tooltip: { trigger: "item" },
    series: [{ type: "pie", radius: "62%", center: ["50%", "48%"],
      data: d.filter((r) => r.n > 0).map((r) => ({ name: r.industry, value: r.n })), label: { fontSize: 11 } }],
  }));
  api("/dashboard/emp-structure").then((d) => chart("ch-scale", {
    tooltip: {}, grid: { left: 50, right: 20, bottom: 30, top: 30 },
    xAxis: { type: "category", data: d.map((r) => r.scale + "型企业") },
    yAxis: { type: "value", name: "人数" },
    series: [{ type: "bar", data: d.map((r) => r.n), itemStyle: { color: "#7c3aed", borderRadius: [4, 4, 0, 0] }, barWidth: 40 }],
  }));
  api("/reminders/audit-overdue").then((rows) => {
    const list = rows.filter((r) => r.overdue_days >= 0).slice(0, 8);
    $("#d-overdue").innerHTML = list.length ? `<table class="tbl"><tr><th>企业</th><th>应审日期</th><th>逾期(天)</th></tr>` +
      list.map((r) => `<tr><td>${esc(r.name)}</td><td>${r.due_date}</td><td><span class="tag red">${r.overdue_days}</span></td></tr>`).join("") + "</table>"
      : `<div class="empty">暂无逾期审计企业 ✓</div>`;
  });
  api("/reminders/risks?status=未处理").then((rows) => {
    $("#d-risk").innerHTML = rows.length ? rows.slice(0, 8).map((r) =>
      `<div style="padding:8px 0;border-bottom:1px dashed var(--border);display:flex;justify-content:space-between;gap:10px">
        <span>${TAG(r.level)} <b>${esc(r.company_name)}</b> ${esc(r.rtype)}</span>
        <span class="muted">${esc((r.content || "").slice(0, 18))}…</span></div>`).join("")
      : `<div class="empty">暂无未处理风险 ✓</div>`;
  });
}

/* ================= 视图: 企业信息报表 ================= */
function viewReport(root) {
  let page = 1, size = 10, kw = "", ctype = "";
  root.innerHTML = `
  <div class="page-head"><div><h2>企业信息报表</h2><div class="sub">全平台在管企业分页报表 · 支持检索与导出</div></div>
    <button class="btn ghost" id="rp-export">导出 CSV</button></div>
  <div class="card">
    <div class="toolbar">
      <input id="rp-kw" placeholder="企业名/法人/联系方式" style="width:220px" value="${esc(kw)}">
      <select id="rp-type"><option value="">全部类型</option><option>全资</option><option>控股</option><option>参股</option></select>
      <button class="btn primary sm" id="rp-search">查询</button>
    </div>
    <div id="rp-body"></div><div class="pager" id="rp-pager"></div>
  </div>`;
  const load = async () => {
    const d = await api(`/dashboard/report?keyword=${encodeURIComponent(kw)}&ctype=${ctype}&page=${page}&size=${size}`);
    $("#rp-body").innerHTML = `<table class="tbl"><tr><th>#</th><th>企业名称</th><th>类型</th><th>法定代表人</th><th>联系方式</th><th>注册资本(万)</th><th>营收(万)</th><th>利润(万)</th><th>员工数</th><th>状态</th><th>操作</th></tr>` +
      d.items.map((c, i) => `<tr>
        <td>${(page - 1) * size + i + 1}</td>
        <td><a onclick="openCompanyDetail(${c.id})">${esc(c.name)}</a></td>
        <td>${TAG(c.ctype)}</td><td>${esc(c.legal_rep)}</td><td>${esc(c.phone)}</td>
        <td>${money(c.reg_capital)}</td><td>${money(c.revenue)}</td><td>${money(c.profit)}</td>
        <td>${c.emp_count}</td><td>${TAG(c.status)} ${c.audit_overdue ? '<span class="tag red">审计逾期</span>' : ""}</td>
        <td class="ops"><a onclick="openCompanyDetail(${c.id})">详情</a></td></tr>`).join("") + "</table>" +
      (d.items.length ? "" : `<div class="empty">未查询到企业数据</div>`);
    const pages = Math.max(1, Math.ceil(d.total / size));
    $("#rp-pager").innerHTML = `<span>共 ${d.total} 条 / ${pages} 页</span>
      <button ${page <= 1 ? "disabled" : ""} id="rp-prev">上一页</button><span>${page} / ${pages}</span>
      <button ${page >= pages ? "disabled" : ""} id="rp-next">下一页</button>`;
    $("#rp-prev").onclick = () => { page--; load(); };
    $("#rp-next").onclick = () => { page++; load(); };
  };
  $("#rp-search").onclick = () => { kw = $("#rp-kw").value.trim(); ctype = $("#rp-type").value; page = 1; load(); };
  $("#rp-kw").onkeydown = (e) => e.key === "Enter" && $("#rp-search").click();
  $("#rp-type").onchange = () => { ctype = $("#rp-type").value; page = 1; load(); };
  $("#rp-export").onclick = () => exportCSV();
  load();
}
async function exportCSV() {
  const d = await api(`/dashboard/report?keyword=&ctype=&page=1&size=9999`);
  const head = ["企业名称", "类型", "统一社会信用代码", "法定代表人", "联系方式", "注册资本(万元)", "资产总额(万元)", "营收(万元)", "利润(万元)", "员工数", "成立日期", "状态"];
  const lines = [head.join(",")].concat(d.items.map((c) =>
    [c.name, c.ctype, c.credit_code, c.legal_rep, c.phone, c.reg_capital, c.assets, c.revenue, c.profit, c.emp_count, c.founded_date, c.status]
      .map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")));
  const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
  a.download = "企业信息报表.csv"; a.click();
}

/* ================= 视图: 企业信息管理 ================= */
function canManageCompany() { return ["admin", "secretary"].includes(S.user.role); }
function viewCompany(root) {
  let page = 1, kw = "", ctype = "", overdue = "";
  root.innerHTML = `
  <div class="page-head"><div><h2>企业信息管理</h2><div class="sub">企业基本信息 / 扩展信息 / 股权 / 文档资料</div></div>
    ${canManageCompany() ? '<button class="btn primary" id="cp-add">+ 录入企业</button>' : ""}</div>
  <div class="card">
    <div class="toolbar">
      <input id="cp-kw" placeholder="企业名/法人/信用代码/行业" style="width:230px">
      <select id="cp-type"><option value="">全部类型</option><option>全资</option><option>控股</option><option>参股</option></select>
      <label class="muted"><input type="checkbox" id="cp-od"> 仅看审计逾期</label>
      <button class="btn primary sm" id="cp-search">查询</button>
    </div>
    <div id="cp-body"></div><div class="pager" id="cp-pager"></div>
  </div>`;
  const load = async () => {
    const d = await api(`/companies?keyword=${encodeURIComponent(kw)}&ctype=${ctype}&audit_overdue=${overdue}&page=${page}&size=10`);
    $("#cp-body").innerHTML = `<table class="tbl"><tr><th>企业名称</th><th>类型</th><th>行业</th><th>持股比例</th><th>营收(万)</th><th>风险</th><th>证照</th><th>审计</th><th>操作</th></tr>` +
      d.items.map((c) => `<tr>
        <td><a onclick="openCompanyDetail(${c.id})">${esc(c.name)}</a></td>
        <td>${TAG(c.ctype)}</td><td>${esc(c.industry)}</td><td>${c.holder_ratio}%</td><td>${money(c.revenue)}</td>
        <td>${c.risk_count ? `<span class="tag red">${c.risk_count}项</span>` : '<span class="tag green">0</span>'}</td>
        <td>${c.cert_expiring ? `<span class="tag orange">${c.cert_expiring}证照临期</span>` : "正常"}</td>
        <td>${c.audit_overdue ? '<span class="tag red">逾期</span>' : "正常"}</td>
        <td class="ops">
          <a onclick="openCompanyDetail(${c.id})">详情</a>
          ${canManageCompany() || (S.user.role === "company" && S.user.company?.id === c.id) ? ` · <a onclick="openCompanyForm(${c.id})">编辑</a>` : ""}
          ${["admin", "secretary"].includes(S.user.role) && (c.ext_status === "待审核") ? ` · <a onclick="reviewExt(${c.id})">审核扩展信息</a>` : ""}
        </td></tr>`).join("") + "</table>" + (d.items.length ? "" : '<div class="empty">暂无数据</div>');
    const pages = Math.max(1, Math.ceil(d.total / 10));
    $("#cp-pager").innerHTML = `<span>共 ${d.total} 条</span>
      <button ${page <= 1 ? "disabled" : ""} id="cp-prev">上一页</button><span>${page} / ${pages}</span>
      <button ${page >= pages ? "disabled" : ""} id="cp-next">下一页</button>`;
    $("#cp-prev").onclick = () => { page--; load(); };
    $("#cp-next").onclick = () => { page++; load(); };
  };
  $("#cp-search").onclick = () => { kw = $("#cp-kw").value.trim(); ctype = $("#cp-type").value; overdue = $("#cp-od").checked ? "1" : ""; page = 1; load(); };
  if (canManageCompany()) $("#cp-add").onclick = () => openCompanyForm();
  load();
}

function companyFormHtml(c = {}) {
  return `<div class="form-grid">
    <div class="field"><label>企业名称 *</label><input id="f-name" value="${esc(c.name || "")}"></div>
    <div class="field"><label>统一社会信用代码</label><input id="f-credit" value="${esc(c.credit_code || "")}"></div>
    <div class="field"><label>企业类型</label><select id="f-ctype">${["全资", "控股", "参股"].map((t) => `<option ${c.ctype === t ? "selected" : ""}>${t}</option>`).join("")}</select></div>
    <div class="field"><label>法定代表人</label><input id="f-legal" value="${esc(c.legal_rep || "")}"></div>
    <div class="field"><label>联系电话</label><input id="f-phone" value="${esc(c.phone || "")}"></div>
    <div class="field"><label>邮箱</label><input id="f-email" value="${esc(c.email || "")}"></div>
    <div class="field"><label>注册资本(万元)</label><input id="f-reg" type="number" value="${c.reg_capital || 0}"></div>
    <div class="field"><label>成立日期</label><input id="f-founded" type="date" value="${c.founded_date || ""}"></div>
    <div class="field"><label>国标行业</label><input id="f-industry" value="${esc(c.industry || "")}"></div>
    <div class="field"><label>企业规模</label><select id="f-scale">${["大型", "中型", "小型"].map((t) => `<option ${c.scale === t ? "selected" : ""}>${t}</option>`).join("")}</select></div>
    <div class="field"><label>员工人数</label><input id="f-emp" type="number" value="${c.emp_count || 0}"></div>
    <div class="field"><label>学校持股比例(%)</label><input id="f-ratio" type="number" value="${c.holder_ratio || 0}"></div>
    <div class="field"><label>资产总额(万元)</label><input id="f-assets" type="number" value="${c.assets || 0}"></div>
    <div class="field"><label>年营收(万元)</label><input id="f-rev" type="number" value="${c.revenue || 0}"></div>
    <div class="field"><label>年利润(万元)</label><input id="f-profit" type="number" value="${c.profit || 0}"></div>
    <div class="field"><label>审计周期(年)</label><input id="f-cycle" type="number" value="${c.audit_cycle || 1}"></div>
    <div class="field full"><label>企业地址</label><input id="f-addr" value="${esc(c.address || "")}"></div>
    <div class="field full"><label>经营范围</label><textarea id="f-scope">${esc(c.biz_scope || "")}</textarea></div>
    <div class="field full"><label>知识产权数(扩展信息)</label><input id="f-ip" type="number" value="${(c.ext && c.ext.ip_count) || 0}"></div>
    <div class="field full"><label>荣誉/资质说明(扩展信息)</label><input id="f-honor" value="${esc((c.ext && c.ext.honors) || "")}"></div>
  </div>`;
}
function companyFormRead() {
  return {
    name: $("#f-name").value.trim(), credit_code: $("#f-credit").value.trim(), ctype: $("#f-ctype").value,
    legal_rep: $("#f-legal").value.trim(), phone: $("#f-phone").value.trim(), email: $("#f-email").value.trim(),
    reg_capital: +$("#f-reg").value || 0, founded_date: $("#f-founded").value || null, industry: $("#f-industry").value.trim(),
    scale: $("#f-scale").value, emp_count: +$("#f-emp").value || 0, holder_ratio: +$("#f-ratio").value || 0,
    assets: +$("#f-assets").value || 0, revenue: +$("#f-rev").value || 0, profit: +$("#f-profit").value || 0,
    audit_cycle: +$("#f-cycle").value || 1, address: $("#f-addr").value.trim(), biz_scope: $("#f-scope").value.trim(),
    ext: { ip_count: +$("#f-ip").value || 0, honors: $("#f-honor").value },
  };
}
window.openCompanyForm = async function (cid) {
  let c = {};
  if (cid) c = await api("/companies/" + cid);
  UI.openModal(cid ? "编辑企业信息" : "录入企业信息", companyFormHtml(c),
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button>
     <button class="btn primary" id="cf-save">保存${S.user.role === "company" ? "(提交待审核)" : ""}</button>`);
  $("#cf-save").onclick = async () => {
    const body = companyFormRead();
    if (!body.name) return toast("企业名称必填", "err");
    try {
      if (cid) {
        if (S.user.role === "company") await api(`/companies/${cid}/ext`, { method: "POST", body: { ext: body.ext } });
        else await api("/companies/" + cid, { method: "PUT", body });
      } else await api("/companies", { method: "POST", body });
      UI.closeModal(); toast("保存成功", "ok"); switchView("company");
    } catch (e) { toast(e.message, "err"); }
  };
};
window.reviewExt = function (cid) {
  UI.openModal("审核企业扩展信息", `<p>请确认该企业提交的扩展信息(知识产权/荣誉等)是否属实？</p>`,
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button>
     <button class="btn danger" id="rv-no">退回</button><button class="btn primary" id="rv-ok">通过</button>`);
  $("#rv-ok").onclick = async () => { await api(`/companies/${cid}/ext/review?approve=true`, { method: "POST" }); UI.closeModal(); toast("已通过", "ok"); switchView("company"); };
  $("#rv-no").onclick = async () => { await api(`/companies/${cid}/ext/review?approve=false`, { method: "POST" }); UI.closeModal(); toast("已退回", "ok"); switchView("company"); };
};

window.openCompanyDetail = async function (cid) {
  const c = await api("/companies/" + cid);
  const ext = c.ext || {};
  const tab = (key, label) => `<button data-tab="${key}" class="${key === "base" ? "active" : ""}">${label}</button>`;
  UI.openModal(`企业详情 - ${esc(c.name)}`, `
    <div class="sub-tabs" id="dt-tabs">${tab("base", "基本信息")}${tab("ext", "扩展信息")}${tab("equity", "股权结构")}${tab("doc", "文档资料")}${tab("cert", "证照信息")}</div>
    <div id="dt-body"></div>`,
    `<button class="btn ghost" onclick="UI.closeModal()">关闭</button>
     ${canManageCompany() || (S.user.role === "company" && S.user.company?.id === cid) ? `<button class="btn primary" onclick="UI.closeModal();openCompanyForm(${cid})">编辑</button>` : ""}`);
  const renderTab = (k) => {
    $$("#dt-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === k));
    let html = "";
    if (k === "base") {
      html = `<dl class="desc-list">
        <dt>统一信用代码</dt><dd>${esc(c.credit_code)}</dd><dt>企业类型</dt><dd>${TAG(c.ctype)}</dd>
        <dt>法定代表人</dt><dd>${esc(c.legal_rep)}</dd><dt>联系电话</dt><dd>${esc(c.phone)}</dd>
        <dt>注册资本</dt><dd>${money(c.reg_capital)} 万元</dd><dt>成立日期</dt><dd>${esc(c.founded_date)}</dd>
        <dt>国标行业</dt><dd>${esc(c.industry)}</dd><dt>企业规模</dt><dd>${esc(c.scale)}</dd>
        <dt>员工人数</dt><dd>${c.emp_count}</dd><dt>学校持股</dt><dd>${c.holder_ratio}%</dd>
        <dt>资产总额</dt><dd>${money(c.assets)} 万元</dd><dt>年营收</dt><dd>${money(c.revenue)} 万元</dd>
        <dt>年利润</dt><dd>${money(c.profit)} 万元</dd><dt>审计周期</dt><dd>${c.audit_cycle} 年</dd>
        <dt>上次审计</dt><dd>${esc(c.last_audit_date)} ${c.audit_overdue ? '<span class="tag red">逾期</span>' : ""}</dd>
        <dt>状态</dt><dd>${TAG(c.status)}</dd>
        <dt>企业地址</dt><dd class="full">${esc(c.address)}</dd>
        <dt>经营范围</dt><dd class="full">${esc(c.biz_scope)}</dd></dl>`;
    } else if (k === "ext") {
      html = `<dl class="desc-list">
        <dt>知识产权</dt><dd>${ext.ip_count ?? 0} 项</dd><dt>科研项目</dt><dd>${ext.projects ?? 0} 项</dd>
        <dt>荣誉证书</dt><dd>${esc(ext.honors ?? ext.honor ?? "-")}</dd><dt>研发投入</dt><dd>${ext.rd_invest ?? "-"} 万元</dd>
        <dt>信息状态</dt><dd>${TAG(ext.ext_status || "已审核")}</dd></dl>
        ${(S.user.role === "company" && S.user.company?.id === cid) ? `<div style="margin-top:12px"><button class="btn primary sm" onclick="openCompanyForm(${cid})">编辑扩展信息(提交审核)</button></div>` : ""}`;
    } else if (k === "equity") {
      html = `<table class="tbl"><tr><th>股东</th><th>持股比例</th><th>出资方式</th><th>出资时间</th></tr>` +
        c.equity.map((e) => `<tr><td>${esc(e.shareholder)}</td><td>${e.ratio}%</td><td>${esc(e.method)}</td><td>${esc(e.invest_time)}</td></tr>`).join("") + "</table>" +
        (canManageCompany() ? `<div style="margin-top:10px"><button class="btn primary sm" onclick="addEquity(${cid})">+ 登记股权变动</button></div>` : "");
    } else if (k === "doc") {
      html = `<table class="tbl"><tr><th>文档名</th><th>分类</th><th>上传人</th><th>时间</th><th>操作</th></tr>` +
        (c.documents.map((d) => `<tr><td>${esc(d.name)}</td><td>${esc(d.category)}</td><td>${esc(d.uploaded_by)}</td><td>${esc(d.created_at)}</td>
          <td class="ops"><a href="/api/companies/${cid}/documents/${d.id}/download?token=${S.token}" target="_blank">下载</a>
          ${canManageCompany() || S.user.role === "company" ? ` · <a onclick="delDoc(${cid},${d.id})">删除</a>` : ""}</td></tr>`).join("") || '<tr><td colspan="5" class="empty">暂无文档</td></tr>') + "</table>" +
        `<div style="margin-top:10px;display:flex;gap:8px;align-items:center">
          <input id="doc-name" placeholder="文档名称" style="flex:1;border:1px solid var(--border);border-radius:6px;padding:7px 10px">
          <select id="doc-cat"><option>营业执照</option><option>公司章程</option><option>审计报告</option><option>合同协议</option><option>其他</option></select>
          <input type="file" id="doc-file" style="font-size:12px">
          <button class="btn primary sm" onclick="uploadDoc(${cid})">上传</button></div>`;
    } else if (k === "cert") {
      html = `<table class="tbl"><tr><th>证照名称</th><th>证号</th><th>到期日</th><th>状态</th></tr>` +
        c.certificates.map((d) => `<tr><td>${esc(d.cert_name)}</td><td>${esc(d.cert_no)}</td><td>${esc(d.expire_date)}</td><td>${TAG(d.status)}</td></tr>`).join("") + "</table>" +
        (canManageCompany() ? `<div style="margin-top:10px"><button class="btn primary sm" onclick="addCert(${cid})">+ 登记证照</button></div>` : "");
    }
    $("#dt-body").innerHTML = html;
  };
  $$("#dt-tabs button").forEach((b) => b.onclick = () => renderTab(b.dataset.tab));
  renderTab("base");
};
window.addEquity = function (cid) {
  UI.openModal("登记股权变动", `<div class="form-grid">
    <div class="field full"><label>股东名称</label><input id="eq-name"></div>
    <div class="field"><label>持股比例(%)</label><input id="eq-ratio" type="number"></div>
    <div class="field"><label>出资方式</label><select id="eq-method"><option>货币出资</option><option>实物出资</option><option>技术入股</option><option>股权转让</option></select></div>
    <div class="field"><label>出资时间</label><input id="eq-time" type="date"></div>
    <div class="field full"><label>备注</label><input id="eq-remark"></div></div>`,
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="eq-save">保存</button>`);
  $("#eq-save").onclick = async () => {
    await api(`/companies/${cid}/equity`, { method: "POST", body: {
      shareholder: $("#eq-name").value.trim(), ratio: +$("#eq-ratio").value || 0,
      method: $("#eq-method").value, invest_time: $("#eq-time").value || null, remark: $("#eq-remark").value } });
    UI.closeModal(); toast("已登记", "ok"); openCompanyDetail(cid);
  };
};
window.uploadDoc = async function (cid) {
  const f = $("#doc-file").files[0];
  if (!f) return toast("请选择文件", "err");
  const fd = new FormData();
  fd.append("file", f); fd.append("name", $("#doc-name").value.trim() || f.name); fd.append("category", $("#doc-cat").value);
  const res = await fetch(`/api/companies/${cid}/documents`, { method: "POST", headers: { Authorization: "Bearer " + S.token }, body: fd });
  if (!res.ok) { const d = await res.json().catch(() => ({})); return toast(d.detail || "上传失败", "err"); }
  toast("上传成功", "ok"); openCompanyDetail(cid);
};
window.delDoc = function (cid, did) {
  UI.confirm("确认删除该文档？", async () => { await api(`/companies/${cid}/documents/${did}`, { method: "DELETE" }); toast("已删除", "ok"); openCompanyDetail(cid); });
};
window.addCert = function (cid) {
  UI.openModal("登记证照", `<div class="form-grid">
    <div class="field"><label>证照名称</label><input id="ct-name"></div>
    <div class="field"><label>证号</label><input id="ct-no"></div>
    <div class="field full"><label>到期日期</label><input id="ct-exp" type="date"></div></div>`,
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="ct-save">保存</button>`);
  $("#ct-save").onclick = async () => {
    await api(`/companies/${cid}/certificates`, { method: "POST", body: {
      cert_name: $("#ct-name").value.trim(), cert_no: $("#ct-no").value.trim(), expire_date: $("#ct-exp").value } });
    UI.closeModal(); toast("已登记", "ok"); openCompanyDetail(cid);
  };
};

/* ================= 视图: 企业规范提醒 ================= */
function viewRemind(root) {
  root.innerHTML = `
  <div class="page-head"><div><h2>企业规范提醒</h2><div class="sub">法规政策 / 制度执行 / 证照到期 / 审计提醒 / 风险提示</div></div></div>
  <div class="tabs" id="rm-tabs">
    <div class="tab active" data-t="policy">法规政策提醒</div><div class="tab" data-t="rule">制度执行提醒</div>
    <div class="tab" data-t="cert">资质证照到期</div><div class="tab" data-t="audit">企业审计提醒</div>
    <div class="tab" data-t="risk">风险提示</div>
  </div><div id="rm-body"></div>`;
  const mgr = canManageCompany();
  const tabs = {
    policy: async () => {
      const rows = await api("/reminders/policies");
      $("#rm-body").innerHTML = `<div class="card">
        ${mgr ? `<div class="toolbar"><button class="btn primary sm" id="pl-add">+ 发布法规政策</button></div>` : ""}
        <table class="tbl"><tr><th>标题</th><th>分类</th><th>来源</th><th>发布日期</th><th>内容</th></tr>
        ${rows.map((p) => `<tr><td><b>${esc(p.title)}</b></td><td>${TAG(p.category) || "gray"}</td><td>${esc(p.source)}</td><td>${esc(p.publish_date)}</td>
          <td class="muted" style="max-width:340px">${esc((p.content || "").slice(0, 40))}…</td></tr>`).join("")}</table></div>`;
      if (mgr) $("#pl-add").onclick = () => {
        UI.openModal("发布法规政策", `<div class="form-grid">
          <div class="field full"><label>标题</label><input id="pl-title"></div>
          <div class="field"><label>分类</label><select id="pl-cat"><option>国家政策</option><option>资产管理</option><option>税收政策</option><option>行业监管</option><option>审计监督</option></select></div>
          <div class="field"><label>来源</label><input id="pl-src"></div>
          <div class="field full"><label>内容摘要</label><textarea id="pl-content"></textarea></div></div>`,
          `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="pl-save">发布</button>`);
        $("#pl-save").onclick = async () => {
          await api("/reminders/policies", { method: "POST", body: {
            title: $("#pl-title").value.trim(), category: $("#pl-cat").value,
            source: $("#pl-src").value.trim(), content: $("#pl-content").value.trim() } });
          UI.closeModal(); toast("已发布并推送站内消息", "ok"); tabs.policy();
        };
      };
    },
    rule: async () => {
      const rows = await api("/reminders/rules");
      $("#rm-body").innerHTML = `<div class="card">
        ${mgr ? `<div class="toolbar"><button class="btn primary sm" id="ru-add">+ 新增制度提醒</button></div>` : ""}
        <table class="tbl"><tr><th>提醒事项</th><th>说明</th><th>提醒时间</th><th>对象</th><th>状态</th><th>操作</th></tr>
        ${rows.map((r) => `<tr><td><b>${esc(r.title)}</b></td><td class="muted">${esc(r.content)}</td><td>${esc(r.remind_date)}</td><td>${esc(r.target)}</td><td>${TAG(r.status)}</td>
          <td class="ops">${mgr && r.status === "待处理" ? `<a onclick="ruleDone(${r.id})">标记完成</a>` : ""}</td></tr>`).join("")}</table></div>`;
      if (mgr) $("#ru-add").onclick = () => {
        UI.openModal("新增制度提醒", `<div class="form-grid">
          <div class="field full"><label>提醒事项</label><input id="ru-title"></div>
          <div class="field full"><label>说明</label><textarea id="ru-content"></textarea></div>
          <div class="field"><label>提醒日期</label><input id="ru-date" type="date"></div>
          <div class="field"><label>提醒对象</label><input id="ru-target" value="全部企业"></div></div>`,
          `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="ru-save">保存</button>`);
        $("#ru-save").onclick = async () => {
          await api("/reminders/rules", { method: "POST", body: {
            title: $("#ru-title").value.trim(), content: $("#ru-content").value.trim(),
            remind_date: $("#ru-date").value, target: $("#ru-target").value.trim() } });
          UI.closeModal(); toast("已新增", "ok"); tabs.rule();
        };
      };
    },
    cert: async () => {
      const rows = await api("/reminders/certificates");
      $("#rm-body").innerHTML = `<div class="card"><h3>临期/过期证照 (自动监控，到期前3个月预警)</h3>
        <table class="tbl"><tr><th>企业</th><th>证照</th><th>证号</th><th>到期日</th><th>状态</th></tr>
        ${rows.map((r) => `<tr><td>${esc(r.company_name)}</td><td>${esc(r.cert_name)}</td><td>${esc(r.cert_no)}</td><td>${esc(r.expire_date)}</td><td>${TAG(r.status)}</td></tr>`).join("") || '<tr><td colspan="5" class="empty">全部证照状态正常 ✓</td></tr>'}</table></div>`;
    },
    audit: async () => {
      const rows = await api("/reminders/audit-overdue");
      $("#rm-body").innerHTML = `<div class="card"><h3>企业审计提醒 (系统每周自动遍历，到期前30天预警)</h3>
        <table class="tbl"><tr><th>企业</th><th>审计周期</th><th>上次审计</th><th>应审日期</th><th>状态</th><th>操作</th></tr>
        ${rows.map((r) => `<tr><td>${esc(r.name)}</td><td>${r.audit_cycle}年</td><td>${esc(r.last_audit_date || "未审计")}</td><td>${esc(r.due_date)}</td>
          <td>${r.overdue_days >= 0 ? '<span class="tag red">逾期</span>' : '<span class="tag orange">临近</span>'}</td>
          <td class="ops">${mgr || ["supervisor", "chairman"].includes(S.user.role) ? `<a onclick="auditDone(${r.id},'${esc(r.name)}')">登记已完成审计</a>` : ""}</td></tr>`).join("") || '<tr><td colspan="6" class="empty">无到期审计任务 ✓</td></tr>'}</table></div>`;
    },
    risk: async () => {
      const rows = await api("/reminders/risks");
      $("#rm-body").innerHTML = `<div class="card"><h3>经营风险监控 (工商异常/法律纠纷/行政处罚)</h3>
        <table class="tbl"><tr><th>企业</th><th>风险类型</th><th>等级</th><th>内容</th><th>状态</th><th>操作</th></tr>
        ${rows.map((r) => `<tr><td>${esc(r.company_name)}</td><td>${esc(r.rtype)}</td><td>${TAG(r.level)}</td><td class="muted">${esc(r.content)}</td><td>${TAG(r.status)}</td>
          <td class="ops">${r.status === "未处理" && ["admin", "secretary", "supervisor", "chairman"].includes(S.user.role) ? `<a onclick="riskDone(${r.id})">标记处理</a>` : ""}</td></tr>`).join("") || '<tr><td colspan="6" class="empty">暂无风险记录 ✓</td></tr>'}</table></div>`;
    },
  };
  $$("#rm-tabs .tab").forEach((t) => t.onclick = () => {
    $$("#rm-tabs .tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active"); tabs[t.dataset.t]();
  });
  tabs.policy();
}
window.ruleDone = async (id) => { await api(`/reminders/rules/${id}/done`, { method: "PUT" }); toast("已完成", "ok"); switchView("remind"); };
window.auditDone = (cid, name) => UI.confirm(`确认登记「${name}」已完成本次审计？`, async () => {
  await api(`/reminders/audit/${cid}/record`, { method: "POST" }); toast("已登记", "ok"); switchView("remind"); });
window.riskDone = async (id) => { await api(`/reminders/risks/${id}/handle`, { method: "PUT" }); toast("已处理", "ok"); switchView("remind"); };

/* ================= 视图: 业务审批 ================= */
function viewApproval(root) {
  root.innerHTML = `
  <div class="page-head"><div><h2>业务审批</h2><div class="sub">设备采购 / 出差 / 报销 / 用印 / 合同 · 金额超5万元需董事长终审</div></div>
    <button class="btn primary" id="ap-new">+ 发起申请</button></div>
  <div class="tabs" id="ap-tabs"><div class="tab active" data-t="mine">我的申请</div><div class="tab" data-t="todo">待我审批</div></div>
  <div id="ap-body"></div>`;
  const tabs = {
    mine: async () => {
      const d = await api("/approvals");
      $("#ap-body").innerHTML = `<div class="card"><table class="tbl">
        <tr><th>类型</th><th>标题</th><th>金额(元)</th><th>当前节点</th><th>状态</th><th>申请时间</th><th>操作</th></tr>
        ${d.mine.map((a) => `<tr><td>${TAG(a.atype) || esc(a.atype)}</td><td>${esc(a.title)}</td><td>${money(a.amount)}</td>
          <td>${esc(a.current_node)}</td><td>${TAG(a.status) || '<span class="tag orange">' + esc(a.status) + "</span>"}</td><td>${esc(a.created_at)}</td>
          <td class="ops"><a onclick="apprDetail(${a.id})">查看</a></td></tr>`).join("") || '<tr><td colspan="7" class="empty">暂无申请记录</td></tr>'}</table></div>`;
    },
    todo: async () => {
      const d = await api("/approvals");
      $("#ap-body").innerHTML = `<div class="card"><table class="tbl">
        <tr><th>类型</th><th>标题</th><th>申请人</th><th>金额(元)</th><th>状态</th><th>操作</th></tr>
        ${d.todo.map((a) => `<tr><td>${esc(a.atype)}</td><td>${esc(a.title)}</td><td>${esc(a.applicant)}</td><td>${money(a.amount)}</td><td>${TAG(a.status) || '<span class="tag orange">' + esc(a.status) + "</span>"}</td>
          <td class="ops"><a onclick="apprDetail(${a.id})">查看</a> · <a onclick="apprAct(${a.id},'通过')">通过</a> · <a style="color:var(--danger)" onclick="apprAct(${a.id},'驳回')">驳回</a></td></tr>`).join("") || '<tr><td colspan="6" class="empty">暂无待审批事项 ✓</td></tr>'}</table></div>`;
    },
  };
  $$("#ap-tabs .tab").forEach((t) => t.onclick = () => {
    $$("#ap-tabs .tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active"); tabs[t.dataset.t]();
  });
  $("#ap-new").onclick = async () => {
    const cos = await api("/companies/all");
    UI.openModal("发起业务申请", `<div class="form-grid">
      <div class="field"><label>申请类型</label><select id="na-type"><option>设备采购</option><option>出差申请</option><option>费用报销</option><option>用印申请</option><option>合同审批</option></select></div>
      <div class="field"><label>关联企业(选填)</label><select id="na-company"><option value="">不关联</option>${cos.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select></div>
      <div class="field full"><label>标题 *</label><input id="na-title"></div>
      <div class="field full"><label>金额(元，超5万元走董事长终审)</label><input id="na-amount" type="number" value="0"></div>
      <div class="field full"><label>事由说明</label><textarea id="na-reason"></textarea></div></div>`,
      `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="na-save">提交</button>`);
    $("#na-save").onclick = async () => {
      try {
        const r = await api("/approvals", { method: "POST", body: {
          atype: $("#na-type").value, title: $("#na-title").value.trim(), reason: $("#na-reason").value.trim(),
          amount: +$("#na-amount").value || 0, company_id: $("#na-company").value ? +$("#na-company").value : null } });
        UI.closeModal(); toast(`已提交(${r.status})`, "ok"); tabs.mine(); refreshMsgBadge();
      } catch (e) { toast(e.message, "err"); }
    };
  };
  tabs.mine();
}
window.apprDetail = async function (id) {
  const a = await api("/approvals/" + id);
  UI.openModal(`审批单 #${a.id} - ${esc(a.atype)}`, `
    <dl class="desc-list">
      <dt>标题</dt><dd class="full">${esc(a.title)}</dd>
      <dt>申请人</dt><dd>${esc(a.applicant)}</dd><dt>关联企业</dt><dd>${esc(a.company_name || "无")}</dd>
      <dt>金额</dt><dd>${money(a.amount)} 元 ${a.amount > 50000 ? '<span class="tag red">超5万需董事长终审</span>' : ""}</dd>
      <dt>状态</dt><dd>${TAG(a.status) || '<span class="tag orange">' + esc(a.status) + "</span>"}</dd>
      <dt>事由</dt><dd class="full">${esc(a.reason)}</dd></dl>
    <h3 style="margin:16px 0 10px;font-size:14px">审批记录</h3>
    ${a.logs.map((l) => `<div style="padding:7px 0;border-bottom:1px dashed var(--border);font-size:13px">
      <b>${esc(l.approver)}</b>(${esc(l.approver_role)}) ${TAG(l.action) || esc(l.action)} <span class="muted">${esc(l.created_at)}</span>
      <div class="muted">${esc(l.comment)}</div></div>`).join("") || '<div class="empty">暂无记录</div>'}`,
    `<button class="btn ghost" onclick="UI.closeModal()">关闭</button>`);
};
window.apprAct = function (id, act) {
  UI.openModal(`审批操作 - ${act}`, `<div class="field"><label>审批意见</label><textarea id="ac-comment" placeholder="请输入审批意见"></textarea></div>`,
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn ${act === "通过" ? "primary" : "danger"}" id="ac-ok">确定${act}</button>`);
  $("#ac-ok").onclick = async () => {
    try { await api(`/approvals/${id}/action?act=${encodeURIComponent(act)}&comment=${encodeURIComponent($("#ac-comment").value.trim())}`, { method: "POST" });
      UI.closeModal(); toast(`已${act}`, "ok"); switchView("approval"); }
    catch (e) { toast(e.message, "err"); }
  };
};

/* ================= 视图: 企业目标考核 ================= */
function viewAssessment(root) {
  root.innerHTML = `
  <div class="page-head"><div><h2>企业目标考核</h2><div class="sub">指标设定 / 过程监控 / 考核评价</div></div></div>
  <div class="tabs" id="as-tabs">
    <div class="tab active" data-t="kpi">指标设定与过程监控</div><div class="tab" data-t="eval">考核评价</div>
  </div><div id="as-body"></div>`;
  const mgr = ["admin", "supervisor", "chairman"].includes(S.user.role);
  const tabs = {
    kpi: async () => {
      const cos = await api("/companies/all");
      const cid = S.user.role === "company" ? S.user.company?.id : $("#as-co").value || 0;
      const rows = await api(`/assessment/indicators?company_id=${cid}&year=2026`);
      $("#as-body").innerHTML = `<div class="card">
        <div class="toolbar">
          ${S.user.role === "company" ? "" : `<select id="as-co"><option value="">全部企业</option>${cos.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select>`}
          ${mgr ? '<button class="btn primary sm" id="kpi-add">+ 设定指标</button>' : ""}
        </div>
        ${rows.map((k) => `<div style="padding:12px 0;border-bottom:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
            <div><b>${esc(k.company_name)}</b> · ${esc(k.name)}
              <span class="tag ${k.category === "财务指标" ? "blue" : "gray"}">${esc(k.category)}</span>
              <span class="muted">权重 ${k.weight}%</span></div>
            <div class="muted">目标 ${money(k.target)}${esc(k.unit)} · 累计 ${money(k.accumulated)}${esc(k.unit)}</div>
          </div>
          <div style="display:flex;align-items:center;gap:10px;margin-top:8px">
            <div class="progress-bar" style="flex:1"><i style="width:${Math.min(k.progress, 100)}%"></i></div>
            <span class="muted" style="min-width:44px">${k.progress}%</span>
            ${["admin", "supervisor", "secretary"].includes(S.user.role) ? `<a onclick="kpiRecord(${k.id},'${esc(k.name)}')">录入进度</a>` : ""}
          </div>
          <div class="muted" style="margin-top:4px">过程记录：${k.records.map((r) => `${r.period} ${money(r.value)}${esc(k.unit)}(${r.progress}%)`).join(" · ") || "暂无"}</div>
        </div>`).join("") || '<div class="empty">暂无考核指标</div>'}
      </div>`;
      const co = $("#as-co");
      if (co) co.onchange = tabs.kpi;
      if (mgr) $("#kpi-add").onclick = () => {
        UI.openModal("设定考核指标(2026年度)", `<div class="form-grid">
          <div class="field full"><label>企业</label><select id="ki-co">${cos.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select></div>
          <div class="field"><label>指标名称</label><input id="ki-name"></div>
          <div class="field"><label>类别</label><select id="ki-cat"><option>财务指标</option><option>非财务指标</option></select></div>
          <div class="field"><label>目标值</label><input id="ki-target" type="number"></div>
          <div class="field"><label>单位</label><input id="ki-unit" placeholder="万元/%/项"></div>
          <div class="field"><label>权重(%)</label><input id="ki-weight" type="number" value="10"></div>
          <div class="field"><label>考核标准</label><input id="ki-std" value="按季度分解目标值"></div></div>`,
          `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="ki-save">保存</button>`);
        $("#ki-save").onclick = async () => {
          await api("/assessment/indicators", { method: "POST", body: {
            company_id: +$("#ki-co").value, year: 2026, name: $("#ki-name").value.trim(), category: $("#ki-cat").value,
            target: +$("#ki-target").value || 0, unit: $("#ki-unit").value.trim(), weight: +$("#ki-weight").value || 0,
            standard: $("#ki-std").value.trim() } });
          UI.closeModal(); toast("已设定", "ok"); tabs.kpi();
        };
      };
    },
    eval: async () => {
      const rows = await api("/assessment/evaluations?year=2025");
      $("#as-body").innerHTML = `<div class="card">
        ${mgr ? `<div class="toolbar"><button class="btn primary sm" id="ev-add">+ 新增考核评价</button></div>` : ""}
        <table class="tbl"><tr><th>企业</th><th>年度</th><th>总分</th><th>评级</th><th>评价意见</th><th>评价人</th></tr>
        ${rows.map((e) => `<tr><td>${esc(e.company_name)}</td><td>${e.year}</td><td><b>${e.total_score}</b></td>
          <td>${e.grade === "优秀" ? TAG("已通过").replace("已通过", "优秀") : `<span class="tag ${e.grade === "优秀" ? "green" : "blue"}">${esc(e.grade)}</span>`}</td>
          <td class="muted">${esc(e.comment)}</td><td>${esc(e.evaluator)}</td></tr>`).join("") || '<tr><td colspan="6" class="empty">暂无评价记录</td></tr>'}</table></div>`;
      if (mgr) $("#ev-add").onclick = async () => {
        const cos = await api("/companies/all");
        UI.openModal("新增考核评价", `<div class="form-grid">
          <div class="field full"><label>企业</label><select id="ev-co">${cos.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select></div>
          <div class="field"><label>年度</label><input id="ev-year" type="number" value="2026"></div>
          <div class="field"><label>总分</label><input id="ev-score" type="number" max="100"></div>
          <div class="field"><label>评级</label><select id="ev-grade"><option>优秀</option><option>良好</option><option>合格</option><option>不合格</option></select></div>
          <div class="field full"><label>评价意见</label><textarea id="ev-comment"></textarea></div></div>`,
          `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="ev-save">保存</button>`);
        $("#ev-save").onclick = async () => {
          await api("/assessment/evaluations", { method: "POST", body: {
            company_id: +$("#ev-co").value, year: +$("#ev-year").value || 2026, total_score: +$("#ev-score").value || 0,
            grade: $("#ev-grade").value, comment: $("#ev-comment").value.trim() } });
          UI.closeModal(); toast("已保存(结果将关联绩效)", "ok"); tabs.eval();
        };
      };
    },
  };
  $$("#as-tabs .tab").forEach((t) => t.onclick = () => {
    $$("#as-tabs .tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active"); tabs[t.dataset.t]();
  });
  tabs.kpi();
}
window.kpiRecord = function (kid, name) {
  UI.openModal(`录入过程数据 - ${name}`, `<div class="form-grid">
    <div class="field"><label>考核期</label><select id="kr-period"><option>Q1</option><option>Q2</option><option>Q3</option><option>Q4</option><option>月度</option></select></div>
    <div class="field"><label>完成值</label><input id="kr-value" type="number"></div>
    <div class="field full"><label>说明</label><input id="kr-comment"></div></div>`,
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="kr-save">保存</button>`);
  $("#kr-save").onclick = async () => {
    await api(`/assessment/indicators/${kid}/records`, { method: "POST", body: {
      period: $("#kr-period").value, value: +$("#kr-value").value || 0, comment: $("#kr-comment").value.trim() } });
    UI.closeModal(); toast("已录入", "ok"); switchView("assessment");
  };
};

/* ================= 视图: 成果转化 ================= */
function viewTransfer(root) {
  root.innerHTML = `
  <div class="page-head"><div><h2>成果转化</h2><div class="sub">科研成果登记发布 / 校企对接合作 / 转化过程跟踪</div></div>
    <button class="btn primary" id="tr-add">+ 登记成果</button></div>
  <div class="tabs" id="tr-tabs">
    <div class="tab active" data-t="ach">成果库</div><div class="tab" data-t="coop">合作对接</div>
  </div><div id="tr-body"></div>`;
  const mgr = ["admin", "secretary", "chairman"].includes(S.user.role);
  const tabs = {
    ach: async () => {
      const rows = await api("/transfer/achievements");
      $("#tr-body").innerHTML = `<div class="grid-2">` + rows.map((a) => `<div class="card">
        <div style="display:flex;justify-content:space-between;margin-bottom:8px">
          <h3 style="margin:0">${esc(a.name)}</h3>${TAG(a.status)}</div>
        <div class="muted" style="margin-bottom:8px">所属领域：${esc(a.field)} · 持有方：${esc(a.owner)}</div>
        <div style="font-size:13px;line-height:1.8">
          <div><b>技术特点：</b>${esc(a.features)}</div>
          <div><b>创新点：</b>${esc(a.innovation)}</div>
          <div><b>应用前景：</b>${esc(a.prospect)}</div></div>
        <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap">
          ${(a.status === "已发布" && (S.user.role !== "company" || a.company_id !== S.user.company?.id)) ? `<button class="btn primary sm" onclick="applyCoop(${a.id},'${esc(a.name)}')">申请合作对接</button>` : ""}
          ${mgr && a.status === "待审核" ? `<button class="btn primary sm" onclick="achReview(${a.id},true)">审核发布</button><button class="btn ghost sm" onclick="achReview(${a.id},false)">退回</button>` : ""}
        </div></div>`).join("") + "</div>";
    },
    coop: async () => {
      const rows = await api("/transfer/cooperations");
      $("#tr-body").innerHTML = `<div class="card"><table class="tbl">
        <tr><th>成果</th><th>申请方</th><th>合作意向</th><th>协议</th><th>状态</th><th>转化进度</th><th>操作</th></tr>
        ${rows.map((c) => `<tr><td>${esc(c.ach_name)}</td><td>${esc(c.company_name || c.applicant)}</td><td class="muted">${esc((c.intent || "").slice(0, 24))}</td>
          <td class="muted">${esc((c.agreement || "-").slice(0, 20))}</td><td>${TAG(c.status)}</td>
          <td class="muted" style="max-width:220px">${esc(c.tracks || "暂无记录")}</td>
          <td class="ops">
            ${mgr || S.user.role === "supervisor" ? `<a onclick="coopStatus(${c.id},'${esc(c.status)}')">更新状态</a> · <a onclick="addTrack(${c.id})">进度跟踪</a>` : "—"}</td></tr>`).join("") || '<tr><td colspan="7" class="empty">暂无合作记录</td></tr>'}</table></div>`;
    },
  };
  $$("#tr-tabs .tab").forEach((t) => t.onclick = () => {
    $$("#tr-tabs .tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active"); tabs[t.dataset.t]();
  });
  $("#tr-add").onclick = () => {
    UI.openModal("登记科研成果", `<div class="form-grid">
      <div class="field full"><label>成果名称 *</label><input id="ac-name"></div>
      <div class="field"><label>所属领域</label><input id="ac-field"></div>
      <div class="field"><label>持有团队/人</label><input id="ac-owner"></div>
      <div class="field full"><label>技术特点</label><textarea id="ac-feat"></textarea></div>
      <div class="field full"><label>创新点</label><textarea id="ac-innov"></textarea></div>
      <div class="field full"><label>应用前景</label><textarea id="ac-prosp"></textarea></div></div>`,
      `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="ac-save">提交(待审核)</button>`);
    $("#ac-save").onclick = async () => {
      await api("/transfer/achievements", { method: "POST", body: {
        name: $("#ac-name").value.trim(), field: $("#ac-field").value.trim(), owner: $("#ac-owner").value.trim(),
        features: $("#ac-feat").value.trim(), innovation: $("#ac-innov").value.trim(), prospect: $("#ac-prosp").value.trim() } });
      UI.closeModal(); toast("已提交登记", "ok"); tabs.ach();
    };
  };
  tabs.ach();
}
window.achReview = async (id, ok) => { await api(`/transfer/achievements/${id}/review?approve=${ok}`, { method: "POST" }); toast(ok ? "已发布" : "已退回", "ok"); switchView("transfer"); };
window.applyCoop = function (aid, name) {
  UI.openModal(`申请合作 - ${name}`, `<div class="field full"><label>合作意向说明</label><textarea id="cp-intent" placeholder="说明希望如何开展合作、拟投入资源等"></textarea></div>`,
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="cp-ok">提交意向</button>`);
  $("#cp-ok").onclick = async () => {
    await api("/transfer/cooperations", { method: "POST", body: { achievement_id: aid, intent: $("#cp-intent").value.trim() } });
    UI.closeModal(); toast("已提交意向，等待对接", "ok"); switchView("transfer");
  };
};
window.coopStatus = function (cid, cur) {
  UI.openModal("更新合作状态", `<div class="form-grid">
    <div class="field"><label>当前状态</label><input value="${cur}" disabled></div>
    <div class="field"><label>新状态</label><select id="cs-status"><option>意向沟通</option><option>洽谈中</option><option>已签约</option><option>已完成</option></select></div>
    <div class="field full"><label>协议说明(签约时填写)</label><input id="cs-agr"></div></div>`,
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="cs-ok">更新</button>`);
  $("#cs-ok").onclick = async () => {
    await api(`/transfer/cooperations/${cid}/status?status=${encodeURIComponent($("#cs-status").value)}&agreement=${encodeURIComponent($("#cs-agr").value.trim())}`, { method: "PUT" });
    UI.closeModal(); toast("已更新", "ok"); switchView("transfer");
  };
};
window.addTrack = function (cid) {
  UI.openModal("录入转化进度", `<div class="form-grid">
    <div class="field"><label>当前阶段</label><input id="tk-stage" placeholder="技术开发/中试验证/产业化"></div>
    <div class="field"><label>资金使用(万元)</label><input id="tk-fund" type="number"></div>
    <div class="field full"><label>进度说明</label><textarea id="tk-prog"></textarea></div>
    <div class="field full"><label>存在问题</label><input id="tk-prob"></div></div>`,
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="tk-ok">保存</button>`);
  $("#tk-ok").onclick = async () => {
    await api(`/transfer/cooperations/${cid}/tracks`, { method: "POST", body: {
      stage: $("#tk-stage").value.trim(), progress: $("#tk-prog").value.trim(),
      fund_used: +$("#tk-fund").value || 0, problems: $("#tk-prob").value.trim() } });
    UI.closeModal(); toast("已录入", "ok"); switchView("transfer");
  };
};

/* ================= 视图: 平台管理 ================= */
function viewPlatform(root) {
  root.innerHTML = `
  <div class="page-head"><div><h2>平台管理</h2><div class="sub">用户 / 菜单 / 授权 / 审计 / 交接 / 消息</div></div></div>
  <div class="tabs" id="pf-tabs">
    <div class="tab active" data-t="user">用户身份管理</div><div class="tab" data-t="menu">菜单管理</div>
    <div class="tab" data-t="auth">授权管理</div><div class="tab" data-t="audit">安全审计</div>
    <div class="tab" data-t="hand">工作交接</div><div class="tab" data-t="msg">消息提醒</div>
  </div><div id="pf-body"></div>`;
  const tabs = {
    user: async () => {
      const [rows, roles] = await Promise.all([api("/auth/users"), api("/auth/roles")]);
      $("#pf-body").innerHTML = `<div class="card">
        <div class="toolbar"><button class="btn primary sm" id="us-add">+ 添加用户</button>
          <span class="muted">内部员工由管理员添加并分配角色；企业用户由管理员/秘书通过企业录入自动生成。</span></div>
        <table class="tbl"><tr><th>用户名</th><th>姓名</th><th>角色</th><th>部门</th><th>关联企业</th><th>状态</th><th>操作</th></tr>
        ${rows.map((u) => `<tr><td>${esc(u.username)}</td><td>${esc(u.name)}</td><td>${TAG(u.role_name) || esc(u.role_name)}</td><td>${esc(u.dept)}</td><td>${esc(u.company_name || "-")}</td>
          <td>${u.status ? '<span class="tag green">启用</span>' : '<span class="tag gray">停用</span>'}</td>
          <td class="ops"><a onclick="userEdit(${u.id})">编辑</a> · <a onclick="userReset(${u.id},'${esc(u.username)}')">重置密码</a>
            · <a style="color:var(--danger)" onclick="userDel(${u.id},'${esc(u.username)}')">删除</a></td></tr>`).join("")}</table></div>`;
      $("#us-add").onclick = () => {
        UI.openModal("添加用户", `<div class="form-grid">
          <div class="field"><label>用户名 *</label><input id="nu-username"></div>
          <div class="field"><label>初始密码 *</label><input id="nu-pwd" value="hw@12345"></div>
          <div class="field"><label>姓名 *</label><input id="nu-name"></div>
          <div class="field"><label>角色</label><select id="nu-role">${roles.map((r) => `<option value="${r.key}">${r.name}</option>`).join("")}</select></div>
          <div class="field"><label>部门</label><input id="nu-dept"></div>
          <div class="field"><label>手机号</label><input id="nu-phone"></div>
          <div class="field full"><label>邮箱</label><input id="nu-email"></div></div>
          <p class="muted" style="margin-top:8px">选择"企业用户"角色时需在编辑中关联企业；首次登录须修改初始密码。</p>`,
          `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="nu-save">保存</button>`);
        $("#nu-save").onclick = async () => {
          try {
            await api("/auth/users", { method: "POST", body: {
              username: $("#nu-username").value.trim(), password: $("#nu-pwd").value, name: $("#nu-name").value.trim(),
              role: $("#nu-role").value, dept: $("#nu-dept").value.trim(), phone: $("#nu-phone").value.trim(), email: $("#nu-email").value.trim() } });
            UI.closeModal(); toast("已添加", "ok"); tabs.user();
          } catch (e) { toast(e.message, "err"); }
        };
      };
    },
    menu: async () => {
      const rows = await api("/platform/menus/all");
      $("#pf-body").innerHTML = `<div class="card"><h3>菜单管理 (布局可在顶栏切换横/竖版，主题色可切换)</h3>
        <table class="tbl"><tr><th>菜单</th><th>标识</th><th>排序</th><th>可见</th><th>操作</th></tr>
        ${rows.map((m) => `<tr><td>${esc(m.name)}</td><td class="muted">${esc(m.key)}</td><td>${m.sort}</td>
          <td>${m.visible ? '<span class="tag green">显示</span>' : '<span class="tag gray">隐藏</span>'}</td>
          <td class="ops"><a onclick="menuToggle(${m.id},${m.visible ? 0 : 1})">${m.visible ? "隐藏" : "显示"}</a> · <a onclick="menuSort(${m.id},${m.sort})">排序</a></td></tr>`).join("")}</table></div>`;
    },
    auth: async () => {
      const [gs, us] = await Promise.all([api("/platform/groups"), api("/auth/users")]);
      $("#pf-body").innerHTML = `<div class="card"><h3>权限组授权 (组内用户同权限，支持临时授权)</h3>
        ${gs.map((g) => `<div style="padding:12px 0;border-bottom:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px">
            <b>${esc(g.name)}</b><span class="muted">${esc(g.description)}</span></div>
          <div class="muted" style="margin:6px 0">功能范围：${esc(g.perms)}</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">${g.members.map((m) => `<span class="tag blue">${esc(m.name)}(${esc(m.role)}) <a onclick="rmMember(${g.id},${m.id})" style="color:var(--danger)">✕</a></span>`).join("") || '<span class="muted">暂无成员</span>'}</div>
          <div style="margin-top:8px"><button class="btn ghost sm" onclick="addMember(${g.id})">+ 添加成员/临时授权</button></div>
        </div>`).join("")}</div>`;
    },
    audit: async () => {
      const [al, ll] = await Promise.all([api("/platform/audit-logs?page=1&size=15"), api("/platform/login-logs?page=1&size=10")]);
      $("#pf-body").innerHTML = `
        <div class="grid-2">
        <div class="card"><h3>操作审计日志</h3><table class="tbl"><tr><th>时间</th><th>用户</th><th>模块</th><th>操作</th><th>详情</th></tr>
          ${al.items.map((l) => `<tr><td class="muted">${esc(l.created_at)}</td><td>${esc(l.username)}</td><td>${esc(l.module)}</td><td>${esc(l.action)}</td><td class="muted">${esc((l.detail || "").slice(0, 18))}</td></tr>`).join("")}</table></div>
        <div class="card"><h3>登录日志</h3><table class="tbl"><tr><th>时间</th><th>用户</th><th>IP</th><th>结果</th></tr>
          ${ll.items.map((l) => `<tr><td class="muted">${esc(l.created_at)}</td><td>${esc(l.username)}</td><td>${esc(l.ip)}</td>
            <td>${l.action === "登录成功" ? '<span class="tag green">成功</span>' : '<span class="tag red">失败</span>'}</td></tr>`).join("")}</table></div></div>`;
    },
    hand: async () => {
      const [hs, us] = await Promise.all([api("/platform/handover"), api("/auth/users")]);
      $("#pf-body").innerHTML = `<div class="card"><h3>工作交接 (离职/换岗权限批量移交)</h3>
        <div class="toolbar">
          <select id="hd-from">${us.map((u) => `<option value="${esc(u.username)}">${esc(u.name)}(${esc(u.role_name)})</option>`).join("")}</select>
          <span class="muted">→</span>
          <select id="hd-to">${us.map((u) => `<option value="${esc(u.username)}">${esc(u.name)}(${esc(u.role_name)})</option>`).join("")}</select>
          <select id="hd-scope"><option>全部业务</option><option>审批事务</option><option>仅权限组</option></select>
          <button class="btn primary sm" id="hd-go">执行交接</button></div>
        <table class="tbl"><tr><th>交接人</th><th>接收人</th><th>范围</th><th>说明</th><th>时间</th></tr>
        ${hs.map((h) => `<tr><td>${esc(h.from_user)}</td><td>${esc(h.to_user)}</td><td>${esc(h.scope)}</td><td class="muted">${esc(h.detail)}</td><td class="muted">${esc(h.created_at)}</td></tr>`).join("") || '<tr><td colspan="5" class="empty">暂无交接记录</td></tr>'}</table></div>`;
      $("#hd-go").onclick = async () => {
        try {
          const r = await api("/platform/handover", { method: "POST", body: {
            from_user: $("#hd-from").value, to_user: $("#hd-to").value, scope: $("#hd-scope").value } });
          toast(`交接完成：转移在途审批${r.moved_approvals}件，同步权限组${r.synced_groups}个`, "ok"); tabs.hand();
        } catch (e) { toast(e.message, "err"); }
      };
    },
    msg: async () => {
      const [d, tps] = await Promise.all([api("/platform/messages"), api("/platform/templates")]);
      $("#pf-body").innerHTML = `<div class="grid-2">
        <div class="card"><h3>消息中心</h3>
          ${canManageCompany() ? `<div class="toolbar"><button class="btn primary sm" id="msg-send">+ 发送消息(邮件/短信/系统)</button></div>` : ""}
          ${d.items.map((m) => `<div style="padding:9px 0;border-bottom:1px dashed var(--border)">
            <div style="display:flex;justify-content:space-between;gap:8px"><b>${m.status === "未读" ? "🔴 " : ""}${esc(m.title)}</b>
              <span class="tag ${m.channel === "系统" ? "gray" : m.channel === "邮件" ? "blue" : "orange"}">${esc(m.channel)}</span></div>
            <div class="muted" style="margin-top:4px">${esc(m.content)}</div></div>`).join("") || '<div class="empty">暂无消息</div>'}</div>
        <div class="card"><h3>邮件模板管理</h3>
          ${tps.map((t) => `<div style="padding:9px 0;border-bottom:1px dashed var(--border)">
            <b>${esc(t.name)}</b> <span class="tag blue">${esc(t.channel)}</span>
            <div class="muted" style="margin-top:4px">${esc(t.subject)}</div>
            <div class="muted">${esc(t.content)}</div></div>`).join("")}</div></div>`;
      if (canManageCompany()) $("#msg-send").onclick = () => {
        UI.openModal("发送消息提醒", `<div class="form-grid">
          <div class="field"><label>渠道</label><select id="ms-ch"><option>系统</option><option>邮件</option><option>短信</option></select></div>
          <div class="field"><label>接收对象</label><select id="ms-rv"><option value="all">全部用户</option><option value="chairman">董事长</option><option value="secretary">秘书</option><option value="supervisor">主管</option><option value="company">企业用户</option></select></div>
          <div class="field full"><label>标题</label><input id="ms-title"></div>
          <div class="field full"><label>内容</label><textarea id="ms-content"></textarea></div></div>`,
          `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="ms-ok">发送</button>`);
        $("#ms-ok").onclick = async () => {
          await api(`/platform/messages/send?title=${encodeURIComponent($("#ms-title").value.trim())}&content=${encodeURIComponent($("#ms-content").value.trim())}&channel=${encodeURIComponent($("#ms-ch").value)}&receiver_role=${$("#ms-rv").value}`, { method: "POST" });
          UI.closeModal(); toast("已发送", "ok"); tabs.msg(); refreshMsgBadge();
        };
      };
    },
  };
  $$("#pf-tabs .tab").forEach((t) => t.onclick = () => {
    $$("#pf-tabs .tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active"); tabs[t.dataset.t]();
  });
  tabs.user();
}
window.userEdit = async (uid) => {
  const [rows, cos] = await Promise.all([api("/auth/users"), api("/companies/all")]);
  const u = rows.find((x) => x.id === uid);
  UI.openModal(`编辑用户 - ${u.username}`, `<div class="form-grid">
    <div class="field"><label>姓名</label><input id="eu-name" value="${esc(u.name)}"></div>
    <div class="field"><label>角色</label><select id="eu-role">${["admin", "chairman", "secretary", "supervisor", "employee", "company"].map((r) => `<option value="${r}" ${u.role === r ? "selected" : ""}>${({ admin: "管理员", chairman: "董事长", secretary: "秘书", supervisor: "主管", employee: "员工", company: "企业用户" })[r]}</option>`).join("")}</select></div>
    <div class="field"><label>部门</label><input id="eu-dept" value="${esc(u.dept)}"></div>
    <div class="field"><label>关联企业(企业用户必选)</label><select id="eu-co"><option value="">无</option>${cos.map((c) => `<option value="${c.id}" ${u.company_id === c.id ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div>
    <div class="field"><label>状态</label><select id="eu-st"><option value="1" ${u.status ? "selected" : ""}>启用</option><option value="0" ${!u.status ? "selected" : ""}>停用</option></select></div></div>`,
    `<button class="btn ghost" onclick="UI.closeModal()">取消</button><button class="btn primary" id="eu-save">保存</button>`);
  $("#eu-save").onclick = async () => {
    await api("/auth/users/" + uid, { method: "PUT", body: {
      name: $("#eu-name").value.trim(), role: $("#eu-role").value, dept: $("#eu-dept").value.trim(),
      company_id: $("#eu-co").value ? +$("#eu-co").value : null, status: +$("#eu-st").value } });
    UI.closeModal(); toast("已保存", "ok"); switchView("platform");
  };
};
window.userReset = (uid, un) => UI.confirm(`确认重置「${un}」的密码？`, async () => {
  const r = await api(`/auth/users/${uid}/reset-password`, { method: "POST" });
  toast(`新密码: ${r.new_password} (已要求首次登录修改)`, "ok");
});
window.userDel = (uid, un) => UI.confirm(`确认删除用户「${un}」？`, async () => {
  await api("/auth/users/" + uid, { method: "DELETE" }); toast("已删除", "ok"); switchView("platform");
});
window.menuToggle = async (mid, v) => { await api(`/platform/menus/${mid}?visible=${v}`, { method: "PUT" }); switchView("platform"); };
window.menuSort = (mid, cur) => {
  UI.openModal("调整菜单排序", `<div class="field"><label>排序值(越小越靠前)</label><input id="so-v" type="number" value="${cur}"></div>`,
    `<button class="btn primary" id="so-ok">保存</button>`);
  $("#so-ok").onclick = async () => { await api(`/platform/menus/${mid}?sort=${$("#so-v").value}`, { method: "PUT" }); UI.closeModal(); switchView("platform"); };
};
window.addMember = (gid) => {
  UI.openModal("添加权限组成员", `<div class="field"><label>选择用户</label><select id="am-uid"></select></div>`);
  api("/auth/users").then((us) => {
    $("#am-uid").innerHTML = us.map((u) => `<option value="${u.id}">${esc(u.name)}(${esc(u.username)})</option>`).join("");
    $("#modal-foot").innerHTML = `<button class="btn primary" id="am-ok">加入</button>`;
    $("#am-ok").onclick = async () => { await api(`/platform/groups/${gid}/members/${$("#am-uid").value}`, { method: "POST" }); UI.closeModal(); toast("已加入", "ok"); switchView("platform"); };
  });
};
window.rmMember = async (gid, uid) => { await api(`/platform/groups/${gid}/members/${uid}`, { method: "DELETE" }); toast("已移除", "ok"); switchView("platform"); };

/* ---------- 主题 / 布局 / 消息 ---------- */
const THEMES = ["blue", "green", "purple", "red", "dark"];
$("#btn-theme").onclick = () => {
  const cur = document.body.dataset.theme;
  document.body.dataset.theme = THEMES[(THEMES.indexOf(cur) + 1) % THEMES.length];
};
$("#btn-layout").onclick = () => {
  const cur = document.body.dataset.layout;
  document.body.dataset.layout = cur === "sidebar" ? "top" : "sidebar";
  $("#topnav").classList.toggle("hidden", cur !== "sidebar");
};
$("#user-chip").onclick = () => $(".user-menu").classList.toggle("hidden");
$("#menu-logout").onclick = () => logout();
$("#menu-profile").onclick = () => {
  $("#pwd-old").value = ""; $("#pwd-new").value = ""; $("#pwd-new2").value = "";
  $("#pwd-modal").classList.remove("hidden");
};
$("#msg-badge").onclick = () => { if (allowedViews().includes("platform")) switchView("platform"); else toast("暂无消息中心权限"); };
$("#btn-change-pwd").onclick = async () => {
  const o = $("#pwd-old").value, n = $("#pwd-new").value, n2 = $("#pwd-new2").value;
  if (n !== n2) return toast("两次新密码不一致", "err");
  try { await api("/auth/change-password", { method: "POST", body: { old_password: o, new_password: n } });
    $("#pwd-modal").classList.add("hidden"); toast("密码修改成功", "ok"); }
  catch (e) { toast(e.message, "err"); }
};

/* ---------- 启动 ---------- */
$("#btn-login").onclick = doLogin;
$("#login-password").onkeydown = (e) => { if (e.key === "Enter") doLogin(); };
// 密码框确保不会被任何全局键盘监听拦截
$("#login-password").addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === "Tab") return;
}, false);
(async function init() {
  if (!S.token) {
    $("#login-page").classList.remove("hidden");
    // 页面渲染完后自动聚焦密码框，确保可输入
    setTimeout(() => {
      const p = document.getElementById("login-password");
      if (p) p.focus();
    }, 100);
    return;
  }
  try { await enterApp(); }
  catch (e) {
    $("#login-page").classList.remove("hidden");
    setTimeout(() => {
      const p = document.getElementById("login-password");
      if (p) p.focus();
    }, 100);
  }
})();
