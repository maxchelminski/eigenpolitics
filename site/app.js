"use strict";

const $ = (selector) => document.querySelector(selector);
const SVG_NS = "http://www.w3.org/2000/svg";
const palette = { 100: "#528bb0", 200: "#cb785b", 328: "#9a9468", 1: "#9c8259", 9: "#70966c", 13: "#70966c", 22: "#b2934f", 29: "#c5a54f", 37: "#9786ad", 46: "#4e9691", 112: "#778aaf", 370: "#979659", 380: "#b6819d" };
const state = { index: null, data: null, view: "spectral", selected: null, query: "", threshold: 0.8, request: 0, target: null, compare: false, cache: new Map(), pending: new Map(), generation: 0, axes: null };
const metricInfo = {
  fiedler_value: ["How connected is the chamber?", "Lower λ₂ indicates weaker connectivity in this weighted voting graph.", "Normalized Laplacian · λ₂"],
  sweep_conductance: ["Where does the network separate?", "Lower sweep conductance means a smaller cut relative to the smaller group’s volume.", "Fiedler sweep conductance"],
  mean_betweenness: ["How is brokerage distributed?", "Mean shortest-path betweenness in the thresholded voting graph.", "Mean betweenness"],
  gini_betweenness: ["How concentrated is brokerage?", "A higher Gini means more unequal computed brokerage. It is not a direct measure of political power.", "Gini coefficient"],
};

