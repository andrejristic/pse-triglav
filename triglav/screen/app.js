"use strict";
const T = new URLSearchParams(location.search).get("t") || "";
const H = {"X-Triglav-Token": T, "Content-Type": "application/json"};
let lang = "en";
const shown = {};            // held parts already shown to the operator, by id
const SR = {overview: "Pregled", talk: "Razgovor sa SHARED_LIB", agents: "Agenti i theta (25-35)", inbox: "Inbox",
  talkh: "Pitaj SHARED_LIB svojim riječima. Odgovara samo iz svojih činjenica; sve što nešto mijenja samo predlaže.",
  send: "Pitaj", read: "Pročitano", show: "Prikaži", release: "Pusti", sure: "Sigurno?",
  ours: "naš", colleague: "kolega", stranger: "tuđinac", enemy: "neprijatelj", physician: "Physician",
  watched: "Guardian pored njega", "kept-away": "odvojen", harvested: "požnjeven", intact: "dnevnik netaknut",
  broken: "dnevnik OŠTEĆEN", textbook: "udžbenik zaključan", operator: "operater"};
const t = (k, en) => lang === "sr" && SR[k] ? SR[k] : en;
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const CLS = {enemy: "bad", physician: "bad", watched: "warn", "kept-away": "warn", colleague: "acc", ours: "plain", stranger: "plain", harvested: "plain"};

async function api(path, body) {
  const r = await fetch(path, body ? {method: "POST", headers: H, body: JSON.stringify(body)} : {headers: H});
  return r.json();
}

function agentRow(a) {
  const row = el("div", "row");
  row.append(el("span", "name", a.name));
  const bar = el("div", "bar"); bar.append(el("div", "band"));
  if (a.theta != null) {
    const d = el("div", "dot"); d.style.left = Math.max(0, Math.min(99, a.theta)) + "%";
    d.style.background = a.theta < 25 || a.theta > 35 ? "var(--bad)" : "var(--ok)"; bar.append(d);
  }
  row.append(bar, el("span", "num", a.theta == null ? "-" : a.theta.toFixed(1)));
  row.append(el("span", "pill " + (CLS[a.status] || "plain"), t(a.status, a.status)));
  if ((a.status === "enemy" || a.status === "physician") ) {
    const b = el("button", null, t("release", "Release"));
    b.onclick = () => act({action: "release", who: a.name}, b);
    row.append(b);
  }
  return row;
}

async function act(body, btn) {
  if (btn.dataset.armed !== "1") { btn.dataset.armed = "1"; btn.textContent = t("sure", "Sure?"); return; }
  const out = await api("/api/act", {...body, confirm: true});
  if (out.error) { btn.textContent = out.error; return; }
  if (body.action === "held") { shown[body.q] = out.decoded; btn.replaceWith(el("div", "a", out.decoded)); return; }
  refresh();
}

function inboxItem(i) {
  const d = el("div", "item" + (i.seen ? "" : " new"));
  d.append(el("div", null, i.text));
  const bar = el("div", "row");
  if (!i.seen) { const b = el("button", null, t("read", "Mark read")); b.onclick = () => act({action: "read", id: i.id}, b); bar.append(b); }
  for (const q of i.quarantine) {
    if (shown[q]) { d.append(el("div", "a", shown[q])); continue; }
    const b = el("button", null, t("show", "Show") + " " + q); b.onclick = () => act({action: "held", q}, b); bar.append(b);
  }
  d.append(bar);
  return d;
}

async function refresh() {
  if (document.querySelector('[data-armed="1"]')) return;     // waiting for a confirming click
  const s = await api("/api/state");
  document.getElementById("who").textContent = `installation ${s.installation} · ${t("operator", "operator")} ${s.operator || "-"}${s.rank ? " (rank " + s.rank + ")" : ""}`;
  const log = document.getElementById("log");
  log.textContent = s.log_ok ? t("intact", "log intact") : t("broken", "log BROKEN");
  log.className = "pill " + (s.log_ok ? "ok" : "bad");
  document.getElementById("tb").textContent = s.textbook ? t("textbook", "textbook locked") + " " + s.textbook.slice(0, 8) : "";
  const ag = document.getElementById("agents"); ag.replaceChildren(...s.agents.map(agentRow));
  const ib = document.getElementById("inbox"); ib.replaceChildren(...s.inbox.slice().reverse().map(inboxItem));
}

document.getElementById("ask").onsubmit = async (ev) => {
  ev.preventDefault();
  const q = document.getElementById("q").value.trim();
  if (!q) return;
  const log = document.getElementById("chatlog");
  log.append(el("div", "q", q));
  document.getElementById("q").value = "";
  const out = await api("/api/chat", {q});
  const a = el("div", "a", out.text || out.error);
  if (out.propose) { const b = el("button", null, t("release", "Release") + " " + out.propose.who); b.onclick = () => act(out.propose, b); a.append(el("div", null, ""), b); }
  log.append(a); log.scrollTop = log.scrollHeight;
};

function tab(main) {
  document.getElementById("v-main").classList.toggle("hide", !main);
  document.getElementById("v-chat").classList.toggle("hide", main);
  document.getElementById("t-main").classList.toggle("on", main);
  document.getElementById("t-chat").classList.toggle("on", !main);
}
document.getElementById("t-main").onclick = () => tab(true);
document.getElementById("t-chat").onclick = () => tab(false);
const EN = {};
document.querySelectorAll("[data-i]").forEach(e => EN[e.dataset.i] = e.textContent);
document.getElementById("lang").onclick = (ev) => {
  lang = lang === "en" ? "sr" : "en"; ev.target.textContent = lang === "en" ? "SR" : "EN";
  document.querySelectorAll("[data-i]").forEach(e => e.textContent = t(e.dataset.i, EN[e.dataset.i]));
  refresh();
};
refresh(); setInterval(refresh, 5000);
