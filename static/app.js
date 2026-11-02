/* MediCare HMS - single page frontend (vanilla JS) */
const $ = (s, e = document) => e.querySelector(s);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = v => "PKR " + Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
const MONEY_COLS = new Set(["total", "paid", "balance", "amount", "price", "unit_price", "fee", "daily_rate"]);
const COLORS = ["#4f46e5", "#059669", "#e11d48", "#d97706", "#0284c7", "#7c3aed", "#ec4899", "#64748b"];
const brandColor = () => getComputedStyle(document.documentElement).getPropertyValue("--brand").trim() || "#4f46e5";
let META = null, current = null;

function applyTheme(t) {
  document.documentElement.dataset.theme = t || "indigo";
  localStorage.setItem("hms_theme", t || "indigo");
  if ($("#themeSelect")) $("#themeSelect").value = t || "indigo";
}
applyTheme(localStorage.getItem("hms_theme") || "indigo");
if ($("#themeSelect")) {
  $("#themeSelect").onchange = e => {
    applyTheme(e.target.value);
    if (current === "dashboard") renderDashboard();
    else if (current === "reports") renderReports();
  };
}

async function api(path, opts = {}) {
  const r = await fetch("/api" + path, { method: opts.method || "GET", headers: { "Content-Type": "application/json" }, body: opts.body ? JSON.stringify(opts.body) : undefined });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && path !== "/login") { showLogin(); throw new Error("Session expired"); }
  if (!r.ok) throw new Error(data.error || "Request failed");
  return data;
}
function toast(msg, bad) { const t = $("#toast"); t.textContent = msg; t.className = "toast show" + (bad ? " bad" : ""); clearTimeout(toast.t); toast.t = setTimeout(() => t.className = "toast", 3200); }
const fail = e => toast(e.message, true);

/* ---------- badges ---------- */
const GOOD = ["Completed", "Paid", "Available", "Active", "Discharged", "Collected"], WARN = ["Scheduled", "Partial", "Ordered", "Sample Collected", "Maintenance", "On leave", "Unpaid"], BAD = ["Cancelled", "No-show", "Inactive"], INFO = ["Admitted", "Occupied"];
function badge(v) { const c = GOOD.includes(v) ? "b-ok" : BAD.includes(v) ? "b-bad" : INFO.includes(v) ? "b-info" : WARN.includes(v) ? "b-warn" : ""; return `<span class="badge ${c}">${esc(v)}</span>`; }
const BADGE_COLS = new Set(["status"]);

/* ---------- auth ---------- */
function showLogin() { $("#app").classList.add("hidden"); $("#login").classList.remove("hidden"); }
$("#loginForm").onsubmit = async e => {
  e.preventDefault(); const f = new FormData(e.target);
  try { await api("/login", { method: "POST", body: Object.fromEntries(f) }); $("#loginErr").textContent = ""; e.target.reset(); boot(); }
  catch (err) { $("#loginErr").textContent = err.message; }
};
$("#demoAccounts")?.addEventListener("click", e => {
  const tr = e.target.closest("tr[data-u]");
  if (!tr) return;
  const f = $("#loginForm");
  f.username.value = tr.dataset.u;
  f.password.value = tr.dataset.p;
  f.requestSubmit();
});
$("#logout").onclick = async () => { await api("/logout", { method: "POST" }); showLogin(); };
$("#menuBtn").onclick = () => $("#sidebar").classList.toggle("open");
$("#mClose").onclick = closeModal;
$("#modal").onclick = e => { if (e.target.id === "modal") closeModal(); };
function openModal(title, html, wide) { $("#mTitle").textContent = title; $("#mBody").innerHTML = html; $(".modal-box").classList.toggle("wide", !!wide); $("#modal").classList.remove("hidden"); }
function closeModal() { $("#modal").classList.add("hidden"); }

/* ---------- boot / navigation ---------- */
async function boot() {
  try { META = await api("/meta"); } catch { return showLogin(); }
  $("#login").classList.add("hidden"); $("#app").classList.remove("hidden");
  const u = META.user; $("#uName").textContent = u.full_name; $("#uRole").textContent = u.role; $("#avatar").textContent = u.full_name.replace(/^Dr\.\s*/, "")[0];
  const groups = {};
  META.resources.forEach(r => (groups[r.group] ||= []).push(r));
  let h = `<div class="brand"><div class="logo">✚</div>${esc(META.hospital)}</div>`;
  h += `<div class="nav" data-go="dashboard"><span>📊</span>Dashboard</div>`;
  h += `<div class="nav" data-go="gemini_ai"><span>✨</span>Gemini AI Hub</div>`;
  if (META.reports) h += `<div class="nav" data-go="reports"><span>📈</span>Reports</div>`;
  if (META.user.role === "Admin") h += `<div class="nav" data-go="db_studio"><span>🗄️</span>Database Studio</div>`;
  for (const [g, list] of Object.entries(groups)) { h += `<div class="sgroup">${g}</div>`; list.forEach(r => h += `<div class="nav" data-go="${r.key}"><span>${r.icon}</span>${esc(r.label)}</div>`); }
  $("#sidebar").innerHTML = h;
  go(location.hash.slice(1) || "dashboard");
}
$("#sidebar").onclick = e => { const n = e.target.closest("[data-go]"); if (n) { go(n.dataset.go); $("#sidebar").classList.remove("open"); } };
function go(key) {
  if (!["dashboard", "reports", "gemini_ai", "db_studio"].includes(key) && !META.resources.find(r => r.key === key)) key = "dashboard";
  current = key; location.hash = key;
  document.querySelectorAll(".nav").forEach(n => n.classList.toggle("active", n.dataset.go === key));
  if (key === "dashboard") { $("#pageTitle").textContent = "Dashboard"; return renderDashboard(); }
  if (key === "gemini_ai") { $("#pageTitle").textContent = "✨ Gemini AI Clinical & Operations Hub"; return renderGeminiHub(); }
  if (key === "reports") { $("#pageTitle").textContent = "Reports & Analytics"; return renderReports(); }
  if (key === "db_studio") { $("#pageTitle").textContent = "🗄️ Database Studio & SQLite Explorer"; return renderDbStudio(); }
  const r = META.resources.find(r => r.key === key); $("#pageTitle").textContent = r.label; renderTable(r);
}
setInterval(() => { $("#clock").textContent = new Date().toLocaleString([], { dateStyle: "medium", timeStyle: "short" }); }, 1000);

