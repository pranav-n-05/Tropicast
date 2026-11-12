/* Tropicast dashboard (vanilla JS, Leaflet, Plotly). Talks to /api/v1. */
"use strict";
const API = "/api/v1";
const CAT_COLORS = { LOW: "#6e7b8b", D: "#7cc4f5", DD: "#4aa3df", CS: "#7ee787", SCS: "#f6e05e", VSCS: "#f6ad55",
  ESCS: "#f56565", SuCS: "#d53f8c", UNK: "#8b98a8" };
const CAT_ORDER = ["D", "DD", "CS", "SCS", "VSCS", "ESCS", "SuCS"];
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtT = (iso) => iso ? new Date(iso).toISOString().replace("T", " ").slice(0, 16) + "Z" : "–";

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    let d = r.statusText;
    try { d = (await r.json()).detail || d; } catch (_) {}
    throw new Error(`${r.status}: ${d}`);
  }
  return r.json();
}

/* ---------- map ---------- */
const map = L.map("map", { worldCopyJump: true, zoomSnap: 0.5 }).setView([16, 75], 4.5);
L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
  attribution: "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors", maxZoom: 10,
}).addTo(map);
L.rectangle([[0, 40], [30, 100]], { color: "#58a6ff", weight: 1, dashArray: "4 6", fill: false, interactive: false })
  .bindTooltip("v1 domain: 0–30°N, 40–100°E").addTo(map);
const trackLayer = L.layerGroup().addTo(map);
const fcLayer = L.layerGroup().addTo(map);
$("#cat-legend").innerHTML = CAT_ORDER.map((c) => `<span style="background:${CAT_COLORS[c]}">${c}</span>`).join("");

/* ---------- tabs ---------- */
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("on", x === b));
  document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("on", p.id === "tab-" + b.dataset.tab));
  if (b.dataset.tab === "models") loadModels();
  if (b.dataset.tab === "sources") loadSources();
}));

/* ---------- health ---------- */
async function loadHealth() {
  const el = $("#health");
  try {
    const h = await api("/health");
    el.textContent = h.status === "ok" ? `API ok · v${h.version}` : `degraded (data:${h.data_built} models:${h.models_trained})`;
    el.className = "status " + (h.status === "ok" ? "ok" : "bad");
  } catch (e) { el.textContent = "API unreachable"; el.className = "status bad"; }
}

/* ---------- lists ---------- */
function storeItem(s, extra) {
  const li = document.createElement("li");
  li.dataset.sid = s.sid;
  li.innerHTML = `<div><div class="nm">${esc(s.name)}</div><div class="meta">${esc(s.sid)} · ${esc(extra)}</div></div>`;
  li.addEventListener("click", () => selectStorm(s.sid));
  return li;
}

async function loadActive() {
  const ul = $("#active-list");
  ul.innerHTML = "";
  try {
    const ns = await api("/notifications?limit=5");
    $("#notes").innerHTML = ns.length ? "<h3>Notifications</h3>" + ns.map((n) => `<div class="src"><b>${esc(n.kind)}</b> · <span class="meta">${fmtT(n.at)}</span><br>${esc(n.message)}</div>`).join("") : "";
  } catch (_) {}
  try {
    const r = await api("/active");
    $("#active-note").textContent = r.note;
    if (!r.data.length) ul.innerHTML = `<li class="meta">No systems in the latest data window.</li>`;
    r.data.forEach((a) => {
      const li = storeItem(a, `last obs ${fmtT(a.freshness.last_observation_utc)} (${a.freshness.age_hours} h ago)`);
      li.insertAdjacentHTML("beforeend", `<span class="pill fresh-${a.freshness.status}">${a.freshness.status.replace("_", " ")}</span>`);
      ul.appendChild(li);
    });
  } catch (e) { ul.innerHTML = `<li class="meta">${esc(e.message)}</li>`; }
}