function el(tag, attrs = {}, text = null) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
  if (text !== null) node.textContent = text;
  return node;
}
function html(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function format(value, digits = 3) {
  return Number.isFinite(Number(value)) && value !== null ? Number(value).toFixed(digits) : "—";
}
function number(value) { return Number(value || 0).toLocaleString("en-US"); }
function ordinal(value) { const v = Number(value), t = v % 100; return `${v}${t >= 11 && t <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[v % 10] || "th")}`; }
function period(d) { return `${d.start_year}–${String(d.end_year).slice(-2)}`; }
function partyColor(n) { return palette[n.party_code] || "#87988a"; }
function prettyName(name) {
  if (!name) return "Unknown member";
  const parts = String(name).split(", ");
  if (parts.length < 2) return name;
  const surname = parts[0].toLowerCase().replace(/(^|[-\s])\S/g, (letter) => letter.toUpperCase());
  return `${parts.slice(1).join(", ")} ${surname}`;
}
function dateLabel(value) {
  if (!value) return "unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { $("#toast").hidden = true; }, 6000);
}
async function readJSON(path) {
  const response = await fetch(path, { cache: "no-cache" });
  if (!response.ok) throw new Error(`Could not load ${path} (HTTP ${response.status}).`);
  return response.json();
}
function safeDataPath(value) {
  if (typeof value !== "string" || !/^congresses\/\d+\.json$/.test(value)) throw new Error("The data manifest contains an invalid file path.");
  return `data/${value}`;
}
async function loadCongress(summary) {
  const generation = state.generation, key = `${generation}:${summary.congress}`;
  if (state.cache.has(key)) return state.cache.get(key);
  if (!state.pending.has(key)) {
    const pending = readJSON(safeDataPath(summary.data_file)).then(data => {
      if (!Array.isArray(data.nodes) || !data.nodes.length) throw new Error("The Congress data contains no analyzed members.");
      const result = { ...summary, ...data };
      if (generation === state.generation) state.cache.set(key, result);
      return result;
    }).finally(() => state.pending.delete(key));
    state.pending.set(key, pending);
  }
  return state.pending.get(key);
}
function setFixedAxes(index) {
  const source = index.axis_bounds;
  const valid = (a) => Array.isArray(a) && a.length === 2 && a.every(Number.isFinite) && a[0] < a[1];
  // Unit-normalized eigenvector coordinates and normalized betweenness are
  // bounded by one. The fallback keeps old snapshots usable without rescaling.
  state.axes = {
    x: valid(source?.x) ? [...source.x] : [-1, 1],
    y: valid(source?.y) ? [...source.y] : [-1, 1],
    betweenness: valid(source?.betweenness) ? [...source.betweenness] : [0, 1],
  };
}
function fillTimeline() {
  const entries = state.index.congresses, slider = $("#congress-slider");
  slider.max = entries.length - 1;
  slider.disabled = false;
  $("#congress-dots").style.setProperty("--congress-count", entries.length);
  $("#congress-dots").replaceChildren(...entries.map((d, index) => {
    const dot = html("button", "timeline-dot");
    dot.type = "button";
    dot.dataset.congress = d.congress;
    dot.dataset.index = index;
    dot.title = `${ordinal(d.congress)} · ${period(d)}`;
    dot.setAttribute("aria-label", `${ordinal(d.congress)} Congress, ${period(d)}`);
    dot.tabIndex = -1;
    dot.addEventListener("click", () => selectCongress(d.congress));
    dot.addEventListener("keydown", event => {
      const changes = { ArrowLeft: -1, ArrowRight: 1, Home: -entries.length, End: entries.length };
      if (!(event.key in changes)) return;
      event.preventDefault();
      const position = Math.max(0, Math.min(entries.length - 1, index + changes[event.key]));
      selectCongress(entries[position].congress);
      $("#congress-dots").children[position].focus();
    });
    return dot;
  }));
  const labels = entries.length > 1 ? [0, Math.round((entries.length - 1) / 3), Math.round(2 * (entries.length - 1) / 3), entries.length - 1] : [0];
  $("#congress-years").replaceChildren(...[...new Set(labels)].map((position, index) => {
    const label = html("span", "", `${ordinal(entries[position].congress)} · ${entries[position].start_year}`);
    label.style.left = `${position / Math.max(1, entries.length - 1) * 100}%`;
    if (index === 0) label.classList.add("first");
    if (position === entries.length - 1) label.classList.add("last");
    return label;
  }));
}
function syncTimeline(summary) {
  const entries = state.index.congresses;
  const index = entries.findIndex(d => d.congress === summary.congress);
  state.target = summary.congress;
  $("#congress-slider").value = index;
  $("#congress-slider").style.setProperty("--progress", `${index / Math.max(1, entries.length - 1) * 100}%`);
  $("#congress-slider").setAttribute("aria-valuetext", `${ordinal(summary.congress)} Congress, ${summary.start_year} to ${summary.end_year}`);
  $("#congress-readout").textContent = `${ordinal(summary.congress)} Senate · ${period(summary)}`;
  $("#congress-prev").disabled = index <= 0;
  $("#congress-next").disabled = index >= entries.length - 1;
  $("#congress-dots").querySelectorAll(".timeline-dot").forEach(dot => {
    const active = Number(dot.dataset.congress) === summary.congress;
    dot.setAttribute("aria-current", String(active));
    dot.tabIndex = active ? 0 : -1;
  });
}
function stepCongress(direction) {
  if (!state.index) return;
  const entries = state.index.congresses;
  const position = entries.findIndex(d => d.congress === state.target);
  const next = Math.max(0, Math.min(entries.length - 1, position + direction));
  selectCongress(entries[next].congress);
}
function renderSnapshot() {
  const latest = state.index.congresses.at(-1);
  $("#snapshot-status").textContent = `Snapshot refreshed ${dateLabel(state.index.generated_at)}`;
  $("#history-range").textContent = `${state.index.congresses[0].start_year} — ${latest.end_year} / ${state.index.congresses.length} CONGRESSES`;
}
async function selectCongress(congress, updateURL = true) {
  const summary = state.index.congresses.find((d) => Number(d.congress) === Number(congress));
  if (!summary) return;
  const request = ++state.request;
  $("#workspace").setAttribute("aria-busy", "true");
  syncTimeline(summary);
  $("#timeline-status").textContent = `Loading ${ordinal(summary.congress)}…`;
  try {
    const data = await loadCongress(summary);
    if (request !== state.request) return;
    state.data = data;
    state.selected = null;
    state.query = "";
    $("#senator-search").value = "";
    $("#load-error").hidden = true;
    if (updateURL) {
      const url = new URL(location.href);
      url.searchParams.set("congress", summary.congress);
      history.replaceState(null, "", url);
    }
    renderStats();
    renderLegend();
    renderChart();
    renderDetail();
    renderHistory();
    renderProvenance();
    renderComparison();
    renderOutliers();
    $("#congress-current").textContent = `${ordinal(data.congress)} Congress · ${period(data)}`;
    const included = number(data.members || data.nodes.length);
    $("#data-notes").textContent = `${ordinal(data.congress)} Congress · ${period(data)} · ${included} analyzed members across the term, including replacements. Roll calls through ${dateLabel(data.last_vote_date)}. Exclusions and exact coverage are documented in provenance.`;
    $("#plot-range").textContent = `${number(data.rollcalls)} ROLL CALLS · ${period(data)}`;
  } catch (error) {
    if (request !== state.request) return;
    $("#load-error").textContent = `${error.message} Run the data refresh command in the README and reload. The last successfully loaded chart, if any, remains below.`;
    $("#load-error").hidden = false;
    if (state.data) syncTimeline(state.data);
  } finally {
    if (request === state.request) {
      $("#workspace").setAttribute("aria-busy", "false");
      $("#timeline-status").textContent = "";
    }
  }
}
function renderStats() {
  const d = state.data;
  const specs = [
    ["SPECTRAL CONNECTIVITY", format(d.fiedler_value), "λ₂", "Lower values indicate weaker connectivity"],
    ["SWEEP CONDUCTANCE", format(d.sweep_conductance), "", "A spectral estimate of a low-conductance cut"],
    ["MEAN BROKERAGE", format(d.mean_betweenness, 4), "", "Betweenness on the thresholded graph"],
    ["MEMBERS ANALYZED", number(d.members || d.nodes.length), "", `${number(d.rollcalls)} roll calls in the voting matrix`],
  ];
  $("#stats").replaceChildren(...specs.map(([label, value, suffix, note]) => {
    const card = html("div", "stat");
    const main = html("div", "stat-value", value);
    if (suffix) main.append(html("small", "", suffix));
    card.append(html("div", "stat-label", label), main, html("div", "stat-note", note));
    return card;
  }));
}
function renderLegend() {
  const groups = new Map();
  state.data.nodes.forEach((node) => {
    const group = groups.get(node.party_code) || { name: node.party, count: 0, color: partyColor(node) };
    group.count++;
    groups.set(node.party_code, group);
  });
  $("#party-legend").replaceChildren(...[...groups.values()].sort((a, b) => b.count - a.count).map((group) => {
    const item = html("span", "legend-item"), dot = html("span", "legend-dot");
    dot.style.backgroundColor = group.color;
    item.append(dot, document.createTextNode(`${group.name} ${group.count}`));
    return item;
  }));
}
function coordinates(data, view) {
  return data.nodes.map((node) => ({ node, x: Number(node.x), y: view === "brokerage" ? Number(node.betweenness) : Number(node.y) }));
}
function matches(node) {
  return !state.query || `${node.name} ${prettyName(node.name)} ${node.state} ${node.party}`.toLowerCase().includes(state.query);
}
function buildScatter(data, { compact = false, view = state.view, sharedBounds = null } = {}) {
  const mobile = window.innerWidth < 760;
  const width = compact ? 560 : (mobile ? 400 : 860), height = compact ? 280 : (mobile ? 315 : 355);
  const margin = { left: compact ? 50 : 58, right: 24, top: 25, bottom: 51 };
  const points = coordinates(data, view);
  const [xb, yb] = sharedBounds || [state.axes.x, view === "brokerage" ? state.axes.betweenness : state.axes.y];
  const sx = (v) => margin.left + (v - xb[0]) / (xb[1] - xb[0]) * (width - margin.left - margin.right);
  const sy = (v) => height - margin.bottom - (v - yb[0]) / (yb[1] - yb[0]) * (height - margin.top - margin.bottom);
  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": `${ordinal(data.congress)} Senate ${view} chart. Use Tab to explore senators.`, "data-x-min": xb[0], "data-x-max": xb[1], "data-y-min": yb[0], "data-y-max": yb[1] });
  svg.append(el("title", {}, `${ordinal(data.congress)} Senate: ${view === "brokerage" ? "betweenness versus Fiedler coordinate" : "two-dimensional spectral embedding"}`));
  for (let i = 0; i <= 4; i++) {
    const x = xb[0] + i * (xb[1] - xb[0]) / 4, y = yb[0] + i * (yb[1] - yb[0]) / 4;
    svg.append(el("line", { x1: sx(x), x2: sx(x), y1: margin.top, y2: height - margin.bottom, class: "chart-grid" }));
    svg.append(el("line", { x1: margin.left, x2: width - margin.right, y1: sy(y), y2: sy(y), class: "chart-grid" }));
    svg.append(el("text", { x: sx(x), y: height - margin.bottom + 19, "text-anchor": "middle", class: "chart-tick" }, format(x, 2)));
    svg.append(el("text", { x: margin.left - 10, y: sy(y) + 4, "text-anchor": "end", class: "chart-tick" }, format(y, view === "brokerage" ? 3 : 2)));
  }
  svg.append(el("line", { x1: sx(0), x2: sx(0), y1: margin.top, y2: height - margin.bottom, class: "chart-zero" }));
  svg.append(el("line", { x1: margin.left, x2: width - margin.right, y1: sy(0), y2: sy(0), class: "chart-zero" }));
  svg.append(el("text", { x: (width + margin.left) / 2, y: height - 6, "text-anchor": "middle", class: "chart-label" }, "Fiedler coordinate · v₂"));
  svg.append(el("text", { transform: `translate(13,${(height - margin.bottom) / 2}) rotate(-90)`, "text-anchor": "middle", class: "chart-label" }, view === "brokerage" ? "Betweenness centrality" : "Secondary coordinate · v₃"));
  if (view === "network") {
    const byID = new Map(points.map((p) => [String(p.node.id), p]));
    const edges = (data.edges || []).filter((edge) => edge.weight >= state.threshold);
    edges.forEach((edge) => {
      const source = byID.get(String(edge.source)), target = byID.get(String(edge.target));
      if (!source || !target) return;
      svg.append(el("line", { x1: sx(source.x), y1: sy(source.y), x2: sx(target.x), y2: sy(target.y), stroke: "#688774", "stroke-width": 0.65, opacity: state.query ? 0.04 : Math.max(0.035, 0.18 - edges.length / 40000) }));
    });
    if (!compact) $("#edge-count").textContent = `${number(edges.length)} visible ties`;
  }
  points.forEach(({ node, x, y }) => {
    const isSelected = !compact && String(state.selected) === String(node.id);
    const circle = el("circle", { cx: sx(x), cy: sy(y), r: compact ? 3.5 : (mobile ? 3.8 : 4.4), fill: partyColor(node), class: `point${!compact && !matches(node) ? " dim" : ""}${isSelected ? " selected" : ""}`, tabindex: compact ? -1 : 0, role: "button", "aria-label": `${prettyName(node.name)}, ${node.party}, ${node.state}. Fiedler ${format(x)}, betweenness ${format(node.betweenness, 4)}` });
    circle.append(el("title", {}, `${prettyName(node.name)} · ${node.party} · ${node.state}\nFiedler: ${format(x, 4)} · Brokerage: ${format(node.betweenness, 4)}`));
    if (!compact) {
      const activate = () => { state.selected = node.id; renderDetail(); highlightPoints(); };
      circle.dataset.id = node.id;
      circle.addEventListener("click", activate);
      circle.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(); } });
      circle.addEventListener("focus", () => { state.selected = node.id; renderDetail(); highlightPoints(); });
    }
    svg.append(circle);
  });
  return svg;
}
function highlightPoints() {
  $("#main-chart").querySelectorAll(".point").forEach((point) => point.classList.toggle("selected", point.dataset.id === String(state.selected)));
  const svg = $("#main-chart svg"), selected = $("#main-chart .point.selected");
  svg?.querySelector(".point-label")?.remove();
  if (selected) {
    const node = state.data.nodes.find(item => String(item.id) === String(state.selected));
    const x = Number(selected.getAttribute("cx")), y = Number(selected.getAttribute("cy"));
    const label = el("text", { x: x + 9, y: y - 11, class: "point-label", "pointer-events": "none" }, prettyName(node.name));
    if (x > svg.viewBox.baseVal.width * .62) { label.setAttribute("x", x - 9); label.setAttribute("text-anchor", "end"); }
    svg.append(label);
  }
  $("#outlier-list").querySelectorAll(".outlier-button").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.id === String(state.selected))));
}
function renderChart() {
  if (!state.data) return;
  const config = {
    spectral: ["SPECTRAL EMBEDDING", "Two dimensions of division", "Each point is a senator. Nearby positions reflect similar patterns in the weighted voting network. Party colors are added after the analysis.", "Axes stay fixed across Congresses. Eigenvectors are normalized separately, so this compares shapes without establishing a common ideological scale."],
    network: ["WEIGHTED VOTING NETWORK", "The ties between votes", "Lines connect senators whose transformed voting correlation meets the display threshold. Positions use the same spectral embedding as the geometry view.", "This slider changes the visible ties only. Spectral metrics use the full weighted graph; brokerage uses a separate 0.5 edge threshold."],
    brokerage: ["STRUCTURAL BROKERAGE", "Who lies on the paths?", "Height shows weighted shortest-path betweenness on a graph retaining ties of at least 0.5. Higher values identify more frequent intermediaries in this model.", "Short service can produce misleadingly high brokerage: missing and nonservice votes are coded zero. Check each member’s record coverage before interpreting a high score."],
  }[state.view];
  $("#plot-eyebrow").textContent = config[0];
  $("#plot-title").textContent = config[1];
  $("#view-description").textContent = config[2];
  $("#interpretation-text").textContent = config[3];
  $("#network-controls").hidden = state.view !== "network";
  $("#main-chart").replaceChildren(buildScatter(state.data));
  renderSearch();
  highlightPoints();
}
function renderOutliers() {
  const data = state.data, inspector = $("#outlier-inspector");
  inspector.hidden = data.congress !== 119;
  $("#outlier-list").replaceChildren();
  if (inspector.hidden) return;
  // Curated inspection shortcuts for the audited 119th snapshot, not exclusions
  // or a ranking algorithm. Look up counts in the current data, never hardcode them.
  const identifiers = [42508, 42507, 21355, 41104, 49703, 40300];
  identifiers.forEach(id => {
    const node = data.nodes.find(item => item.id === id);
    if (!node) return;
    const button = html("button", "outlier-button");
    button.type = "button"; button.dataset.id = id;
    button.setAttribute("aria-pressed", "false");
    button.append(html("strong", "", prettyName(node.name)), html("span", "", `${node.state} · ${number(node.votes_cast)} / ${number(data.rollcalls)} encoded votes`));
    button.addEventListener("click", () => {
      state.selected = id;
      state.query = "";
      $("#senator-search").value = "";
      renderDetail(); renderChart();
    });
    $("#outlier-list").append(button);
  });
  const excluded = data.provenance?.excluded_members || [];
  const officeNotes = [];
  if (!data.nodes.some(node => node.id === 99912)) officeNotes.push("Donald Trump is excluded: his member metadata identifies the President, even though Voteview includes Senate-labelled positions.");
  const vance = excluded.find(node => node.id === 42304);
  if (vance) officeNotes.push(`JD Vance is excluded: ${vance.reason}.`);
  const rubio = excluded.find(node => node.id === 41102);
  if (rubio) officeNotes.push(`Marco Rubio is excluded from this Congress: ${rubio.reason}. Earlier Congresses retain his Senate records.`);
  $("#outlier-office-note").textContent = officeNotes.join(" ");
}
function renderSearch() {
  const container = $("#search-results");
  container.hidden = !state.query;
  container.replaceChildren();
  if (!state.query) return;
  const results = state.data.nodes.filter(matches);
  if (!results.length) {
    const exclusions = (state.data.provenance?.excluded_members || []).filter(node =>
      `${node.name} ${prettyName(node.name)}`.toLowerCase().includes(state.query));
    if (exclusions.length) exclusions.forEach(node => container.append(html("p", "", `${prettyName(node.name)} is excluded from this Congress: ${node.reason}.`)));
    else container.append(html("p", "", "No matching senators. Try a surname, state, or party."));
    return;
  }
  results.slice(0, 12).forEach((node) => {
    const button = html("button", "", prettyName(node.name));
    button.type = "button";
    button.addEventListener("click", () => { state.selected = node.id; renderDetail(); highlightPoints(); });
    container.append(button);
  });
  if (results.length > 12) container.append(html("p", "", `${results.length} matches. Refine the search to see more names.`));
}
function renderDetail() {
  const panel = $("#senator-detail");
  panel.replaceChildren();
  const node = state.data.nodes.find((item) => String(item.id) === String(state.selected));
  if (!node) { panel.append(html("span", "detail-label", "EXPLORE A POINT"), html("p", "", "Select a dot or search by name to see a senator’s coordinates and brokerage.")); return; }
  panel.append(html("span", "detail-label", "SELECTED SENATOR"), html("h4", "", prettyName(node.name)), html("p", "", `${node.party} · ${node.state}`));
  const values = html("div", "detail-values");
  const coverage = Number(node.votes_cast) / state.data.rollcalls;
  [["FIEDLER", format(node.x, 4)], ["BROKERAGE", format(node.betweenness, 4)], ["ENCODED ±1 VOTES", number(node.votes_cast)], ["RECORD COVERAGE", `${format(coverage * 100, 1)}%`]].forEach(([label, value]) => {
    const item = html("div");
    item.append(html("span", "", label), html("strong", "", value));
    values.append(item);
  });
  panel.append(values);
  if (coverage < 0.1) panel.append(html("p", "coverage-warning", "Low record coverage. Zero-coded nonservice or missing votes can inflate apparent brokerage. This fraction is not a service-adjusted attendance rate."));
}
function renderHistory() {
  if (!state.index || !state.data) return;
  const metric = $("#history-metric").value, info = metricInfo[metric];
  $("#history-chart-title").textContent = info[0];
  $("#history-description").textContent = info[1];
  const items = state.index.congresses.filter((d) => typeof d[metric] === "number" && Number.isFinite(d[metric]));
  if (!items.length) { $("#history-chart").replaceChildren(html("p", "", "No values are available for this measure.")); return; }
  const mobile = window.innerWidth < 760;
  const width = mobile ? 400 : 1200, height = mobile ? 250 : 230;
  const margin = { l: 48, r: 20, t: 22, b: 38 };
  const start = Math.min(...items.map((d) => d.start_year)), end = Math.max(...items.map((d) => d.start_year));
  const max = Math.max(...items.map((d) => d[metric]), 0.001) * 1.12;
  const sx = (x) => margin.l + (x - start) / Math.max(end - start, 1) * (width - margin.l - margin.r);
  const sy = (y) => height - margin.b - y / max * (height - margin.t - margin.b);
  const svg = el("svg", { viewBox: `0 0 ${width} ${height}`, role: "group", "aria-label": `${info[2]} across ${items.length} Congresses. Each point selects a Congress.` });
  for (let i = 0; i <= 3; i++) {
    const value = i * max / 3;
    svg.append(el("line", { x1: margin.l, x2: width - margin.r, y1: sy(value), y2: sy(value), class: "chart-grid" }));
    svg.append(el("text", { x: margin.l - 10, y: sy(value) + 4, "text-anchor": "end", class: "chart-tick" }, format(value, max < 0.1 ? 3 : 2)));
  }
  const years = [...new Set([start, ...[1800, 1850, 1900, 1950, 2000].filter((y) => y > start + 15 && y < end - 15), end])];
  years.forEach((year) => svg.append(el("text", { x: sx(year), y: height - 12, class: "chart-tick", "text-anchor": "middle" }, year)));
  if (start < 1861 && end > 1861 && !mobile) {
    svg.append(el("line", { x1: sx(1861), x2: sx(1861), y1: margin.t, y2: height - margin.b, stroke: "#d5bca8", "stroke-dasharray": "3 4" }));
    svg.append(el("text", { x: sx(1861) + 7, y: margin.t + 5, class: "chart-tick" }, "1861 · Civil War"));
  }
  // Gaps in coverage remain visible; do not imply a complete series.
  let segment = [];
  const segments = [];
  items.forEach((item, index) => {
    if (index && item.congress !== items[index - 1].congress + 1) { segments.push(segment); segment = []; }
    segment.push(item);
  });
  segments.push(segment);
  segments.forEach((series) => {
    const path = series.map((d, i) => `${i ? "L" : "M"}${sx(d.start_year)},${sy(d[metric])}`).join(" ");
    svg.append(el("path", { d: path, stroke: "#557963", "stroke-width": 1.8, fill: "none" }));
  });
  items.forEach((d) => {
    const active = d.congress === state.data.congress;
    if (active) svg.append(el("line", { x1: sx(d.start_year), x2: sx(d.start_year), y1: margin.t, y2: height - margin.b, stroke: "#ba7547", "stroke-dasharray": "2 4", opacity: 0.5 }));
    const circle = el("circle", { cx: sx(d.start_year), cy: sy(d[metric]), r: active ? 5.5 : 3, fill: active ? "#bb7547" : "#698972", class: "history-dot", tabindex: 0, role: "button", "aria-label": `${ordinal(d.congress)} Congress, ${period(d)}: ${format(d[metric], 4)}. Select to explore.` });
    circle.append(el("title", {}, `${ordinal(d.congress)} · ${period(d)}\n${info[2]}: ${format(d[metric], 4)}`));
    const activate = () => { selectCongress(d.congress); };
    circle.addEventListener("click", activate);
    circle.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(); } });
    svg.append(circle);
  });
  $("#history-chart").replaceChildren(svg);
}
async function renderComparison() {
  const panel = $("#comparison-panel");
  panel.hidden = !state.compare;
  if (!state.compare || !state.data) return;
  const current = state.data;
  const baseline = state.index.congresses.find((d) => d.congress === 96);
  if (!baseline) { panel.replaceChildren(html("p", "", "The 96th Congress snapshot is not available. Refresh Congress 96 to enable this comparison.")); return; }
  try {
    const prior = await loadCongress(baseline);
    if (!state.compare || state.data !== current) return;
    const sharedBounds = [state.axes.x, state.axes.y];
    panel.replaceChildren(html("h3", "", "Two chambers, one visual frame"), html("p", "", "Shared axis limits make the shapes easier to compare. Eigenvectors are normalized independently; they do not form a common ideological scale."));
    const grid = html("div", "comparison-grid");
    [prior, current].forEach((data) => {
      const item = html("div"), caption = html("div", "comparison-caption");
      caption.append(html("strong", "", `${ordinal(data.congress)} · ${period(data)}`), html("span", "", `λ₂ ${format(data.fiedler_value)}`));
      item.append(caption, buildScatter(data, { compact: true, view: "spectral", sharedBounds }));
      grid.append(item);
    });
    panel.append(grid);
  } catch (error) {
    if (!state.compare || state.data !== current) return;
    panel.replaceChildren(html("p", "", `Comparison unavailable: ${error.message}`));
  }
}
function renderProvenance() {
  const data = state.data;
  $("#provenance-output").textContent = JSON.stringify({
    congress: data.congress,
    snapshot_generated_at: state.index.generated_at,
    methodology_version: data.methodology_version || state.index.methodology_version,
    latest_roll_call_date: data.last_vote_date,
    provenance: data.provenance || {},
  }, null, 2);
  const summary = state.index.congresses.find((d) => d.congress === data.congress);
  $("#download-congress").href = safeDataPath(summary.data_file);
}
function downloadCSV() {
  if (!state.index) return;
  const columns = ["congress", "start_year", "end_year", "members", "rollcalls", "last_vote_date", "fiedler_value", "sweep_conductance", "mean_betweenness", "max_betweenness", "gini_betweenness"];
  const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const text = [columns.join(","), ...state.index.congresses.map((d) => columns.map((key) => escape(d[key])).join(","))].join("\r\n");
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  const anchor = html("a");
  anchor.href = url; anchor.download = "eigenpolitics-historical-metrics.csv";
  document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function init() {
  try {
    const index = await readJSON("data/index.json");
    if (index.schema_version !== 1 || !Array.isArray(index.congresses) || !index.congresses.length) throw new Error("The data manifest is missing or incompatible.");
    index.congresses.sort((a, b) => a.congress - b.congress);
    state.index = index;
    setFixedAxes(index);
    fillTimeline();
    renderSnapshot();
    const requested = Number(new URLSearchParams(location.search).get("congress"));
    const initial = index.congresses.some((d) => d.congress === requested) ? requested : index.congresses.at(-1).congress;
    await selectCongress(initial, false);
    $("#compare-button").disabled = !index.congresses.some((d) => d.congress === 96);
  } catch (error) {
    $("#snapshot-status").textContent = "Snapshot unavailable";
    $("#load-error").textContent = `${error.message} Start the local server and run python scripts/refresh_data.py as described in the README.`;
    $("#load-error").hidden = false;
    $("#workspace").setAttribute("aria-busy", "false");
  }
}
$("#congress-slider").addEventListener("input", event => {
  const summary = state.index?.congresses[Number(event.target.value)];
  if (summary) selectCongress(summary.congress);
});
$("#congress-prev").addEventListener("click", () => stepCongress(-1));
$("#congress-next").addEventListener("click", () => stepCongress(1));
document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => {
  state.view = button.dataset.view;
  document.querySelectorAll("[data-view]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  renderChart();
}));
$("#senator-search").addEventListener("input", (event) => { state.query = event.target.value.trim().toLowerCase(); renderChart(); });
$("#edge-threshold").addEventListener("input", (event) => { state.threshold = Number(event.target.value); $("#threshold-value").textContent = state.threshold.toFixed(2); renderChart(); });
$("#history-metric").addEventListener("change", renderHistory);
$("#compare-button").addEventListener("click", () => { state.compare = !state.compare; $("#compare-button").setAttribute("aria-pressed", String(state.compare)); renderComparison(); });
$("#download-csv").addEventListener("click", downloadCSV);
let resizeTimer;
window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { renderChart(); renderHistory(); renderComparison(); }, 150); });
// Poll the generated manifest; downloading Voteview and computing metrics belongs
// to the Python pipeline. Hidden tabs make no periodic network requests.
setInterval(async () => {
  if (document.hidden || !state.index) return;
  try {
    const next = await readJSON("data/index.json");
    if (next.schema_version !== 1 || !Array.isArray(next.congresses) || !next.congresses.length || next.generated_at === state.index.generated_at) return;
    const selected = state.target || state.data?.congress;
    next.congresses.sort((a, b) => a.congress - b.congress);
    state.index = next; state.generation++; state.cache.clear();
    setFixedAxes(next); fillTimeline(); renderSnapshot();
    await selectCongress(next.congresses.some((d) => d.congress === selected) ? selected : next.congresses.at(-1).congress, false);
    toast("A refreshed research snapshot is now available.");
  } catch { /* Retain the last successful snapshot on temporary server errors. */ }
}, 300000);
init();