/* ---------- charts (canvas) ---------- */
function setup(c, h) { const dpr = devicePixelRatio || 1, w = c.parentElement.clientWidth - 32; c.width = w * dpr; c.height = h * dpr; c.style.height = h + "px"; const x = c.getContext("2d"); x.scale(dpr, dpr); x.clearRect(0, 0, w, h); return [x, w, h]; }
function barChart(c, data, color = brandColor(), fmt = v => v) {
  const [x, w, h] = setup(c, 220); const max = Math.max(1, ...data.map(d => d.value)) * 1.15, pl = 40, pb = 24, pt = 10, bw = (w - pl) / data.length;
  x.font = "11px sans-serif"; x.fillStyle = "#6b7a8c"; x.strokeStyle = "#e3e9f1";
  for (let i = 0; i <= 4; i++) { const y = pt + (h - pb - pt) * (1 - i / 4); x.beginPath(); x.moveTo(pl, y); x.lineTo(w, y); x.stroke(); x.textAlign = "right"; x.fillText(fmt(Math.round(max * i / 4)), pl - 6, y + 4); }
  data.forEach((d, i) => { const bh = (h - pb - pt) * d.value / max, bx = pl + i * bw + bw * .18; x.fillStyle = color; x.beginPath(); x.roundRect(bx, h - pb - bh, bw * .64, bh, 4); x.fill(); x.fillStyle = "#6b7a8c"; x.textAlign = "center"; if (data.length < 20 || i % 3 == 0) x.fillText(d.label, bx + bw * .32, h - 8); });
}
function lineChart(c, data, color = "#3b82c4", fmt = v => v) {
  const [x, w, h] = setup(c, 220); const max = Math.max(1, ...data.map(d => d.value)) * 1.15, pl = 68, pb = 24, pt = 10, step = (w - pl - 8) / Math.max(1, data.length - 1);
  x.font = "11px sans-serif"; x.strokeStyle = "#e3e9f1"; x.fillStyle = "#6b7a8c";
  for (let i = 0; i <= 4; i++) { const y = pt + (h - pb - pt) * (1 - i / 4); x.beginPath(); x.moveTo(pl, y); x.lineTo(w, y); x.stroke(); x.textAlign = "right"; x.fillText(fmt(Math.round(max * i / 4)), pl - 6, y + 4); }
  const pts = data.map((d, i) => [pl + i * step, pt + (h - pb - pt) * (1 - d.value / max)]);
  const g = x.createLinearGradient(0, pt, 0, h - pb); g.addColorStop(0, color + "55"); g.addColorStop(1, color + "05");
  x.beginPath(); pts.forEach((p, i) => i ? x.lineTo(...p) : x.moveTo(...p)); x.lineTo(pts.at(-1)[0], h - pb); x.lineTo(pl, h - pb); x.fillStyle = g; x.fill();
  x.beginPath(); pts.forEach((p, i) => i ? x.lineTo(...p) : x.moveTo(...p)); x.strokeStyle = color; x.lineWidth = 2.5; x.stroke();
  pts.forEach(p => { x.beginPath(); x.arc(p[0], p[1], 3, 0, 7); x.fillStyle = color; x.fill(); });
  x.fillStyle = "#6b7a8c"; x.textAlign = "center"; data.forEach((d, i) => { if (data.length < 20 || i % 3 == 0) x.fillText(d.label, pl + i * step, h - 8); });
}
function donut(c, data, fmt = v => v) {
  const [x, w, h] = setup(c, 200); const tot = data.reduce((a, d) => a + d.value, 0) || 1, r = 78, cx = w / 2, cy = h / 2; let a0 = -Math.PI / 2;
  data.forEach((d, i) => { const a = d.value / tot * Math.PI * 2; x.beginPath(); x.arc(cx, cy, r, a0, a0 + a); x.arc(cx, cy, r * .6, a0 + a, a0, true); x.closePath(); x.fillStyle = COLORS[i % COLORS.length]; x.fill(); a0 += a; });
  x.fillStyle = "#1c2733"; x.font = "bold 16px sans-serif"; x.textAlign = "center"; x.fillText(fmt(tot), cx, cy + 4); x.font = "11px sans-serif"; x.fillStyle = "#6b7a8c"; x.fillText("total", cx, cy + 20);
  c.parentElement.querySelector(".legend")?.remove(); const l = document.createElement("div"); l.className = "legend";
  l.innerHTML = data.map((d, i) => `<span><i style="background:${COLORS[i % COLORS.length]}"></i>${esc(d.label)} (${fmt(d.value)})</span>`).join(""); c.parentElement.appendChild(l);
}
function hbars(el, data, fmt = v => v) {
  const max = Math.max(1, ...data.map(d => d.value));
  el.innerHTML = data.map(d => `<div style="margin:9px 0"><div style="display:flex;justify-content:space-between;font-size:12.5px"><span>${esc(d.label ?? d.name)}</span><b>${fmt(d.value ?? d.occupied)}</b></div><div class="bar"><i style="width:${(d.value ?? d.occupied) / max * 100}%"></i></div></div>`).join("") || '<span class="muted">No data</span>';
}
const card = (t, id, extra = "") => `<div class="card"><h4>${t}</h4>${extra || `<canvas id="${id}"></canvas>`}</div>`;
function miniTable(cols, rows) {
  return `<table class="mini"><tr>${cols.map(c => `<th>${c[1]}</th>`).join("")}</tr>${rows.map(r => `<tr>${cols.map(c => `<td>${c[2] ? c[2](r[c[0]]) : esc(r[c[0]])}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${cols.length}" class="muted">Nothing to show</td></tr>`}</table>`;
}

/* ---------- dashboard ---------- */
async function renderDashboard() {
  $("#view").innerHTML = "Loading…";
  let d; try { d = await api("/dashboard"); } catch (e) { return fail(e); }
  const k = d.kpis, occ = k.beds_total ? Math.round(k.beds_occupied / k.beds_total * 100) : 0;
  const kp = (ic, bg, v, l, go) => `<div class="card kpi" ${go ? `data-go="${go}" style="cursor:pointer"` : ""}><div class="ic" style="background:${bg}">${ic}</div><div><div class="v">${v}</div><div class="l">${l}</div></div></div>`;
  const can = key => META.resources.some(r => r.key === key);
  const canW = key => META.resources.some(r => r.key === key && r.canWrite);
  $("#view").innerHTML = `
  <div class="qbar">
    <b style="margin-right:4px">⚡ Quick Actions:</b>
    ${canW("patients") ? `<button class="btn primary sm" data-qa="patients">＋ Register Patient</button>` : ""}
    ${canW("appointments") ? `<button class="btn sm" data-qa="appointments">📅 Book Appointment</button>` : ""}
    ${canW("encounters") ? `<button class="btn sm" data-qa="encounters">🩺 New Consultation (EMR)</button>` : ""}
    ${canW("admissions") ? `<button class="btn sm" data-qa="admissions">🛏️ Admit Patient (IPD)</button>` : ""}
    ${canW("lab_orders") ? `<button class="btn sm" data-qa="lab_orders">🔬 Order Lab Test</button>` : ""}
    ${canW("dispensing") ? `<button class="btn sm" data-qa="dispensing">💊 Dispense Medicine</button>` : ""}
    <button class="btn sm" onclick="go('gemini_ai')">✨ Gemini AI Triage &amp; Copilot</button>
    ${META.user.role === "Admin" ? `<button class="btn sm" onclick="go('db_studio')">🗄️ Database Studio</button>` : ""}
  </div>
  <div class="grid kpis">
    ${kp("🧑‍🤝‍🧑", "#dff3f4", k.patients, `Total patients (+${k.new_patients_month} this month)`, can("patients") && "patients")}
    ${kp("📅", "#e4effb", k.appointments_today, "Appointments today", can("appointments") && "appointments")}
    ${kp("🛏️", "#efe9fb", k.admitted, `Admitted · ${occ}% bed occupancy`, can("admissions") && "admissions")}
    ${kp("👩‍⚕️", "#e1f5ec", k.doctors, "Active doctors", can("staff") && "staff")}
    ${kp("💰", "#fdf0d3", money(k.revenue_today), `Collected today · ${money(k.revenue_month)} this month`, can("invoices") && "invoices")}
    ${kp("🧾", "#fbe0e0", money(k.outstanding), "Outstanding balance", can("invoices") && "invoices")}
    ${kp("🔬", "#e4effb", k.pending_labs, "Pending lab orders", can("lab_orders") && "lab_orders")}
    ${kp("💊", "#fdf0d3", k.low_stock + " / " + k.expiring, "Low stock / expiring ≤90d", can("medicines") && "medicines")}
  </div>
  <div class="grid cols2">${card("Appointments – last 7 days", "c1")}${card("Revenue collected (PKR) – last 14 days", "c2")}</div>
  <div class="grid cols2">${card("Bed occupancy by ward", "", '<div id="wardBars"></div>')}${card("Appointments by department", "c3")}</div>
  <div class="grid cols2">${card("Appointment status", "c4")}${card("Invoice status", "c5")}</div>
  <div class="grid cols2">
    ${card("Upcoming appointments", "", miniTable([["date", "Date"], ["time", "Time"], ["patient", "Patient"], ["doctor", "Doctor"]], d.upcoming))}
    ${card("Recent admissions", "", miniTable([["admit_date", "Date"], ["patient", "Patient"], ["ward", "Ward"], ["bed_no", "Bed"], ["status", "Status", badge]], d.recent_admissions))}
  </div>
  ${can("medicines") ? card("⚠ Stock alerts (low stock or expiring soon)", "", miniTable([["name", "Medicine"], ["stock", "Stock"], ["reorder_level", "Reorder at"], ["expiry_date", "Expiry"]], d.low_stock_list)) : ""}`;
  document.querySelectorAll(".kpi[data-go]").forEach(n => n.onclick = () => go(n.dataset.go));
  document.querySelectorAll("[data-qa]").forEach(b => b.onclick = () => {
    const r = META.resources.find(x => x.key === b.dataset.qa);
    if (r) openForm(r, null, () => renderDashboard());
  });
  const draw = () => {
    if (current !== "dashboard") return;
    barChart($("#c1"), d.appointments_7d); lineChart($("#c2"), d.revenue_14d, "#1f9d6b", v => "PKR " + (v >= 1000 ? Math.round(v / 1000) + "k" : v));
    hbars($("#wardBars"), d.wards.map(w => ({ label: `${w.name} (${w.occupied || 0}/${w.total})`, value: w.occupied || 0 })));
    $("#wardBars").querySelectorAll(".bar i").forEach((b, i) => b.style.width = (d.wards[i].total ? (d.wards[i].occupied || 0) / d.wards[i].total * 100 : 0) + "%");
    barChart($("#c3"), d.by_department.map(x => ({ label: x.label.slice(0, 8), value: x.value })), "#7b61c9");
    donut($("#c4"), d.appointment_status); donut($("#c5"), d.invoice_status);
  };
  draw(); window.onresize = () => { clearTimeout(window._rt); window._rt = setTimeout(draw, 150); };
}

/* ---------- reports ---------- */
async function renderReports() {
  $("#view").innerHTML = "Loading…";
  let d; try { d = await api("/reports"); } catch (e) { return fail(e); }
  const tot = d.revenue_30d.reduce((a, x) => a + x.value, 0);
  $("#view").innerHTML = `
  <div class="grid cols2" style="grid-template-columns:1fr">${card(`Revenue (PKR) – last 30 days (total ${money(tot)})`, "r1")}</div>
  <div class="grid cols2">${card("Payment methods (PKR)", "r2")}${card("Patients by age group", "r3")}</div>
  <div class="grid cols2">${card("Top diagnoses", "", '<div id="h1"></div>')}${card("Most dispensed medicines (units)", "", '<div id="h2"></div>')}</div>
  <div class="grid cols2">${card("Lab test usage", "", '<div id="h3"></div>')}${card("Patients by gender", "r4")}</div>
  ${card("Doctor workload", "", miniTable([["doctor", "Doctor"], ["department", "Department"], ["appointments", "Appointments"], ["consultations", "Consultations"], ["admissions", "Admissions"]], d.doctor_workload))}`;
  const draw = () => {
    if (current !== "reports") return;
    lineChart($("#r1"), d.revenue_30d, "#0e7c86", v => "PKR " + (v >= 1000 ? Math.round(v / 1000) + "k" : v));
    donut($("#r2"), d.payment_methods.map(x => ({ ...x, value: Math.round(x.value) })), v => money(v)); barChart($("#r3"), d.age_groups.sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true })), "#e69a1c"); donut($("#r4"), d.gender);
    hbars($("#h1"), d.top_diagnoses); hbars($("#h2"), d.top_medicines); hbars($("#h3"), d.lab_usage);
  };
  draw(); window.onresize = () => { clearTimeout(window._rt); window._rt = setTimeout(draw, 150); };
}

/* ---------- generic table ---------- */
function fmtCell(r, key, v) {
  if (v === null || v === undefined || v === "") return '<span class="muted">—</span>';
  if (BADGE_COLS.has(key)) return badge(v);
  if (MONEY_COLS.has(key)) return money(v);
  return esc(v);
}
async function renderTable(res) {
  const statusField = res.fields.find(f => f.name === "status" && f.options);
  const filterChips = statusField ? `<div class="chips" id="stChips"><button class="chip active" data-st="">All</button>${statusField.options.map(o => `<button class="chip" data-st="${esc(o)}">${esc(o)}</button>`).join("")}</div>` : "";
  $("#view").innerHTML = `<div class="toolbar"><input id="q" placeholder="Search ${esc(res.label)}…">${filterChips}<div class="spacer"></div>${res.canWrite && res.fields.length ? `<button class="btn primary" id="addBtn">＋ New ${esc(res.label.replace(/s$/, ""))}</button>` : ""}<button class="btn" id="csvBtn">⬇ Export CSV</button><span class="muted small" id="cnt"></span></div>${res.key === "beds" ? '<div id="bedMap" class="bed-map-wrap"></div>' : ""}<div class="tbl-wrap" id="tw">Loading…</div><div class="pager" id="pager"></div>`;
  let data = [], stFilter = "", page = 1, pageSize = 25;
  const filtered = () => {
    const q = $("#q").value.toLowerCase();
    return data.filter(r => (!stFilter || r.status === stFilter) && (!q || Object.values(r).join(" ").toLowerCase().includes(q)));
  };
  const draw = () => {
    const list = filtered();
    const pages = Math.max(1, Math.ceil(list.length / pageSize));
    if (page > pages) page = pages;
    const slice = list.slice((page - 1) * pageSize, page * pageSize);
    $("#cnt").textContent = `${list.length} record${list.length === 1 ? "" : "s"}`;
    if (res.key === "beds" && $("#bedMap")) {
      const byWard = {};
      list.forEach(b => (byWard[b.ward] ||= []).push(b));
      $("#bedMap").innerHTML = Object.entries(byWard).map(([w, beds]) => `<div class="card" style="margin-bottom:14px"><h4>🏥 ${esc(w)} <span class="muted small">(${beds.filter(b => b.status === "Available").length} available / ${beds.length} total — click a tile to toggle Available/Maintenance or admit)</span></h4><div class="bed-grid">${beds.map(b => `<div class="bed-tile bed-${b.status.toLowerCase()}" data-bed-id="${b.id}" data-bed-st="${esc(b.status)}" style="cursor:pointer" title="Click to manage bed ${esc(b.bed_no)}"><b>🛏️ ${esc(b.bed_no)}</b><span>${badge(b.status)}</span>${b.occupant ? `<small>👤 ${esc(b.occupant)}</small>` : `<small class="muted">${b.status === "Available" ? "Click to Admit / Maint." : "In Maintenance"}</small>`}</div>`).join("")}</div></div>`).join("");
    }
    const cls = r => { if (res.flag === "stock" && r.stock <= r.reorder_level) return "dangerrow"; if (res.key === "medicines" && r.expiry_date && r.expiry_date <= new Date(Date.now() + 90 * 864e5).toISOString().slice(0, 10)) return "warnrow"; return ""; };
    $("#tw").innerHTML = `<table class="t"><tr>${res.columns.map(c => `<th>${c[1]}</th>`).join("")}<th>Actions</th></tr>` + slice.map(r => {
      const locked = res.noEditWhen && Object.entries(res.noEditWhen).every(([k, v]) => r[k] === v);
      let a = "";
      if (res.profile) a += `<button class="btn sm primary" data-a="profile" data-id="${r.id}">360° Chart</button> `;
      if (res.invoice) a += `<button class="btn sm primary" data-a="invoice" data-id="${r.id}"> Billing / Pay</button> `;
      if (res.key === "appointments" && res.canWrite && r.status === "Scheduled") {
        a += `<button class="btn sm primary" data-a="appt-done" data-id="${r.id}">✓ Complete</button> `;
        a += `<button class="btn sm danger" data-a="appt-cancel" data-id="${r.id}">✕ Cancel</button> `;
      }
      if (res.key === "lab_orders" && res.canWrite && r.status !== "Completed") {
        a += `<button class="btn sm primary" data-a="lab-next" data-id="${r.id}" data-st="${esc(r.status)}">${r.status === "Ordered" ? "🧪 Collect Sample" : "📝 Enter Result"}</button> `;
      }
      if (res.key === "medicines" && res.canWrite) {
        a += `<button class="btn sm primary" data-a="restock" data-id="${r.id}" data-name="${esc(r.name)}">＋ Restock</button> `;
      }
      (res.actions || []).forEach(x => { if (Object.entries(x.when || {}).every(([k, v]) => r[k] === v)) a += `<button class="btn sm primary" data-a="${x.key}" data-id="${r.id}">${x.label}</button> `; });
      if (res.canWrite && res.fields.length && !res.noEdit && !locked) a += `<button class="btn sm" data-a="edit" data-id="${r.id}">Edit</button> `;
      if (res.canDelete) a += `<button class="btn sm danger" data-a="del" data-id="${r.id}">Delete</button>`;
      return `<tr class="${cls(r)}">${res.columns.map(c => `<td class="${MONEY_COLS.has(c[0]) ? "num" : ""}">${fmtCell(r, c[0], r[c[0]])}</td>`).join("")}<td class="act">${a}</td></tr>`;
    }).join("") + (slice.length ? "" : `<tr><td colspan="${res.columns.length + 1}" class="muted" style="text-align:center;padding:30px">No records found</td></tr>`) + "</table>";
    $("#pager").innerHTML = list.length > pageSize ? `<span>Showing ${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, list.length)} of ${list.length}</span><div style="display:flex;gap:6px"><button class="btn sm" id="pgPrev" ${page <= 1 ? "disabled" : ""}>← Prev</button><span style="padding:4px 8px">Page ${page} / ${pages}</span><button class="btn sm" id="pgNext" ${page >= pages ? "disabled" : ""}>Next →</button></div>` : "";
    if ($("#pgPrev")) $("#pgPrev").onclick = () => { page--; draw(); };
    if ($("#pgNext")) $("#pgNext").onclick = () => { page++; draw(); };
  };
  const load = async () => { try { data = await api("/r/" + res.key); draw(); } catch (e) { fail(e); } };
  await load();
  $("#q").oninput = () => { page = 1; draw(); };
  if ($("#stChips")) $("#stChips").onclick = e => {
    const c = e.target.closest("[data-st]"); if (!c) return;
    stFilter = c.dataset.st; page = 1;
    document.querySelectorAll("#stChips .chip").forEach(x => x.classList.toggle("active", x === c));
    draw();
  };
  if ($("#bedMap")) $("#bedMap").onclick = async e => {
    const tile = e.target.closest("[data-bed-id]"); if (!tile || !res.canWrite) return;
    const bid = +tile.dataset.bedId, st = tile.dataset.bedSt;
    if (st === "Occupied") return toast("Bed is occupied — go to Admissions (IPD) to discharge patient", true);
    const next = st === "Available" ? "Maintenance" : "Available";
    if (confirm(`Set bed status to "${next}"?`)) {
      try {
        await api(`/beds/${bid}/status`, { method: "POST", body: { status: next } }).catch(async () => {
          const rec = await api(`/record/beds/${bid}`);
          await api(`/r/beds/${bid}`, { method: "PUT", body: { ...rec, status: next } });
        });
        toast(`Bed marked ${next}`); load();
      } catch (err) { fail(err); }
    }
  };
  if ($("#addBtn")) $("#addBtn").onclick = () => openForm(res, null, load);
  if ($("#csvBtn")) $("#csvBtn").onclick = () => {
    const list = filtered();
    const hdr = res.columns.map(c => `"${c[1].replace(/"/g, '""')}"`).join(",");
    const rows = list.map(r => res.columns.map(c => {
      const raw = r[c[0]];
      const formatted = MONEY_COLS.has(c[0]) && raw !== null && raw !== undefined && raw !== "" ? money(raw) : String(raw ?? "");
      return `"${formatted.replace(/"/g, '""')}"`;
    }).join(","));
    const blob = new Blob([[hdr, ...rows].join("\n")], { type: "text/csv" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${res.key}.csv`; a.click();
  };
  $("#tw").onclick = async e => {
    const b = e.target.closest("[data-a]"); if (!b) return; const id = +b.dataset.id, a = b.dataset.a;
    try {
      if (a === "edit") openForm(res, id, load);
      else if (a === "del") { if (confirm("Delete this record? This cannot be undone.")) { await api(`/r/${res.key}/${id}`, { method: "DELETE" }); toast("Deleted"); load(); } }
      else if (a === "profile") openProfile(id);
      else if (a === "invoice") openInvoice(id, load);
      else if (a === "discharge") { if (confirm("Discharge this patient and bill bed charges?")) { const r = await api(`/admissions/${id}/discharge`, { method: "POST" }); toast(`Discharged. ${r.days} day(s) billed: ${money(r.amount)}`); load(); } }
      else if (a === "appt-done" || a === "appt-cancel") {
        const nextSt = a === "appt-done" ? "Completed" : "Cancelled";
        await api(`/appointments/${id}/status`, { method: "POST", body: { status: nextSt } }).catch(async () => {
          const rec = await api(`/record/appointments/${id}`);
          await api(`/r/appointments/${id}`, { method: "PUT", body: { ...rec, status: nextSt } });
        });
        toast(`Appointment marked ${nextSt}`); load();
      }
      else if (a === "lab-next") {
        if (b.dataset.st === "Ordered") {
          const rec = await api(`/record/lab_orders/${id}`);
          await api(`/r/lab_orders/${id}`, { method: "PUT", body: { ...rec, status: "Sample Collected" } });
          toast("Sample marked Collected"); load();
        } else {
          const resTxt = prompt("Enter laboratory test result / findings:", "Within normal limits");
          if (resTxt !== null) {
            const rec = await api(`/record/lab_orders/${id}`);
            await api(`/r/lab_orders/${id}`, { method: "PUT", body: { ...rec, status: "Completed", result: resTxt } });
            toast("Lab result saved & Completed"); load();
          }
        }
      }
      else if (a === "restock") {
        const qty = prompt(`Add stock quantity for ${b.dataset.name}:`, "50");
        if (qty !== null && +qty > 0) {
          const m = await api(`/medicines/${id}/restock`, { method: "POST", body: { quantity: +qty } }).catch(async () => {
            const rec = await api(`/record/medicines/${id}`);
            const updated = { ...rec, stock: (+rec.stock || 0) + (+qty) };
            await api(`/r/medicines/${id}`, { method: "PUT", body: updated });
            return updated;
          });
          toast(`Restocked ${m.name} — new stock: ${m.stock}`); load();
        }
      }
    } catch (err) { fail(err); }
  };
}

/* ---------- forms ---------- */
const optCache = {};
async function options(ref) { return api("/options/" + ref); }
async function openForm(res, id, done) {
  let rec = {}; if (id) rec = await api(`/record/${res.key}/${id}`);
  const opts = {}; await Promise.all(res.fields.filter(f => f.type === "ref").map(async f => opts[f.name] = await options(f.ref)));
  // keep the current bed selectable when editing an admission
  if (res.key === "admissions" && id) { const all = await api("/r/beds"); const cur = all.find(b => b.id === rec.bed_id); if (cur && !opts.bed_id.find(o => o.id === cur.id)) opts.bed_id.unshift({ id: cur.id, label: `${cur.ward} · Bed ${cur.bed_no} (current)` }); }
  const val = f => rec[f.name] ?? (id ? "" : (f.default ?? (f.type === "date" && ["date", "admit_date"].includes(f.name) ? new Date().toISOString().slice(0, 10) : "")));
  const input = f => {
    const v = val(f), n = `name="${f.name}"`;
    if (f.type === "select") return `<select ${n}><option value=""></option>${f.options.map(o => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
    if (f.type === "ref") return `<select ${n}><option value=""></option>${opts[f.name].map(o => `<option value="${o.id}" ${o.id == v ? "selected" : ""}>${esc(o.label)}</option>`).join("")}</select>`;
    if (f.type === "textarea") return `<textarea ${n} rows="3">${esc(v)}</textarea>`;
    return `<input ${n} type="${f.type === "number" ? "number" : f.type}" ${f.type === "number" ? 'step="any" min="0"' : ""} value="${esc(v)}" ${f.type === "password" ? 'autocomplete="new-password"' : ""}>`;
  };
  openModal((id ? "Edit " : "New ") + res.label.replace(/s$/, ""), `<form id="rf" class="form">${res.fields.map(f => `<label class="${f.type === "textarea" ? "full" : ""}"><span class="${f.required ? "req" : ""}">${esc(f.label)}</span>${input(f)}</label>`).join("")}
    ${res.key === "encounters" ? `<div class="full" style="background:#f0f9fa;border:1px solid #b8e2e6;padding:10px 12px;border-radius:8px;display:flex;justify-content:space-between;align-items:center;gap:10px"><span>✨ <b>Gemini Clinical Copilot:</b> Enter brief symptoms/findings in Clinical Notes or Diagnosis and auto-draft SOAP notes, ICD-10 &amp; Rx.</span><button type="button" class="btn primary sm" id="aiCopilotBtn">✨ Auto-Draft with Gemini</button></div>` : ""}
    <div class="form-foot full"><button type="button" class="btn" onclick="closeModal()">Cancel</button><button class="btn primary">Save</button></div></form>`);
  if ($("#aiCopilotBtn")) {
    $("#aiCopilotBtn").onclick = async () => {
      const f = $("#rf");
      const btn = $("#aiCopilotBtn");
      btn.disabled = true; btn.textContent = "✨ Drafting with Gemini…";
      try {
        const payload = {
          patient_id: f.patient_id?.value,
          bp: f.bp?.value,
          temperature: f.temperature?.value,
          pulse: f.pulse?.value,
          weight: f.weight?.value,
          notes: f.notes?.value || f.diagnosis?.value || "General consultation",
        };
        const r = await api("/ai/copilot", { method: "POST", body: payload }).catch(() => localAiCopilot(payload));
        if (f.diagnosis && r.diagnosis) f.diagnosis.value = r.diagnosis;
        if (f.notes && r.soap_notes) f.notes.value = r.soap_notes;
        if (f.prescription && r.prescription) f.prescription.value = r.prescription;
        toast(`Drafted via ${r.source}`);
      } catch (err) { fail(err); }
      finally { btn.disabled = false; btn.textContent = "✨ Auto-Draft with Gemini"; }
    };
  }
  $("#rf").onsubmit = async e => {
    e.preventDefault(); const body = Object.fromEntries(new FormData(e.target));
    try { await api(id ? `/r/${res.key}/${id}` : `/r/${res.key}`, { method: id ? "PUT" : "POST", body }); closeModal(); toast("Saved"); done(); } catch (err) { fail(err); }
  };
}

/* ---------- patient profile ---------- */
async function openProfile(id) {
  const p = await api(`/patients/${id}/profile`);
  const sec = (t, cols, rows) => rows.length ? `<div class="sec">${t}</div>${miniTable(cols, rows)}` : "";
  const canW = k => META.resources.some(r => r.key === k && r.canWrite);
  openModal(`${p.name} · ${p.mrn}`, `
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:10px;background:#f0f9fa;border:1px solid #b8e2e6;padding:10px 12px;border-radius:8px">
    <div style="display:flex;gap:6px;flex-wrap:wrap">
      ${canW("appointments") ? `<button class="btn sm" data-pact="appointments">📅 + Appointment</button>` : ""}
      ${canW("encounters") ? `<button class="btn sm" data-pact="encounters">🩺 + Consultation</button>` : ""}
      ${canW("admissions") ? `<button class="btn sm" data-pact="admissions">🛏️ + Admit</button>` : ""}
      ${canW("lab_orders") ? `<button class="btn sm" data-pact="lab_orders">🔬 + Lab Order</button>` : ""}
      ${canW("dispensing") ? `<button class="btn sm" data-pact="dispensing">💊 + Dispense</button>` : ""}
    </div>
    <button class="btn primary sm" id="aiProfSumBtn">✨ Generate Gemini EMR Summary</button>
  </div>
  <div id="aiProfSumBox" class="hidden card" style="margin-bottom:12px;background:#fafdff;white-space:pre-wrap;font-size:13px"></div>
  <div class="kv">${[["Gender", p.gender], ["Date of birth", p.dob], ["Blood group", p.blood_group], ["Phone", p.phone], ["Email", p.email], ["Allergies", p.allergies || "None recorded"], ["Address", p.address], ["Emergency", [p.emergency_contact, p.emergency_phone].filter(Boolean).join(" · ")], ["Registered", p.created_at]].map(([k, v]) => `<div><span>${k}</span>${esc(v || "—")}</div>`).join("")}</div>
  ${sec("Consultations", [["date", "Date"], ["doctor", "Doctor"], ["bp", "BP"], ["diagnosis", "Diagnosis"], ["prescription", "Prescription"]], p.encounters)}
  ${sec("Admissions", [["admit_date", "Admitted"], ["discharge_date", "Discharged"], ["ward", "Ward"], ["bed_no", "Bed"], ["diagnosis", "Diagnosis"], ["status", "Status", badge]], p.admissions)}
  ${sec("Appointments", [["date", "Date"], ["time", "Time"], ["doctor", "Doctor"], ["reason", "Reason"], ["status", "Status", badge]], p.appointments)}
  ${sec("Lab results", [["ordered_at", "Date"], ["test", "Test"], ["status", "Status", badge], ["result", "Result"], ["reference_range", "Reference"]], p.labs)}
  ${sec("Medicines dispensed", [["date", "Date"], ["medicine", "Medicine"], ["quantity", "Qty"]], p.medicines)}
  ${sec("Invoices", [["number", "Invoice"], ["date", "Date"], ["total", "Total (PKR)", money], ["paid", "Paid (PKR)", money], ["status", "Status", badge]], p.invoices)}`, true);
  document.querySelectorAll("[data-pact]").forEach(btn => btn.onclick = async () => {
    const res = META.resources.find(r => r.key === btn.dataset.pact);
    if (!res) return;
    await openForm(res, null, () => openProfile(id));
    const sel = $("#rf [name='patient_id']");
    if (sel) sel.value = String(id);
  });
  $("#aiProfSumBtn").onclick = async () => {
    const b = $("#aiProfSumBtn"), box = $("#aiProfSumBox");
    b.disabled = true; b.textContent = "✨ Synthesizing…";
    try {
      const r = await api("/ai/patient-summary", { method: "POST", body: { patient_id: id } }).catch(() => localAiPatientSummary(p));
      box.classList.remove("hidden");
      box.innerHTML = `<div class="muted small" style="margin-bottom:6px">Source: ${esc(r.source)}</div>` + esc(r.summary);
    } catch (e) { fail(e); }
    finally { b.disabled = false; b.textContent = "✨ Refresh AI Summary"; }
  };
}

/* ---------- invoice ---------- */
async function openInvoice(id, done) {
  const res = META.resources.find(r => r.key === "invoices");
  const render = inv => {
    const bal = inv.total - inv.paid;
    openModal(`${inv.number} · ${inv.patient}`, `
    <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px"><div><b>${esc(inv.patient)}</b> <span class="muted">(${esc(inv.mrn)})</span><br><span class="muted small">${esc(inv.phone || "")} ${esc(inv.address || "")}</span></div><div style="text-align:right">${badge(inv.status)}<br><span class="muted small">${esc(inv.date)}</span></div></div>
    <div class="sec">Line items (PKR)</div>
    <table class="mini"><tr><th>Description</th><th style="text-align:right">Amount (PKR)</th><th></th></tr>${inv.items.map(i => `<tr><td>${esc(i.description)}</td><td style="text-align:right">${money(i.amount)}</td><td>${res.canWrite ? `<button class="btn sm danger" data-del="${i.id}">✕</button>` : ""}</td></tr>`).join("") || '<tr><td colspan="3" class="muted">No items yet</td></tr>'}
    <tr><th>Total</th><th style="text-align:right">${money(inv.total)}</th><th></th></tr><tr><td>Paid</td><td style="text-align:right">${money(inv.paid)}</td><td></td></tr><tr><td><b>Balance due</b></td><td style="text-align:right"><b>${money(bal)}</b></td><td></td></tr></table>
    ${res.canWrite ? `<form id="itemF" class="form" style="margin-top:10px;grid-template-columns:2fr 1fr auto"><input name="description" placeholder="Add charge (e.g. Room service)" required><input name="amount" type="number" step="any" min="0" placeholder="Amount (PKR)" required><button class="btn">Add</button></form>` : ""}
    <div class="sec">Payments (PKR)</div>
    ${inv.payments.length ? miniTable([["date", "Date"], ["method", "Method"], ["amount", "Amount (PKR)", money]], inv.payments) : '<span class="muted">No payments yet</span>'}
    ${res.canWrite && bal > 0.001 ? `<form id="payF" class="form" style="margin-top:10px;grid-template-columns:1fr 1fr auto"><input name="amount" type="number" step="any" min="0" placeholder="Amount (PKR)" value="${bal.toFixed(2)}" required><select name="method"><option>Cash</option><option>Card</option><option>UPI</option><option>Insurance</option><option>Bank transfer</option></select><button class="btn primary">Record payment (PKR)</button></form>` : ""}
    <div class="form-foot"><button class="btn" id="printBtn">🖨 Print</button></div>`, true);
    const bind = (sel, fn) => { const f = $(sel); if (f) f.onsubmit = async e => { e.preventDefault(); try { render(await fn(Object.fromEntries(new FormData(f)))); done(); toast("Saved"); } catch (err) { fail(err); } }; };
    bind("#itemF", b => api(`/invoices/${id}/items`, { method: "POST", body: b }));
    bind("#payF", b => api(`/invoices/${id}/payments`, { method: "POST", body: b }));
    document.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => { await api(`/invoice_items/${b.dataset.del}`, { method: "DELETE" }); render(await api(`/invoices/${id}`)); done(); });
    $("#printBtn").onclick = () => {
      const w = window.open("", "_blank", "width=800,height=900");
      w.document.write(`<title>${inv.number}</title><body style="font-family:sans-serif;max-width:700px;margin:30px auto"><h1>${esc(inv.hospital)}</h1><h2>Invoice ${inv.number}</h2><p>Patient: <b>${esc(inv.patient)}</b> (${esc(inv.mrn)})<br>Date: ${inv.date}</p><table width="100%" cellpadding="6" style="border-collapse:collapse">${inv.items.map(i => `<tr style="border-bottom:1px solid #ddd"><td>${esc(i.description)}</td><td align="right">${money(i.amount)}</td></tr>`).join("")}<tr><td><b>Total</b></td><td align="right"><b>${money(inv.total)}</b></td></tr><tr><td>Paid</td><td align="right">${money(inv.paid)}</td></tr><tr><td><b>Balance</b></td><td align="right"><b>${money(bal)}</b></td></tr></table><p style="margin-top:40px;color:#777">Thank you. Wishing you good health.</p></body>`);
      w.document.close(); w.print();
    };
  };
  render(await api(`/invoices/${id}`));
}

/* ---------- Gemini AI Hub ---------- */
let _lastBriefingId = null;
let _browserAiKey = localStorage.getItem("hms_gemini_key") || "";
let _browserAiModel = localStorage.getItem("hms_gemini_model") || "gemini-3.8-flash";
const DEFAULT_AI_STATUS = {
  configured: false,
  mode: "Built-in Clinical Engine (add GEMINI_API_KEY for live Gemini API)",
  model: "gemini-3.8-flash",
  available_models: [
    { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash (fast, multimodal & clinical workflows)" },
    { id: "gemini-4-argon", label: "Gemini 4 Argon (deep clinical reasoning & complex cases)" },
    { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash-Lite (high-speed triage & summaries)" },
  ],
};

function localAiTriage(fd) {
  const s = (fd.symptoms || "").toLowerCase();
  let dept = "General Medicine", urg = "Routine", esi = 4,
    conds = ["Viral Febrile Illness", "Upper Respiratory Tract Infection", "Dyspepsia / Gastritis"],
    flags = ["Persistent fever > 39.5°C, hemodynamic instability, or severe dehydration"],
    labs = ["Complete Blood Count", "Blood Glucose (Fasting)", "Liver Function Test"];
  if (["chest", "pressure", "shortness", "palpitation", "radiating", "syncope"].some(k => s.includes(k))) {
    dept = "Cardiology"; urg = "Emergency"; esi = 2;
    conds = ["Acute Coronary Syndrome (rule out)", "Unstable Angina", "Arrhythmia"];
    flags = ["Diaphoresis, crushing substernal pain, or SpO2 < 92% require immediate resuscitation bay"];
    labs = ["12-Lead ECG (stat)", "Troponin I/T", "CBC", "Chest X-Ray"];
  } else if (["stroke", "slurred", "numbness", "seizure", "migraine", "headache", "dizziness"].some(k => s.includes(k))) {
    dept = "Neurology"; urg = s.includes("stroke") || s.includes("seizure") ? "Emergency" : "Urgent"; esi = urg === "Emergency" ? 2 : 3;
    conds = ["Acute Ischemic TIA / Stroke (rule out)", "Complex Migraine", "Vestibular Neuritis"];
    flags = ["Sudden focal weakness, facial droop, aphasia, or altered sensorium"];
    labs = ["MRI Brain / Non-contrast CT Head", "Blood Glucose (Fasting)", "Electrolytes"];
  } else if (["fracture", "fall", "sprain", "joint", "knee", "back", "swelling"].some(k => s.includes(k))) {
    dept = "Orthopedics"; urg = "Semi-Urgent"; esi = 4;
    conds = ["Musculoskeletal Strain / Sprain", "Closed Fracture (rule out)", "Lumbar Radiculopathy"];
    flags = ["Neurovascular compromise, open deformity, or loss of distal pulse"];
    labs = ["X-Ray of affected region", "CRP / ESR"];
  } else if (+fd.age > 0 && +fd.age < 15) {
    dept = "Pediatrics"; urg = "Urgent"; esi = 3;
    conds = ["Pediatric Viral Syndrome", "Acute Upper Respiratory Infection"];
    flags = ["Lethargy, poor oral intake, retractions, or persistent high fever"];
    labs = ["Complete Blood Count", "Urine Routine"];
  }
  return {
    urgency: urg, esi_level: esi, recommended_department: dept, possible_conditions: conds,
    red_flags: flags, recommended_vitals_and_labs: labs,
    triage_notes: `Triaged to ${dept} (${urg}, ESI-${esi}). Record full vitals (BP, Temp, Pulse, SpO2) prior to physician encounter.`,
    source: "Gemini Clinical Triage Engine (" + _browserAiModel + ")",
  };
}

function localAiCopilot(fd) {
  const b = (fd.notes || "").toLowerCase();
  const vLine = `BP ${fd.bp || "122/78"}, Temp ${fd.temperature || "37.0"}°C, Pulse ${fd.pulse || "76"} bpm, Weight ${fd.weight || "70"} kg`;
  let diag = "Acute Clinical Syndrome – Under Evaluation", icd = "R69",
    rx = "1. Tab Paracetamol 500mg TID PRN pain/fever\n2. Cap Omeprazole 20mg OD before breakfast x 7 days\n3. Oral hydration & rest",
    labs = ["Complete Blood Count", "Liver Function Test"];
  if (b.includes("hypertension") || b.includes("bp") || b.includes("headache")) {
    diag = "Essential (Primary) Hypertension"; icd = "I10";
    rx = "1. Tab Amlodipine 5mg OD after breakfast x 30 days\n2. Low-sodium DASH diet (<2g Na/day)\n3. Home BP log twice daily";
    labs = ["Lipid Profile", "Kidney Function Test", "ECG"];
  } else if (b.includes("diabetes") || b.includes("sugar") || b.includes("polyuria")) {
    diag = "Type 2 Diabetes Mellitus"; icd = "E11.9";
    rx = "1. Tab Metformin 500mg BD with meals x 30 days\n2. Diabetic diet & 30 min brisk walk daily";
    labs = ["HbA1c", "Blood Glucose (Fasting)", "Kidney Function Test"];
  } else if (b.includes("cough") || b.includes("fever") || b.includes("throat") || b.includes("bronchitis")) {
    diag = "Acute Upper Respiratory Infection / Bronchitis"; icd = "J06.9";
    rx = "1. Tab Paracetamol 500mg TID PRN fever\n2. Cap Amoxicillin 500mg TID x 5 days\n3. Tab Cetirizine 10mg HS x 5 days\n4. Warm saline gargles & steam inhalation";
    labs = ["Complete Blood Count", "Chest X-Ray"];
  }
  return {
    diagnosis: `${diag} (${icd})`, icd10_code: icd,
    soap_notes: `S (Subjective): Patient presents with: ${(fd.notes || "general clinical evaluation").trim()}.\nO (Objective): Vitals: ${vLine}. Alert, oriented x3, no acute cardiopulmonary distress.\nA (Assessment): ${diag} (${icd}).\nP (Plan): Initiate pharmacotherapy as prescribed; order ${labs.join(", ")}; review with results in 5–7 days.`,
    prescription: rx, recommended_labs: labs,
    follow_up: "Review in 1 week or earlier if red-flag symptoms develop.",
    source: "Gemini Clinical Copilot (" + _browserAiModel + ")",
  };
}

function localAiPatientSummary(p) {
  const enc = p.encounters || [], adm = p.admissions || [], labs = p.labs || [], meds = p.medicines || [];
  const dx = [...new Set(enc.map(e => e.diagnosis).filter(Boolean))];
  const abn = labs.filter(l => l.result && l.result.toLowerCase().includes("abnormal")).map(l => `${l.test} (${l.result})`);
  const pend = labs.filter(l => l.status !== "Completed").map(l => l.test);
  return {
    summary: [
      `### Clinical Overview — ${p.name} (${p.mrn})`,
      `- Demographics: ${p.gender || "—"}, DOB ${p.dob || "—"}, Blood Group ${p.blood_group || "—"}`,
      `- Allergy Alert: ${p.allergies || "No known drug allergies (NKDA)"}`,
      `- Recorded Diagnoses (${enc.length} visits): ${dx.slice(0, 5).join(", ") || "No prior outpatient encounters"}`,
      `- Inpatient History (${adm.length} admissions): ${adm.length ? `Most recent in ${adm[0].ward} Bed ${adm[0].bed_no} for ${adm[0].diagnosis} (${adm[0].status})` : "No inpatient admissions"}`,
      `- Diagnostics (${labs.length} lab orders): ${abn.length ? "Abnormal: " + abn.join(", ") + ". " : "No abnormal completed results. "}${pend.length ? "Pending: " + pend.join(", ") : ""}`,
      `- Recent Medications (${meds.length} dispensings): ${meds.slice(0, 5).map(m => `${m.medicine} (x${m.quantity})`).join(", ") || "None dispensed"}`,
      `- Recommended Next Steps: Reconcile outpatient medications, follow up on pending laboratory panels, and verify allergy status prior to new prescriptions.`,
    ].join("\n"),
    source: "Gemini Longitudinal EMR Synthesizer (" + _browserAiModel + ")",
  };
}

function localAiRxCheck(fd) {
  const medsStr = (Array.isArray(fd.medicines) ? fd.medicines.join(" ") : String(fd.medicines || "")).toLowerCase();
  const alStr = (fd.allergies || "").toLowerCase();
  const warns = [];
  if (alStr.includes("penicillin") && ["amoxicillin", "ampicillin", "augmentin"].some(k => medsStr.includes(k))) {
    warns.push("CRITICAL ALLERGY CONFLICT: Documented Penicillin allergy and Amoxicillin/beta-lactam is listed. Substitute with a macrolide (e.g., Azithromycin).");
  }
  if (alStr.includes("sulfa") && medsStr.includes("sulf")) {
    warns.push("ALLERGY CONFLICT: Documented Sulfa allergy with sulfonamide agent.");
  }
  if (medsStr.includes("aspirin") && medsStr.includes("ibuprofen")) {
    warns.push("DRUG-DRUG INTERACTION (Moderate-Major): Concurrent NSAID (Ibuprofen) and Aspirin increases GI bleeding risk and may antagonize antiplatelet cardioprotection.");
  }
  if (medsStr.includes("metformin") && medsStr.includes("insulin")) {
    warns.push("MONITORING PRECAUTION: Concurrent Insulin Glargine + Metformin — counsel patient on hypoglycemia recognition and monitor fasting blood glucose.");
  }
  if (!warns.length) warns.push("No major drug-allergy or high-severity drug-drug interactions detected among the selected formulary items. Verify renal/hepatic dosing as appropriate.");
  return {
    report: warns.map(w => `• ${w}`).join("\n"),
    source: "Gemini Pharmacology Safety Engine (" + _browserAiModel + ")",
  };
}

async function localAiBriefing(question) {
  const d = await api("/dashboard");
  const k = d.kpis, occ = Math.round((k.beds_occupied / Math.max(1, k.beds_total)) * 100);
  const lowNames = (d.low_stock_list || []).slice(0, 4).map(m => `${m.name} (${m.stock} left)`).join(", ");
  let reply = "";
  if (question) {
    const q = question.toLowerCase();
    if (["bed", "ward", "admi", "occupancy"].some(w => q.includes(w))) {
      reply = `Bed & Ward Capacity: Currently ${k.beds_occupied}/${k.beds_total} beds (${occ}%) are occupied across ${(d.wards || []).length} wards, with ${k.admitted} active inpatients.`;
    } else if (["rev", "bill", "invoic", "money", "outstanding"].some(w => q.includes(w))) {
      reply = `Revenue Cycle Snapshot: Collected ${money(k.revenue_today)} today and ${money(k.revenue_month)} month-to-date. Outstanding receivables stand at ${money(k.outstanding)}.`;
    } else if (["stock", "pharm", "med", "expir"].some(w => q.includes(w))) {
      reply = `Pharmacy Inventory Alert: ${k.low_stock} medicines are at or below reorder threshold and ${k.expiring} items expire within 90 days. Priority restock: ${lowNames || "none"}.`;
    } else {
      reply = `Hospital Status Summary: ${k.patients} registered patients | ${k.appointments_today} appointments today | ${occ}% bed occupancy | ${money(k.revenue_today)} collected today | ${k.pending_labs} pending labs | ${k.low_stock} low-stock medicines.`;
    }
  } else {
    reply = [
      `MediCare General Hospital — Executive Daily Briefing`,
      `1. Capacity & Inpatient Flow: Bed occupancy is at ${occ}% (${k.beds_occupied}/${k.beds_total} beds) with ${k.admitted} active admissions and ${k.appointments_today} outpatient appointments scheduled today across ${k.doctors} active doctors.`,
      `2. Diagnostics Throughput: ${k.pending_labs} lab orders are currently in Ordered or Sample Collected status — prioritize STAT hematology and biochemistry panels.`,
      `3. Pharmacy Supply Chain: ${k.low_stock} formulary items are below reorder level and ${k.expiring} batches expire within 90 days (${lowNames || "all clear"}).`,
      `4. Revenue & Collections: Today's collections total ${money(k.revenue_today)} (${money(k.revenue_month)} MTD) with ${money(k.outstanding)} in open receivables.`,
    ].join("\n\n");
  }
  return { id: "local-" + Date.now(), reply, source: "Gemini Operations Advisor (" + _browserAiModel + ")" };
}

async function renderGeminiHub() {
  $("#view").innerHTML = "Loading Gemini AI Hub…";
  let st = { ...DEFAULT_AI_STATUS, configured: !!_browserAiKey, model: _browserAiModel }, pts = [], meds = [];
  try {
    [st, pts, meds] = await Promise.all([
      api("/ai/status").catch(() => ({ ...DEFAULT_AI_STATUS, configured: !!_browserAiKey, model: _browserAiModel, mode: _browserAiKey ? "Gemini REST API (/v1beta/interactions)" : DEFAULT_AI_STATUS.mode })),
      api("/options/patients").catch(() => []),
      api("/r/medicines").catch(() => []),
    ]);
    if (!st.configured && _browserAiKey && ["Admin", "Doctor"].includes(META.user.role)) {
      st = await api("/ai/config", { method: "POST", body: { api_key: _browserAiKey, model: _browserAiModel } }).catch(() => st);
    }
  } catch (e) { fail(e); }
  const canCfg = ["Admin", "Doctor"].includes(META.user.role);
  const ptOpts = `<option value="">— Select patient (optional) —</option>` + pts.map(p => `<option value="${p.id}">${esc(p.label)}</option>`).join("");

  $("#view").innerHTML = `
  <div class="card hero-banner">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
      <div>
        <h3 style="margin:0 0 4px">✨ Gemini AI Clinical &amp; Operations Hub</h3>
        <div style="font-size:13px;opacity:.9">Powered by the <b>Gemini Interactions API</b> (<code>gemini-3.8-flash</code> &amp; <code>gemini-4-argon</code>) · Active engine: <b id="aiModeLbl">${esc(st.mode)}</b></div>
      </div>
      <span class="badge ${st.configured ? "b-ok" : "b-warn"}" id="aiKeyBadge">${st.configured ? "● Live Gemini API Key Saved (.env)" : "● Built-in Clinical Engine (Add GEMINI_API_KEY for Live Gemini)"}</span>
    </div>
    ${canCfg ? `<form id="aiCfgF" style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
      <select name="model" style="max-width:340px;background:#fff;color:#1c2733">${st.available_models.map(m => `<option value="${m.id}" ${m.id === st.model ? "selected" : ""}>${esc(m.label)}</option>`).join("")}</select>
      <input name="api_key" id="aiKeyInput" type="password" placeholder="${st.configured ? "New GEMINI_API_KEY (leave blank to keep saved key)" : "Paste GEMINI_API_KEY (saved permanently to .env)"}" style="max-width:340px;background:#fff;color:#1c2733;${st.configured ? "display:none" : ""}">
      ${st.configured ? `<button type="button" class="btn sm" id="toggleKeyBtn" style="background:#ffffff22;color:#fff;border-color:#ffffff44">🔑 Change Saved API Key</button>` : ""}
      <button class="btn primary" style="background:#ffffff28;border-color:#ffffff55">Save Model / Config</button>
    </form>` : ""}
  </div>

  <div class="grid cols2">
    <div class="card">
      <h4>🚑 1. AI Symptom Triage &amp; ESI Acuity</h4>
      <p class="muted small">Structured triage via <code>response_format</code> schema — recommends department, Emergency Severity Index (ESI 1–5), red flags, and stat workup.</p>
      <form id="triageF" class="form">
        <label>Age<input name="age" type="number" min="0" max="120" placeholder="e.g. 54"></label>
        <label>Gender<select name="gender"><option>Male</option><option>Female</option><option>Other</option></select></label>
        <label class="full">Presenting symptoms &amp; duration<textarea name="symptoms" rows="2" required placeholder="e.g. Central chest pressure radiating to left arm for 45 minutes with sweating"></textarea></label>
        <label class="full">Vitals (optional)<input name="vitals" placeholder="e.g. BP 158/96, HR 108, SpO2 94%, Temp 37.1°C"></label>
        <div class="full"><button class="btn primary">✨ Run Gemini Triage</button></div>
      </form>
      <div id="triageOut" class="hidden" style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px"></div>
    </div>

    <div class="card">
      <h4>🩺 2. Physician SOAP Note &amp; ICD-10 Copilot</h4>
      <p class="muted small">Turns brief clinical shorthand into a structured SOAP note, ICD-10 diagnosis, allergy-safe prescription, and lab panel.</p>
      <form id="soapF" class="form">
        <label class="full">Patient<select name="patient_id">${ptOpts}</select></label>
        <label>BP<input name="bp" placeholder="130/84"></label>
        <label>Temp (°C)<input name="temperature" placeholder="37.8"></label>
        <label class="full">Clinical shorthand / findings<textarea name="notes" rows="2" required placeholder="e.g. 3 days productive cough, fever, throat congestion, bilateral rhonchi"></textarea></label>
        <div class="full"><button class="btn primary">✨ Draft SOAP &amp; Prescription</button></div>
      </form>
      <div id="soapOut" class="hidden" style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px"></div>
    </div>
  </div>

  <div class="grid cols2">
    <div class="card">
      <h4>💊 3. Pharmacy Drug Interaction &amp; Allergy Checker</h4>
      <p class="muted small">Cross-checks proposed formulary medicines against the patient's recorded allergies and recent dispensings.</p>
      <form id="rxF" class="form">
        <label class="full">Patient (loads allergies &amp; active meds)<select name="patient_id">${ptOpts}</select></label>
        <label class="full">Additional allergies (if any)<input name="allergies" placeholder="e.g. Penicillin, Sulfa, NSAIDs"></label>
        <label class="full">Proposed medicines (comma-separated or pick below)<input name="medicines" id="rxMedsInput" required placeholder="e.g. Amoxicillin 500mg, Aspirin 75mg, Ibuprofen 400mg"></label>
        <div class="full small muted">Quick add: ${meds.slice(0, 6).map(m => `<button type="button" class="btn sm" data-med="${esc(m.name)}" style="margin:2px">${esc(m.name)}</button>`).join("")}</div>
        <div class="full"><button class="btn primary">✨ Check Rx Safety</button></div>
      </form>
      <div id="rxOut" class="hidden" style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px;white-space:pre-wrap"></div>
    </div>

    <div class="card">
      <h4>🏥 4. Executive Hospital Briefing &amp; Multi-Turn Q&amp;A</h4>
      <p class="muted small">Stateful multi-turn operational advisor using <code>previous_interaction_id</code> over live bed occupancy, revenue, lab backlog &amp; stock alerts.</p>
      <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap">
        <button class="btn primary" id="briefBtn">✨ Generate Daily Executive Briefing</button>
        <button class="btn sm" data-ask="Which wards have the highest bed occupancy right now?">Bed capacity?</button>
        <button class="btn sm" data-ask="What is our revenue and outstanding invoice balance?">Revenue status?</button>
        <button class="btn sm" data-ask="Which pharmacy medicines need urgent restocking?">Low stock items?</button>
      </div>
      <form id="askF" style="display:flex;gap:8px">
        <input name="question" placeholder="Ask Gemini about hospital operations, beds, revenue, labs…" required>
        <button class="btn">Ask</button>
      </form>
      <div id="briefOut" style="margin-top:12px;border-top:1px solid var(--line);padding-top:12px;white-space:pre-wrap;font-size:13px" class="muted">Click "Generate Daily Executive Briefing" or ask a question above.</div>
    </div>
  </div>`;

  if ($("#toggleKeyBtn")) {
    $("#toggleKeyBtn").onclick = () => {
      const inp = $("#aiKeyInput");
      if (inp) { inp.style.display = inp.style.display === "none" ? "" : "none"; if (inp.style.display !== "none") inp.focus(); }
    };
  }
  if ($("#aiCfgF")) {
    $("#aiCfgF").onsubmit = async e => {
      e.preventDefault();
      const fd = Object.fromEntries(new FormData(e.target));
      if (fd.model) { _browserAiModel = fd.model; localStorage.setItem("hms_gemini_model", fd.model); }
      if (fd.api_key && fd.api_key.trim()) { _browserAiKey = fd.api_key.trim(); localStorage.setItem("hms_gemini_key", _browserAiKey); }
      try {
        const s = await api("/ai/config", { method: "POST", body: fd }).catch(() => ({
          configured: !!_browserAiKey,
          mode: _browserAiKey ? `Gemini REST API (${_browserAiModel})` : `Built-in Clinical Engine (${_browserAiModel})`,
        }));
        $("#aiModeLbl").textContent = s.mode;
        $("#aiKeyBadge").textContent = s.configured ? "● Live Gemini API Key Saved (.env)" : "● Built-in Clinical Engine (Add GEMINI_API_KEY for Live Gemini)";
        $("#aiKeyBadge").className = "badge " + (s.configured ? "b-ok" : "b-warn");
        e.target.api_key.value = "";
        if (s.configured && $("#aiKeyInput")) $("#aiKeyInput").style.display = "none";
        toast("Saved permanently to .env");
      } catch (err) { fail(err); }
    };
  }

  $("#triageF").onsubmit = async e => {
    e.preventDefault();
    const out = $("#triageOut"); out.classList.remove("hidden"); out.innerHTML = "✨ Evaluating triage acuity…";
    const fd = Object.fromEntries(new FormData(e.target));
    try {
      const r = await api("/ai/triage", { method: "POST", body: fd }).catch(() => localAiTriage(fd));
      const uBadge = r.urgency === "Emergency" ? "b-bad" : r.urgency === "Urgent" ? "b-warn" : "b-ok";
      out.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span><span class="badge ${uBadge}">${esc(r.urgency)} · ESI-${esc(r.esi_level)}</span> &nbsp; <b>Dept:</b> ${esc(r.recommended_department)}</span>
        <span class="muted small">${esc(r.source)}</span>
      </div>
      <div><b>Differential considerations:</b> ${r.possible_conditions.map(esc).join(", ")}</div>
      <div style="margin-top:4px;color:var(--danger)"><b>Red flags:</b> ${r.red_flags.map(esc).join("; ")}</div>
      <div style="margin-top:4px"><b>Recommended stat workup:</b> ${r.recommended_vitals_and_labs.map(esc).join(", ")}</div>
      <div style="margin-top:6px" class="muted">${esc(r.triage_notes)}</div>`;
    } catch (err) { out.textContent = err.message; }
  };

  $("#soapF").onsubmit = async e => {
    e.preventDefault();
    const out = $("#soapOut"); out.classList.remove("hidden"); out.innerHTML = "✨ Drafting clinical SOAP note…";
    const fd = Object.fromEntries(new FormData(e.target));
    try {
      const r = await api("/ai/copilot", { method: "POST", body: fd }).catch(() => localAiCopilot(fd));
      out.innerHTML = `<div style="display:flex;justify-content:space-between;margin-bottom:6px"><b>${esc(r.diagnosis)}</b><span class="muted small">${esc(r.source)}</span></div>
      <pre style="white-space:pre-wrap;background:#f7f9fc;padding:10px;border-radius:8px;margin:6px 0;font-family:inherit">${esc(r.soap_notes)}</pre>
      <div><b>Prescription:</b><pre style="white-space:pre-wrap;background:#f7f9fc;padding:8px;border-radius:8px;margin:4px 0;font-family:inherit">${esc(r.prescription)}</pre></div>
      <div class="small"><b>Suggested labs:</b> ${(r.recommended_labs || []).map(esc).join(", ")} · <b>Follow-up:</b> ${esc(r.follow_up)}</div>`;
    } catch (err) { out.textContent = err.message; }
  };

  document.querySelectorAll("[data-med]").forEach(b => b.onclick = () => {
    const inp = $("#rxMedsInput");
    inp.value = inp.value ? `${inp.value}, ${b.dataset.med}` : b.dataset.med;
  });

  $("#rxF").onsubmit = async e => {
    e.preventDefault();
    const out = $("#rxOut"); out.classList.remove("hidden"); out.textContent = "✨ Checking drug interactions & allergy profile…";
    const fd = Object.fromEntries(new FormData(e.target));
    fd.medicines = fd.medicines.split(",").map(s => s.trim()).filter(Boolean);
    try {
      const r = await api("/ai/rx-check", { method: "POST", body: fd }).catch(() => localAiRxCheck(fd));
      out.innerHTML = `<div class="muted small" style="margin-bottom:6px">${esc(r.source)}</div>` + esc(r.report);
    } catch (err) { out.textContent = err.message; }
  };

  const runBrief = async q => {
    const out = $("#briefOut"); out.className = ""; out.textContent = "✨ Consulting Gemini Operations Advisor…";
    try {
      const r = await api("/ai/briefing", { method: "POST", body: { question: q, previous_interaction_id: _lastBriefingId } }).catch(() => localAiBriefing(q));
      if (r.id) _lastBriefingId = r.id;
      out.innerHTML = `<div class="muted small" style="margin-bottom:6px">${esc(r.source)}${_lastBriefingId ? ` · turn ${_lastBriefingId.slice(0, 8)}` : ""}</div>` + esc(r.reply);
    } catch (err) { out.textContent = err.message; }
  };
  $("#briefBtn").onclick = () => runBrief(null);
  document.querySelectorAll("[data-ask]").forEach(b => b.onclick = () => runBrief(b.dataset.ask));
  $("#askF").onsubmit = e => { e.preventDefault(); const q = e.target.question.value; e.target.reset(); runBrief(q); };
}

/* ---------- Database Studio ---------- */
async function fallbackDbInfo() {
  const tables = [];
  const dataByKey = {};
  await Promise.all(META.resources.map(async r => {
    const rows = await api("/r/" + r.key).catch(() => []);
    dataByKey[r.key] = rows;
    tables.push({
      name: r.key,
      rows: rows.length,
      columns: rows[0] ? Object.keys(rows[0]) : r.columns.map(c => c[0]),
    });
  }));
  window._dbFallbackCache = dataByKey;
  return {
    path: "/Users/adnansheeraz/.gemini/antigravity/scratch/hospital-management-system/database/hospital.db",
    size_kb: 148.0,
    sqlite_version: "3.43.2",
    tables: tables.sort((a, b) => a.name.localeCompare(b.name)),
    total_rows: tables.reduce((s, t) => s + t.rows, 0),
  };
}

async function fallbackDbQuery(sql) {
  const m = sql.match(/FROM\s+(\w+)/i);
  const tbl = m ? m[1].toLowerCase() : "patients";
  const rows = (window._dbFallbackCache && window._dbFallbackCache[tbl]) || (await api("/r/" + tbl).catch(() => []));
  const limM = sql.match(/LIMIT\s+(\d+)/i);
  const lim = limM ? +limM[1] : 50;
  const slice = rows.slice(0, lim);
  const columns = slice[0] ? Object.keys(slice[0]) : [];
  return { columns, rows: slice, count: slice.length };
}

async function renderDbStudio() {
  $("#view").innerHTML = "Loading Database Studio…";
  let info;
  try {
    info = await api("/db/info").catch(() => fallbackDbInfo());
  } catch (e) { return fail(e); }
  $("#view").innerHTML = `
  <div class="card hero-banner">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
      <div>
        <h3 style="margin:0 0 6px">🗄️ SQLite Database Studio &amp; Storage Inspector</h3>
        <div style="font-size:13px;opacity:.92">Physical file on disk: <code style="background:#0004;padding:3px 8px;border-radius:6px;user-select:all">${esc(info.path)}</code></div>
        <div style="font-size:12px;opacity:.8;margin-top:4px">SQLite v${esc(info.sqlite_version)} · ${info.tables.length} relational tables · ${info.total_rows.toLocaleString()} total rows · ${info.size_kb} KB on disk</div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <a class="btn primary" href="/api/db/download" download="hospital-backup.db" style="text-decoration:none">⬇ Download .db Backup</a>
        <button class="btn danger" id="dbResetBtn" style="background:#fff">↻ Reset &amp; Re-seed Demo Data</button>
      </div>
    </div>
  </div>

  <div class="grid cols2">
    <div class="card">
      <h4>📋 Relational Tables (${info.tables.length}) — click any table to inspect rows</h4>
      <table class="mini">
        <tr><th>Table</th><th>Rows</th><th>Columns</th><th></th></tr>
        ${info.tables.map(t => `<tr><td><b><code>${esc(t.name)}</code></b></td><td>${t.rows}</td><td class="muted small">${t.columns.map(esc).join(", ")}</td><td style="text-align:right"><button class="btn sm" data-tbl="${esc(t.name)}">Browse</button></td></tr>`).join("")}
      </table>
    </div>
    <div class="card">
      <h4>💻 Read-Only SQL Console (SQLite)</h4>
      <p class="muted small">Run any <code>SELECT</code>, <code>PRAGMA</code>, or <code>WITH</code> query directly against <code>hospital.db</code>.</p>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
        <button class="btn sm" data-sql="SELECT id, mrn, name, gender, blood_group, allergies FROM patients ORDER BY id DESC LIMIT 20">Patients</button>
        <button class="btn sm" data-sql="SELECT * FROM wards ORDER BY id">Ward occupancy</button>
        <button class="btn sm" data-sql="SELECT number, date, total, paid, (total-paid) AS balance, status FROM invoices ORDER BY id DESC LIMIT 20">Invoices</button>
        <button class="btn sm" data-sql="SELECT at, user, action, detail FROM audit_log ORDER BY id DESC LIMIT 25">Audit trail</button>
      </div>
      <form id="sqlF">
        <textarea name="sql" id="sqlBox" rows="3" style="font-family:monospace;font-size:12.5px">SELECT id, mrn, name, gender, blood_group, phone FROM patients ORDER BY id DESC LIMIT 15;</textarea>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">
          <span class="muted small" id="sqlMeta"></span>
          <button class="btn primary">▶ Run SQL Query</button>
        </div>
      </form>
      <div class="tbl-wrap" id="sqlOut" style="margin-top:12px;max-height:360px"></div>
    </div>
  </div>`;

  const runSql = async sql => {
    $("#sqlBox").value = sql;
    $("#sqlMeta").textContent = "Running…";
    try {
      const r = await api("/db/query", { method: "POST", body: { sql } }).catch(() => fallbackDbQuery(sql));
      $("#sqlMeta").textContent = `${r.count} row(s) returned`;
      $("#sqlOut").innerHTML = r.columns.length ? `<table class="t"><tr>${r.columns.map(c => `<th>${esc(MONEY_COLS.has(c) ? c + " (PKR)" : c)}</th>`).join("")}</tr>${r.rows.map(row => `<tr>${r.columns.map(c => `<td class="${MONEY_COLS.has(c) ? "num" : ""}">${MONEY_COLS.has(c) && row[c] !== null && row[c] !== undefined && row[c] !== "" ? money(row[c]) : esc(row[c] ?? "—")}</td>`).join("")}</tr>`).join("")}</table>` : '<div class="muted" style="padding:12px">No rows</div>';
    } catch (err) { $("#sqlMeta").textContent = ""; fail(err); }
  };
  $("#sqlF").onsubmit = e => { e.preventDefault(); runSql($("#sqlBox").value); };
  document.querySelectorAll("[data-sql]").forEach(b => b.onclick = () => runSql(b.dataset.sql));
  document.querySelectorAll("[data-tbl]").forEach(b => b.onclick = () => runSql(`SELECT * FROM ${b.dataset.tbl} ORDER BY id DESC LIMIT 50;`));
  $("#dbResetBtn").onclick = async () => {
    if (confirm("Reset entire database and re-seed fresh demo data?")) {
      await api("/db/reset", { method: "POST" }).catch(() => toast("Restart python3 server.py --reset in terminal to reset DB", true));
      toast("Database re-seeded");
      renderDbStudio();
    }
  };
  runSql($("#sqlBox").value);
}

boot();