let searchTimer;
async function loadStorms() {
  const ul = $("#storm-list");
  const qs = new URLSearchParams({ season_from: $("#from").value, season_to: $("#to").value, min_wind: $("#minw").value, limit: 400 });
  if ($("#q").value.trim()) qs.set("q", $("#q").value.trim());
  try {
    const r = await api("/storms?" + qs);
    ul.innerHTML = "";
    r.data.forEach((s) => {
      const li = storeItem(s, `${s.season} · ${s.subbasin} · peak ${s.peak_wind_kt ?? "–"} kt (${s.agencies || "no wind"})`);
      if (s.peak_category) li.insertAdjacentHTML("beforeend", `<span class="pill" style="background:${CAT_COLORS[s.peak_category]}">${s.peak_category}</span>`);
      ul.appendChild(li);
    });
    if (!r.data.length) ul.innerHTML = `<li class="meta">No storms match.</li>`;
  } catch (e) { ul.innerHTML = `<li class="meta">${esc(e.message)}</li>`; }
}
["#q", "#from", "#to", "#minw"].forEach((s) => $(s).addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadStorms, 250); }));

/* ---------- storm detail ---------- */
let current = null;

async function selectStorm(sid) {
  document.querySelectorAll(".list li").forEach((li) => li.classList.toggle("sel", li.dataset.sid === sid));
  const d = $("#detail");
  d.innerHTML = `<div class="empty">Loading ${esc(sid)}…</div>`;
  let r;
  try { r = await api(`/storms/${encodeURIComponent(sid)}`); } catch (e) { d.innerHTML = `<div class="warn">${esc(e.message)}</div>`; return; }
  current = r;
  drawTrack(r.data);
  const issuable = r.data.filter((p) => p.wind_kt != null && new Date(p.time).getUTCHours() % 6 === 0);
  const prov = r.product === "PROVISIONAL_TRACK";
  const agencies = [...new Set(r.data.map((p) => p.agency).filter((a) => a !== "none"))];
  d.innerHTML = `
    <h2>${esc(r.name)} <span class="meta">${esc(sid)}</span></h2>
    <div><span class="tag ${prov ? "prov" : "obs"}">${prov ? "PROVISIONAL TRACK" : "BEST TRACK"}</span>
      <span class="pill fresh-${r.freshness.status}">${r.freshness.status.replace("_", " ")}</span></div>
    <dl class="kv" style="margin-top:8px">
      <dt>Observed</dt><dd>${fmtT(r.data[0].time)} → ${fmtT(r.data.at(-1).time)}</dd>
      <dt>Agencies</dt><dd>${agencies.map((a) => a === "newdelhi" ? "RSMC New Delhi (3-min)" : a === "usa" ? "USA/JTWC (1-min)" : a).join(", ") || "positions only"}</dd>
      <dt>Data</dt><dd>${esc(r.data_version)}</dd>
    </dl>
    <div id="intensity-chart" class="chart"></div>
    <h3>Experimental forecast <span class="tag ai">AI</span></h3>
    ${issuable.length ? `<div class="slider"><span class="meta">issue</span>
      <input id="issue" type="range" min="0" max="${issuable.length - 1}" value="${defaultIssue(issuable, r.freshness)}" aria-label="forecast issue time" />
      <span id="issue-lbl" class="meta"></span></div><div id="fc"></div>`
      : `<div class="warn">No synoptic observations with intensity — forecast unavailable.</div>`}
    <h3>Coastal exposure <span class="tag ai">EXPERIMENTAL</span></h3><div id="exposure" class="meta">select an issue time…</div>
    <h3>Satellite IR · CNN estimate · Grad-CAM <span class="tag obs">RESEARCH</span></h3><div id="sat" class="meta">loading…</div>`;
  drawIntensity(r.data, null);
  if (!issuable.length) loadSatellite(sid, null);
  if (issuable.length) {
    const s = $("#issue");
    const go = () => { $("#issue-lbl").textContent = fmtT(issuable[s.value].time); loadForecast(sid, issuable[s.value].time); };
    let t; s.addEventListener("input", () => { $("#issue-lbl").textContent = fmtT(issuable[s.value].time); clearTimeout(t); t = setTimeout(go, 200); });
    go();
  }
}

/* live systems: latest issue; archives: last issue that still has 72 h of verification */
function defaultIssue(issuable, fresh) {
  if (fresh.status !== "archive") return issuable.length - 1;
  const end = new Date(issuable.at(-1).time).getTime() - 72 * 3600e3;
  let idx = 0;
  issuable.forEach((p, i) => { if (new Date(p.time).getTime() <= end) idx = i; });
  return idx;
}

