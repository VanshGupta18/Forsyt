const EVENT_MARKERS = [
  { date: "2008-11-26", label: "26/11" },
  { date: "2019-02-14", label: "Pulwama" },
  { date: "2020-06-15", label: "Galwan" },
];

async function fetchJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function riskClass(value) {
  if (value >= 50) return "risk-high";
  if (value >= 20) return "risk-mid";
  return "risk-low";
}

function setupNav() {
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`screen-${btn.dataset.screen}`).classList.add("active");
      if (btn.dataset.screen === "chart") drawChart();
    });
  });
}

function renderDualSignal(data) {
  const geo = data.geopolitical || {};
  const vol = data.nifty_volatility || {};
  const joint = data.joint_stress || {};
  const analog = data.historical_analog || {};

  document.getElementById("as-of-date").textContent = geo.as_of || "—";
  document.getElementById("stress-score").textContent = joint.stress_score ?? "—";
  document.getElementById("stress-fill").style.width = `${joint.stress_score || 0}%`;
  const badge = document.getElementById("stress-regime");
  badge.textContent = joint.stress_regime || "—";
  badge.className = `badge ${joint.stress_regime || ""}`;
  document.getElementById("stress-narrative").textContent = joint.narrative || "";

  document.getElementById("geo-gpr").textContent = geo.gpr_index ?? "—";
  document.getElementById("geo-regime").textContent = geo.regime ?? "—";
  document.getElementById("geo-change").textContent =
    geo.change_7d_pct != null ? `${geo.change_7d_pct > 0 ? "+" : ""}${geo.change_7d_pct}%` : "—";
  document.getElementById("geo-corridor").textContent = geo.top_corridor || "—";

  document.getElementById("vol-forecast").textContent =
    vol.vol_forecast_5d != null ? `${vol.vol_forecast_5d}%` : "—";
  document.getElementById("vol-regime").textContent = vol.regime ?? "—";
  document.getElementById("vol-prob").textContent =
    vol.high_vol_prob != null ? `${(vol.high_vol_prob * 100).toFixed(1)}%` : "—";
  document.getElementById("vol-trailing").textContent =
    vol.trailing_vol_22d != null ? `${vol.trailing_vol_22d}%` : "—";

  if (analog.sample_days) {
    document.getElementById("analog-line").textContent =
      `Historical analog: on ${analog.sample_days} similar GPR days, NIFTY vol averaged ` +
      `${analog.nifty_vol_median}% and returns ${analog.nifty_return_median}% over next 5 days.`;
  }

  const list = document.getElementById("driving-events");
  list.innerHTML = "";
  (geo.driving_events || []).forEach((ev) => {
    const li = document.createElement("li");
    li.innerHTML = `<a href="${ev.link}" target="_blank" rel="noopener">${ev.title}</a>` +
      `<div class="meta">${ev.source || ""} · ${ev.themes || ""}</div>`;
    list.appendChild(li);
  });

  document.getElementById("disclaimer").textContent = data.disclaimer || "";
}

async function loadHome() {
  const data = await fetchJSON("/api/market/dual-signal?refresh=1");
  renderDualSignal(data);
}

function renderCorridors(payload) {
  document.getElementById("corridor-date").textContent = payload.date ? `As of ${payload.date}` : "";
  const tbody = document.querySelector("#corridor-table tbody");
  tbody.innerHTML = "";
  (payload.corridors || []).forEach((row) => {
    const tr = document.createElement("tr");
    const risk = Number(row.corridor_risk || 0);
    tr.innerHTML = `
      <td>${row.corridor_name || row.corridor}</td>
      <td class="${riskClass(risk)}">${risk.toFixed(1)}</td>
      <td>${Number(row.threat_index || 0).toFixed(1)}</td>
      <td>${Number(row.energy_risk || 0).toFixed(1)}</td>
      <td>${Number(row.goods_risk || 0).toFixed(1)}</td>`;
    tbody.appendChild(tr);
  });
}

async function loadCorridors() {
  const payload = await fetchJSON("/api/corridors");
  renderCorridors(payload);
}

async function loadEvents(theme = "") {
  const qs = new URLSearchParams({ limit: "50" });
  if (theme) qs.set("theme", theme);
  const payload = await fetchJSON(`/api/news/recent?${qs}`);
  const list = document.getElementById("event-feed");
  list.innerHTML = "";
  if (!payload.articles || !payload.articles.length) {
    list.innerHTML = "<li class='meta'>No articles in Postgres yet — run the scrape pipeline.</li>";
    return;
  }
  payload.articles.forEach((ev) => {
    const li = document.createElement("li");
    const themes = ev.nlp_themes || "";
    const when = ev.published_at || ev.scraped_at || "";
    li.innerHTML = `
      <a href="${ev.link}" target="_blank" rel="noopener"><strong>${ev.title}</strong></a>
      <div class="meta">${ev.source || ""} · tier ${ev.tier ?? "—"} · ${when}</div>
      <div class="meta">${themes || "(awaiting NLP tags)"}</div>`;
    list.appendChild(li);
  });
}

let chartHistory = null;

async function drawChart() {
  if (!chartHistory) {
    const payload = await fetchJSON("/api/gpr/history?limit=800");
    chartHistory = payload.history || [];
  }
  const canvas = document.getElementById("dual-chart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  if (!chartHistory.length) {
    ctx.fillStyle = "#8b98a8";
    ctx.fillText("No GPR history available", 20, 40);
    return;
  }

  const gprVals = chartHistory.map((d) => Number(d.gpr_index));
  const minG = Math.min(...gprVals);
  const maxG = Math.max(...gprVals);
  const pad = 40;

  ctx.strokeStyle = "#334155";
  ctx.beginPath();
  ctx.moveTo(pad, h - pad);
  ctx.lineTo(w - pad, h - pad);
  ctx.lineTo(w - pad, pad);
  ctx.stroke();

  ctx.strokeStyle = "#b3202c";
  ctx.lineWidth = 2;
  ctx.beginPath();
  chartHistory.forEach((d, i) => {
    const x = pad + (i / (chartHistory.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((Number(d.gpr_index) - minG) / (maxG - minG || 1)) * (h - 2 * pad);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  EVENT_MARKERS.forEach((marker) => {
    const idx = chartHistory.findIndex((d) => d.date >= marker.date);
    if (idx < 0) return;
    const x = pad + (idx / (chartHistory.length - 1)) * (w - 2 * pad);
    ctx.strokeStyle = "#fbbf24";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, pad);
    ctx.lineTo(x, h - pad);
    ctx.stroke();
    ctx.fillStyle = "#fbbf24";
    ctx.font = "11px sans-serif";
    ctx.fillText(marker.label, x + 4, pad + 14);
  });

  ctx.fillStyle = "#e7ecf3";
  ctx.font = "12px sans-serif";
  ctx.fillText("GPR index", pad, 20);
}

document.getElementById("reload-events").addEventListener("click", () => {
  loadEvents(document.getElementById("theme-filter").value.trim());
});

setupNav();
loadHome();
loadCorridors();
loadEvents();