function drawTrack(pts) {
  trackLayer.clearLayers(); fcLayer.clearLayers();
  const ll = [];
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1], b = pts[i];
    L.polyline([[a.lat, a.lon], [b.lat, b.lon]], { color: CAT_COLORS[b.category || "UNK"], weight: 3,
      dashArray: b.is_provisional ? "6 6" : null, opacity: 0.95 }).addTo(trackLayer);
  }
  pts.forEach((p) => {
    ll.push([p.lat, p.lon]);
    L.circleMarker([p.lat, p.lon], { radius: 3, color: CAT_COLORS[p.category || "UNK"], fillOpacity: 1, weight: 1 })
      .bindTooltip(`<b>${fmtT(p.time)}</b><br>${p.lat.toFixed(1)}°N ${p.lon.toFixed(1)}°E<br>` +
        `${p.wind_kt ?? "–"} kt ${p.agency !== "none" ? `(${p.agency}, ${p.wind_avg_min}-min)` : ""}<br>` +
        `${p.pres_hpa ? p.pres_hpa + " hPa" : ""} ${p.category ? "· " + p.category : ""}`).addTo(trackLayer);
  });
  if (ll.length) map.fitBounds(L.latLngBounds(ll).pad(0.6), { maxZoom: 6 });
}

function drawIntensity(pts, fc) {
  const obs = pts.filter((p) => p.wind_kt != null);
  const traces = [{ x: obs.map((p) => p.time), y: obs.map((p) => p.wind_kt), name: "observed", mode: "lines+markers",
    line: { color: "#e6edf3", width: 2 }, marker: { size: 3 } }];
  const shapes = [];
  if (fc) {
    const x = [fc.issue_time, ...fc.leads.map((l) => l.valid_time)];
    const lo = [fc.initial.wind_kt, ...fc.leads.map((l) => l.wind_kt_90[0])];
    const hi = [fc.initial.wind_kt, ...fc.leads.map((l) => l.wind_kt_90[1])];
    traces.push({ x: [...x, ...x.slice().reverse()], y: [...hi, ...lo.slice().reverse()], fill: "toself",
      fillcolor: "rgba(255,159,67,.18)", line: { width: 0 }, mode: "lines", name: "90 % interval", hoverinfo: "skip" });
    traces.push({ x, y: [fc.initial.wind_kt, ...fc.leads.map((l) => l.wind_kt)], name: "AI median", mode: "lines+markers",
      line: { color: "#ff9f43", dash: "dot", width: 2 } });
    shapes.push({ type: "line", x0: fc.issue_time, x1: fc.issue_time, yref: "paper", y0: 0, y1: 1, line: { color: "#58a6ff", width: 1, dash: "dash" } });
  }
  [17, 28, 34, 48, 64, 90, 120].forEach((v, i) => shapes.push({ type: "line", xref: "paper", x0: 0, x1: 1, y0: v, y1: v,
    line: { color: CAT_COLORS[CAT_ORDER[i]], width: 0.6, dash: "dot" } }));
  Plotly.react("intensity-chart", traces, {
    margin: { l: 38, r: 8, t: 8, b: 30 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#8b98a8", size: 10 }, showlegend: true, legend: { orientation: "h", y: 1.15 },
    yaxis: { title: "kt", gridcolor: "#2a3442", rangemode: "tozero" }, xaxis: { gridcolor: "#2a3442" }, shapes,
  }, { displayModeBar: false, responsive: true });
}

async function loadForecast(sid, issueTime) {
  const box = $("#fc");
  fcLayer.clearLayers();
  box.innerHTML = `<div class="meta">computing…</div>`;
  let f;
  try { f = await api(`/storms/${encodeURIComponent(sid)}/forecast?issue_time=${encodeURIComponent(issueTime)}`); }
  catch (e) { box.innerHTML = `<div class="warn">${esc(e.message)}</div>`; drawIntensity(current.data, null); return; }
  // cones (outer first), median track, verification
  f.leads.slice().reverse().forEach((l) => L.polygon(l.cone_67, { color: "#ff9f43", weight: 0.6, fillColor: "#ff9f43", fillOpacity: 0.1 }).addTo(fcLayer));
  const line = [[f.initial.lat, f.initial.lon], ...f.leads.map((l) => [l.lat, l.lon])];
  L.polyline(line, { color: "#ff9f43", weight: 3, dashArray: "2 6" }).addTo(fcLayer);
  f.leads.forEach((l) => L.circleMarker([l.lat, l.lon], { radius: 4, color: "#ff9f43", fillOpacity: 1 })
    .bindTooltip(`<b>AI +${l.lead_h} h</b> ${fmtT(l.valid_time)}<br>${l.wind_kt} kt (90 %: ${l.wind_kt_90[0]}–${l.wind_kt_90[1]})<br>` +
      `67 % radius ${l.track_radius_km_67} km · 90 % ${l.track_radius_km_90} km`).addTo(fcLayer));
  f.verification.forEach((v) => L.circleMarker([v.lat, v.lon], { radius: 5, color: "#fff", weight: 2, fill: false })
    .bindTooltip(`Observed +${v.lead_h} h${v.wind_kt != null ? ` · ${v.wind_kt} kt` : ""}`).addTo(fcLayer));
  drawIntensity(current.data, f);

  const ver = Object.fromEntries(f.verification.map((v) => [v.lead_h, v]));
  const hav = (a, b) => { const R = 6371, r = Math.PI / 180, dl = (b[0] - a[0]) * r, dn = (b[1] - a[1]) * r;
    const h = Math.sin(dl / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dn / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };
  const rows = f.leads.map((l) => {
    const v = ver[l.lead_h];
    const err = v ? Math.round(hav([l.lat, l.lon], [v.lat, v.lon])) : null;
    return `<tr><td>+${l.lead_h} h</td><td>${l.lat.toFixed(1)}, ${l.lon.toFixed(1)}</td><td>${Math.round(l.track_radius_km_67)}/${Math.round(l.track_radius_km_90)}</td>
      <td>${l.wind_kt} <span class="meta">[${l.wind_kt_90[0]}–${l.wind_kt_90[1]}]</span></td><td>${l.category ? `<span class="pill" style="background:${CAT_COLORS[l.category]}">${l.category}</span>` : "–"}</td>
      <td>${err != null ? err + " km" : "–"}</td></tr>`;
  }).join("");
  const p24 = f.leads.find((l) => l.lead_h === 24);
  const probs = p24 && p24.category_probabilities ? Object.entries(p24.category_probabilities).filter(([, v]) => v >= 0.01)
    .map(([k, v]) => `<span class="pill" style="background:${CAT_COLORS[k] || "#888"}">${k} ${(v * 100).toFixed(0)}%</span>`).join(" ") : "–";
  const ri = f.rapid_intensification;
  box.innerHTML = `
    <div><span class="tag ai">${f.product}</span><span class="tag obs">${f.mode.toUpperCase()}</span></div>
    ${f.input_status.warnings.map((w) => `<div class="warn">${esc(w)}</div>`).join("")}
    <table><thead><tr><th>lead</th><th>position</th><th>r67/r90 km</th><th>wind kt [90 %]</th><th>IMD</th><th>error</th></tr></thead><tbody>${rows}</tbody></table>
    <h3>24 h category probability</h3><div>${probs}</div>
    <h3>Rapid intensification <span class="tag ai">EXPERIMENTAL</span></h3>
    <div class="kv"><dt>P(RI)</dt><dd>${ri.probability != null ? (ri.probability * 100).toFixed(1) + " %" : "withheld (non-IMD winds)"}</dd>
      <dt>Climatology</dt><dd>${(ri.climatological_rate * 100).toFixed(1)} %</dd><dt>Status</dt><dd>${esc(ri.status)}</dd><dt>Definition</dt><dd>${esc(ri.definition)}</dd></dl>
    <h3>Provenance</h3>
    <dl class="kv"><dt>Issue</dt><dd>${fmtT(f.issue_time)}</dd><dt>Processed</dt><dd>${fmtT(f.processed_at)}</dd>
      <dt>Track model</dt><dd><code>${esc(f.model.track)}</code></dd><dt>Intensity</dt><dd><code>${esc(f.model.intensity)}</code></dd>
      <dt>Uncertainty</dt><dd>${esc(f.uncertainty_method)}</dd><dt>Inputs</dt><dd>best-track history only; satellite: ${f.input_status.satellite}; environment: ${f.input_status.environment}</dd></dl>
    <p class="hint">${esc(f.disclaimer)}</p>`;
  loadExposure(sid, f.issue_time);
  loadSatellite(sid, f.issue_time);  // keep imagery in sync with the forecast issue time
}

let expTimer;
function loadExposure(sid, issueTime) {
  clearTimeout(expTimer);
  const el = $("#exposure");
  el.innerHTML = "simulating member tracks…";
  expTimer = setTimeout(async () => {
    let e;
    try { e = await api(`/storms/${encodeURIComponent(sid)}/exposure?issue_time=${encodeURIComponent(issueTime)}&members=300`); }
    catch (err) { el.innerHTML = `<div class="warn">${esc(err.message)}</div>`; return; }
    const bar = (p) => `<span style="display:inline-block;height:8px;width:${Math.round(p * 120)}px;background:#ff9f43;border-radius:2px;vertical-align:middle"></span>`;
    el.innerHTML = e.starts_over_land ? `<div class="meta">Centre already over land at issue time.</div>` : `
      <dl class="kv"><dt>P(landfall ≤ 72 h)</dt><dd><b>${(e.p_landfall_72h * 100).toFixed(0)} %</b></dd>
      ${e.landfall_time_h ? `<dt>Landfall time</dt><dd>+${e.landfall_time_h.median} h (10–90 %: ${e.landfall_time_h.p10}–${e.landfall_time_h.p90} h)</dd>` : ""}</dl>
      <table><thead><tr><th>likely landfall region</th><th>P</th><th></th></tr></thead><tbody>
      ${e.landfall_regions.map((r) => `<tr><td>${esc(r.region)}, ${esc(r.country)}</td><td>${(r.probability * 100).toFixed(0)} %</td><td>${bar(r.probability)}</td></tr>`).join("") || "<tr><td colspan=3>no landfall in members</td></tr>"}</tbody></table>
      <table style="margin-top:6px"><thead><tr><th>centre within ${e.strike_radius_km} km of</th><th>P</th><th></th></tr></thead><tbody>
      ${e.strike_probability.slice(0, 6).map((r) => `<tr><td>${esc(r.region)}, ${esc(r.country)}</td><td>${(r.probability * 100).toFixed(0)} %</td><td>${bar(r.probability)}</td></tr>`).join("")}</tbody></table>
      <p class="hint">${esc(e.limitations)} ${e.members} Monte-Carlo tracks from calibrated cones. Verified skill: Models tab.</p>`;
  }, 300);
}

/* ---------- satellite panel ---------- */
function btColor(k) {  // enhanced IR: warm=grey, cold tops coloured
  if (k > 273) { const g = Math.max(30, Math.min(200, 200 - (k - 273) * 4)); return [g, g, g]; }
  const t = Math.min(1, (273 - k) / 93);  // 273 K -> 180 K
  const stops = [[0, [200, 200, 200]], [0.35, [60, 120, 220]], [0.55, [60, 200, 120]], [0.7, [250, 220, 60]], [0.85, [240, 80, 40]], [1, [255, 255, 255]]];
  for (let i = 1; i < stops.length; i++) if (t <= stops[i][0]) {
    const [a, ca] = stops[i - 1], [b, cb] = stops[i], u = (t - a) / (b - a);
    return ca.map((c, j) => Math.round(c + (cb[j] - c) * u));
  }
  return [255, 255, 255];
}

async function loadSatellite(sid, time) {
  const el = $("#sat");
  let p;
  try { p = await api(`/storms/${encodeURIComponent(sid)}/satellite${time ? "?time=" + encodeURIComponent(time) : ""}`); }
  catch (e) { el.innerHTML = `<span class="meta">${esc(e.message)}</span>`; return; }
  const n = p.image_bt_k.length, S = 4;
  el.innerHTML = `
    <div class="slider"><span class="meta">image</span><input id="satt" type="range" min="0" max="${p.available_times.length - 1}"
      value="${p.available_times.indexOf(p.time)}" aria-label="satellite image time"/><span class="meta">${fmtT(p.time)}</span></div>
    <div style="position:relative;width:${n * S}px;height:${n * S}px;margin:6px auto">
      <canvas id="ir" width="${n}" height="${n}" style="width:100%;height:100%;image-rendering:pixelated"></canvas>
      <canvas id="cam" width="${p.gradcam.length}" height="${p.gradcam.length}" style="position:absolute;left:${p.gradcam_offset_px * S}px;top:${p.gradcam_offset_px * S}px;width:${p.gradcam.length * S}px;height:${p.gradcam.length * S}px;opacity:.45;image-rendering:auto"></canvas>
    </div>
    <label class="meta"><input type="checkbox" id="camtoggle" checked/> Grad-CAM overlay</label>
    <dl class="kv"><dt>CNN estimate</dt><dd><b>${p.cnn_wind_kt} kt</b> (90 %: ${p.cnn_wind_kt_90[0]}–${p.cnn_wind_kt_90[1]})</dd>
      <dt>Best track</dt><dd>${p.best_track_wind_kt ?? "–"} kt ${p.best_track_agency ? "(" + esc(p.best_track_agency) + ")" : ""}</dd>
      <dt>Satellite</dt><dd>${esc(p.satellite)} · VZA ${p.vza_deg}° · ${p.pixel_km} km px</dd>
      <dt>Eye contrast</dt><dd>${p.ir_features.ir_eye_contrast ?? "–"} K · cold &lt;220 K within 200 km: ${p.ir_features.ir_frac220_200 != null ? (p.ir_features.ir_frac220_200 * 100).toFixed(0) + " %" : "–"}</dd>
      <dt>ARCHER eye prob.</dt><dd>${p.archer.eye_prob ?? "–"} %</dd></dl>
    <p class="hint">${esc(p.model.note)} ${esc(p.explainability_note)}</p>`;
  const ctx = $("#ir").getContext("2d"), im = ctx.createImageData(n, n);
  p.image_bt_k.forEach((row, y) => row.forEach((k, x) => { const c = btColor(k), o = 4 * (y * n + x); im.data.set([...c, 255], o); }));
  ctx.putImageData(im, 0, 0);
  const m = p.gradcam.length, cx = $("#cam").getContext("2d"), cm = cx.createImageData(m, m);
  p.gradcam.forEach((row, y) => row.forEach((v, x) => { const o = 4 * (y * m + x); cm.data.set([255, Math.round(80 * (1 - v)), 0, Math.round(255 * v)], o); }));
  cx.putImageData(cm, 0, 0);
  $("#camtoggle").addEventListener("change", (e) => { $("#cam").style.display = e.target.checked ? "" : "none"; });
  let t; $("#satt").addEventListener("input", (e) => { clearTimeout(t); const v = p.available_times[e.target.value]; t = setTimeout(() => loadSatellite(sid, v), 250); });
}

/* ---------- models / evaluation ---------- */
async function loadModels() {
  const el = $("#models");
  try {
    const ev = await api("/evaluation");
    const sel = ev.selection, test = ev.results.test;
    const leads = Object.keys(test[sel.track].leads);
    const row = (m, k, R = test) => leads.map((L) => R[m].leads[L][k] ?? "–");
    const tbl = (title, k, models, R = test) => `<h3>${title}</h3><table><thead><tr><th>model</th>${leads.map((l) => `<th>${l}h</th>`).join("")}</tr></thead>
      <tbody>${models.map((m) => `<tr><td>${esc(m)}${m === sel.track && k.startsWith("track") || m === sel.intensity && k.startsWith("wind") ? " ★" : ""}</td>${row(m, k, R).map((v) => `<td>${v}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
    const main = Object.keys(test).filter((m) => !m.includes("["));
    const ri = ev.rapid_intensification.test;
    el.innerHTML = `<p class="hint">Test seasons ${ev.split.test.join("–")} (unseen storms). ★ = selected on validation. Generated ${esc(ev.generated_utc)}. All values computed by the training pipeline.</p>
      ${tbl("Mean track error (km)", "track_err_mean_km", main)}
      ${tbl("Track skill vs persistence (%)", "track_skill_vs_persistence_pct", main.filter((m) => m !== "persistence"))}
      ${tbl("Wind MAE (kt)", "wind_mae_kt", main)}
      ${tbl("90 % track-radius coverage", "track_cov_90", main.filter((m) => m !== "persistence"))}
      ${tbl("Ablation · track error (km)", "track_err_mean_km", ev.ablation_models)}
      <h3>Rapid intensification (test)</h3><table><thead><tr><th>model</th><th>n</th><th>events</th><th>Brier</th><th>BSS</th><th>AUC</th></tr></thead>
      <tbody>${Object.entries(ri).map(([k, r]) => `<tr><td>${k}</td><td>${r.n}</td><td>${r.n_positive}</td><td>${r.brier}</td><td>${r.brier_skill}</td><td>${r.roc_auc}</td></tr>`).join("")}</tbody></table>
      ${tbl("Environment ablation · track km (2019–2021, env available)", "track_err_mean_km", ev.env_ablation_models.filter((m) => ev.results.test_env[m]), ev.results.test_env)}
      ${tbl("Environment ablation · wind MAE kt", "wind_mae_kt", ev.env_ablation_models.filter((m) => ev.results.test_env[m]), ev.results.test_env)}
      <div id="extra-evals" class="meta">loading satellite / landfall / localisation reports…</div>
      <h3>Not yet evaluated</h3>${Object.entries(ev.not_evaluated).map(([k, v]) => `<div class="src"><b>${esc(k)}</b><br>${esc(v)}</div>`).join("")}`;
    loadExtraEvals();
  } catch (e) { el.innerHTML = `<div class="warn">${esc(e.message)}</div>`; }
}

async function loadExtraEvals() {
  const el = $("#extra-evals");
  const get = async (n) => { try { return await api("/evaluation/" + n); } catch (_) { return null; } };
  const [sat, lf, loc] = await Promise.all([get("satellite"), get("landfall"), get("localization")]);
  let h = "";
  if (sat) {
    const cs = sat.estimation.common_subset;
    h += `<h3>Satellite study · intensity estimation (nested CV, ${sat.data.seasons.join("–")})</h3>
      <table><thead><tr><th>configuration</th><th>n</th><th>MAE kt</th><th>RMSE</th></tr></thead><tbody>
      ${Object.entries(cs).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.n}</td><td>${v.mae}</td><td>${v.rmse}</td></tr>`).join("")}</tbody></table>
      <h3>Satellite study · 24 h intensity change</h3><table><thead><tr><th>configuration</th><th>MAE kt</th><th>RMSE</th></tr></thead><tbody>
      ${Object.entries(sat.forecast_dw24).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.mae}</td><td>${v.rmse}</td></tr>`).join("")}</tbody></table>
      <h3>Stage classification (from satellite estimate)</h3><table><thead><tr><th>model</th><th>accuracy</th><th>macro-F1</th></tr></thead><tbody>
      ${Object.entries(sat.stage_classification).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.accuracy}</td><td>${v.macro_f1}</td></tr>`).join("")}</tbody></table>`;
  }
  if (loc) h += `<h3>Centre localisation (test ${loc.test_seasons.join("–")})</h3><table><thead><tr><th>method</th><th>mean km</th><th>median km</th></tr></thead><tbody>
      ${["cnn_heatmap", "baseline_coldest_cloud", "baseline_crop_centre"].map((k) => `<tr><td>${k}</td><td>${loc[k].mean_km}</td><td>${loc[k].median_km}</td></tr>`).join("")}</tbody></table>`;
  if (lf) h += `<h3>72 h landfall probability (test seasons)</h3><dl class="kv"><dt>cases</dt><dd>${lf.n} (${lf.n_positive} landfalls, ${lf.test_storms} storms)</dd>
      <dt>Brier</dt><dd>${lf.brier} (climatology ${lf.brier_climatology})</dd><dt>BSS</dt><dd>${lf.brier_skill}</dd><dt>AUC</dt><dd>${lf.roc_auc}</dd></dl>`;
  el.innerHTML = h || "Additional studies not yet run.";
}

async function loadSources() {
  const el = $("#sources");
  try {
    const r = await api("/sources");
    el.innerHTML = Object.values(r.data).map((s) => `<div class="src"><span class="st ${s.status}">${esc(s.status)}</span><b>${esc(s.name)}</b><br>
      <span class="meta">auth: ${esc(s.auth || "–")}</span><br>
      ${s.last_attempt_at ? `last check ${fmtT(s.last_attempt_at)} → ${esc(s.last_attempt_status)}<br>` : ""}
      ${s.remote_last_modified ? `remote updated ${esc(s.remote_last_modified)} (${s.remote_age_hours} h ago)<br>` : ""}
      ${s.notes ? `<span class="meta">${esc(s.notes)}</span>` : ""}</div>`).join("") +
      `<button id="runp" class="tabs" style="padding:8px;width:100%;cursor:pointer">Run pipeline cycle now</button>`;
    $("#runp").addEventListener("click", async () => { await api("/pipeline/run", { method: "POST" }); setTimeout(() => { loadSources(); loadActive(); }, 4000); });
  } catch (e) { el.innerHTML = `<div class="warn">${esc(e.message)}</div>`; }
}

loadHealth(); loadActive(); loadStorms();
setInterval(() => { loadHealth(); loadActive(); }, 5 * 60 * 1000);
