const SECTION_STORAGE_KEY = "transferStockCollapsedSections";
const SECTION_TAB_STORAGE_KEY = "transferStockSectionTab";

const SECTION_TABS = {
  main: {
    label: "Main",
    meta: "Useful first read: cockpit, focus brief, ask box, and live signal cards.",
    sections: ["overviewSection", "marketCockpitSection", "focusBriefSection", "askAnalystSection", "signalCardsSection"],
  },
  signals: {
    label: "Signals",
    meta: "Current rumor cards, table filters, row detail, and direct-target watchlist.",
    sections: ["signalCardsSection", "controlsSection", "workspaceSection", "watchlistSection", "coverageSection"],
  },
  clubs: {
    label: "Clubs",
    meta: "Public-club dossiers, club comparison, and season-level transfer history.",
    sections: ["clubDossierSection", "clubComparisonSection", "seasonHistorySection"],
  },
  agents: {
    label: "Agents",
    meta: "Agent access, runbooks, RAG audit, autopilot, scenario swarm, and simulator.",
    sections: ["runbookSection", "agentAccessSection", "agentRunSection", "ragAuditSection", "autopilotSection", "scenarioSwarmSection", "scenarioSimulatorSection", "rumorGraphSection"],
  },
  research: {
    label: "Research",
    meta: "Evidence quality, reporter credibility, trust graph, and backtest context.",
    sections: ["insightSection", "dataQualitySection", "leaderboardsSection", "trustGraphSection", "reporterProfilesSection", "backtestsSection"],
  },
  data: {
    label: "Data",
    meta: "Rawer tables and file lineage for auditing the pipeline behind the dashboard.",
    sections: ["controlsSection", "workspaceSection", "seasonHistorySection", "backtestsSection", "dataFlowSection"],
  },
};

const CLUB_PAGE_SECTIONS = new Set([
  "overviewSection",
  "marketCockpitSection",
  "controlsSection",
  "workspaceSection",
  "clubDossierSection",
  "seasonHistorySection",
]);

const SECTION_NAV_ITEMS = [
  { id: "overviewSection", label: "Overview", bodySelectors: [".metric-card"], keepOpen: true },
  { id: "marketCockpitSection", label: "Analyst Cockpit", bodySelectors: ["#marketCockpit"], keepOpen: true },
  { id: "runbookSection", label: "Research Runbooks", keepOpen: true },
  { id: "focusBriefSection", label: "Focus Brief", keepOpen: true },
  { id: "insightSection", label: "What You Can Get" },
  { id: "dataQualitySection", label: "Data Quality Audit" },
  { id: "askAnalystSection", label: "Ask The Analyst", keepOpen: true },
  { id: "agentAccessSection", label: "Agent Access" },
  { id: "rumorGraphSection", label: "Temporal Rumor Graph" },
  { id: "agentRunSection", label: "Latest Agent Run" },
  { id: "ragAuditSection", label: "RAG Trust Audit" },
  { id: "autopilotSection", label: "Agent Autopilot" },
  { id: "scenarioSwarmSection", label: "Scenario Swarm" },
  { id: "scenarioSimulatorSection", label: "Scenario Simulator" },
  { id: "controlsSection", label: "Filters", bodySelectors: [".control"], keepOpen: true },
  { id: "workspaceSection", label: "Signals Workspace", bodySelectors: [".table-pane .table-wrap", "#detailPane"], keepOpen: true },
  { id: "clubDossierSection", label: "Club Dossier" },
  { id: "clubComparisonSection", label: "Club vs Club" },
  { id: "watchlistSection", label: "Live Watchlist" },
  { id: "signalCardsSection", label: "Live Signal Cards" },
  { id: "coverageSection", label: "Live Coverage" },
  { id: "leaderboardsSection", label: "Credibility Leaderboards" },
  { id: "trustGraphSection", label: "Reporter Trust Graph" },
  { id: "reporterProfilesSection", label: "Reporter Profiles" },
  { id: "seasonHistorySection", label: "Season History" },
  { id: "backtestsSection", label: "Backtest Summary" },
  { id: "dataFlowSection", label: "Pipeline Files" },
];

const DEMO_MODE_OPEN_SECTIONS = new Set([
  "overviewSection",
  "marketCockpitSection",
  "runbookSection",
  "focusBriefSection",
  "askAnalystSection",
  "agentRunSection",
  "ragAuditSection",
  "autopilotSection",
  "scenarioSwarmSection",
  "signalCardsSection",
  "workspaceSection",
  "dataQualitySection",
  "agentAccessSection",
]);

const state = {
  payload: null,
  page: "market",
  routeClub: null,
  selectedSeason: null,
  selectedView: "rumors",
  clubFilter: "All",
  sortMode: "impact",
  search: "",
  selectedKey: null,
  compareClubA: "",
  compareClubB: "",
  selectedReporter: "",
  askQuestion: "",
  askResult: null,
  agent: null,
  ragAudit: null,
  autopilot: null,
  operator: null,
  operatorRuntime: null,
  runbooks: null,
  agentManifest: null,
  rumorGraph: null,
  scenario: null,
  dataQuality: null,
  simulatorResult: null,
  collapsedSections: new Set(),
  sectionTab: "main",
};

function pillClass(label) {
  if (label === "positive") return "pill pill-positive";
  if (label === "negative") return "pill pill-negative";
  return "pill pill-neutral";
}

function confidencePillClass(tier) {
  if (tier === "broad_consensus") return "pill pill-positive";
  if (tier === "strong") return "pill pill-info";
  if (tier === "developing") return "pill pill-neutral";
  return "pill pill-warning";
}

function confidenceTierLabel(tier) {
  if (tier === "broad_consensus") return "Broad consensus";
  if (tier === "strong") return "Strong";
  if (tier === "developing") return "Developing";
  return "Thin";
}

function consensusPillClass(label) {
  if (label === "Broad alignment") return "pill pill-positive";
  if (label === "Aligned") return "pill pill-info";
  if (label === "Developing") return "pill pill-neutral";
  return "pill pill-warning";
}

function stancePillClass(stance) {
  if (stance === "bullish") return "pill pill-positive";
  if (stance === "bearish") return "pill pill-negative";
  if (stance === "neutral") return "pill pill-neutral";
  return "pill pill-warning";
}

function fmtNumber(value, digits = 2) {
  if (value === "" || value === null || value === undefined) return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return num.toFixed(digits);
}

function fmtPct(value, digits = 1) {
  if (value === "" || value === null || value === undefined) return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return `${(num * 100).toFixed(digits)}%`;
}

function fmtSignedPct(value, digits = 1) {
  if (value === "" || value === null || value === undefined) return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return `${num > 0 ? "+" : ""}${(num * 100).toFixed(digits)}%`;
}

function clampNumber(value, low = 0, high = 1) {
  return Math.max(low, Math.min(high, value));
}

function fmtDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return date.toISOString().slice(0, 10);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");
}

function loadCollapsedSections() {
  try {
    const raw = window.localStorage.getItem(SECTION_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch (error) {
    return new Set();
  }
}

function saveCollapsedSections() {
  try {
    window.localStorage.setItem(SECTION_STORAGE_KEY, JSON.stringify(Array.from(state.collapsedSections)));
  } catch (error) {
    // localStorage can be unavailable from file:// or locked-down browsers.
  }
}

function loadSectionTab() {
  try {
    const value = window.localStorage.getItem(SECTION_TAB_STORAGE_KEY);
    return value && SECTION_TABS[value] ? value : "main";
  } catch (error) {
    return "main";
  }
}

function saveSectionTab() {
  try {
    window.localStorage.setItem(SECTION_TAB_STORAGE_KEY, state.sectionTab);
  } catch (error) {
    // localStorage can be unavailable from file:// or locked-down browsers.
  }
}

function tabForSection(sectionId) {
  return Object.entries(SECTION_TABS).find(([, config]) => config.sections.includes(sectionId))?.[0] || "main";
}

function visibleSectionsForCurrentLens() {
  if (state.page === "club" && state.routeClub) return CLUB_PAGE_SECTIONS;
  const tab = SECTION_TABS[state.sectionTab] || SECTION_TABS.main;
  return new Set(tab.sections);
}

function applySectionTabVisibility() {
  const visibleSections = visibleSectionsForCurrentLens();
  SECTION_NAV_ITEMS.forEach((item) => {
    const section = document.getElementById(item.id);
    if (!section) return;
    section.hidden = !visibleSections.has(item.id);
    section.dataset.sectionTabHidden = section.hidden ? "true" : "false";
  });
  const meta = document.getElementById("sectionTabMeta");
  if (meta) {
    const tab = SECTION_TABS[state.sectionTab] || SECTION_TABS.main;
    meta.textContent = state.page === "club" && state.routeClub
      ? "Club view keeps the dossier, stock path, table, and transfer history visible."
      : tab.meta;
  }
  document.querySelectorAll("#sectionTabs button").forEach((button) => {
    const active = button.dataset.sectionTab === state.sectionTab;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  renderSectionMenu();
}

function sectionConfig(sectionId) {
  return SECTION_NAV_ITEMS.find((item) => item.id === sectionId) || null;
}

function sectionHead(section) {
  if (!section) return null;
  return section.querySelector(":scope > .section-head")
    || section.querySelector(":scope > .table-pane > .section-head")
    || null;
}

function sectionBodyElements(section, config) {
  if (!section) return [];
  if (config?.bodySelectors?.length) {
    return config.bodySelectors.flatMap((selector) => Array.from(section.querySelectorAll(selector)));
  }
  const head = sectionHead(section);
  return Array.from(section.children).filter((child) => child !== head);
}

function isSectionCollapsed(sectionId) {
  return state.collapsedSections.has(sectionId);
}

function applySectionCollapseState() {
  SECTION_NAV_ITEMS.forEach((item) => {
    const section = document.getElementById(item.id);
    if (!section) return;
    const collapsed = isSectionCollapsed(item.id);
    section.classList.toggle("is-collapsed", collapsed);
    sectionBodyElements(section, item).forEach((element) => {
      element.hidden = collapsed;
    });
    const button = section.querySelector(`[data-section-collapse="${item.id}"]`);
    if (button) {
      button.setAttribute("aria-expanded", String(!collapsed));
      button.textContent = collapsed ? "Expand" : "Collapse";
      button.title = collapsed ? `Expand ${item.label}` : `Collapse ${item.label}`;
    }
  });
  renderSectionMenu();
}

function toggleSectionCollapsed(sectionId, nextValue = null) {
  const collapsed = nextValue === null ? !isSectionCollapsed(sectionId) : Boolean(nextValue);
  if (collapsed) {
    state.collapsedSections.add(sectionId);
  } else {
    state.collapsedSections.delete(sectionId);
  }
  saveCollapsedSections();
  applySectionCollapseState();
}

function expandAllDashboardSections() {
  state.collapsedSections.clear();
  saveCollapsedSections();
  applySectionCollapseState();
}

function collapseDashboardSections({ reportsOnly = false } = {}) {
  state.collapsedSections.clear();
  SECTION_NAV_ITEMS.forEach((item) => {
    if (reportsOnly && item.keepOpen) return;
    state.collapsedSections.add(item.id);
  });
  saveCollapsedSections();
  applySectionCollapseState();
}

function applyDemoMode() {
  state.page = "market";
  state.routeClub = null;
  state.selectedSeason = state.payload.latest_season;
  state.selectedView = "rumors";
  state.clubFilter = "All";
  state.sortMode = "impact";
  state.search = "";
  const topLive = (state.payload.live_watchlist || [])[0];
  const topSeason = (state.payload.signals_by_season?.[state.payload.latest_season] || [])[0];
  const demoRow = topLive || topSeason || null;
  state.selectedKey = demoRow ? (demoRow.group_key || demoRow.claim_ids || null) : null;
  const player = demoRow?.player || "the strongest current rumor";
  const club = demoRow?.target_club || demoRow?.club || "";
  state.askQuestion = club ? `Explain ${player} at ${club}` : `Explain ${player}`;
  state.askResult = askAnalyst(state.askQuestion);
  state.sectionTab = "main";
  saveSectionTab();
  state.collapsedSections.clear();
  SECTION_NAV_ITEMS.forEach((item) => {
    if (!DEMO_MODE_OPEN_SECTIONS.has(item.id)) state.collapsedSections.add(item.id);
  });
  saveCollapsedSections();
  syncHash();
  renderAll();
  document.getElementById("askAnalystSection")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function setupSectionChrome() {
  SECTION_NAV_ITEMS.forEach((item) => {
    const section = document.getElementById(item.id);
    const head = sectionHead(section);
    if (!section || !head || head.querySelector(`[data-section-collapse="${item.id}"]`)) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "section-collapse-button";
    button.dataset.sectionCollapse = item.id;
    button.setAttribute("aria-expanded", "true");
    button.textContent = "Collapse";
    head.appendChild(button);
  });
  renderSectionMenu();
  applySectionCollapseState();
}

function renderSectionMenu() {
  const list = document.getElementById("sectionMenuList");
  if (!list) return;
  list.innerHTML = SECTION_NAV_ITEMS.map((item) => {
    const collapsed = isSectionCollapsed(item.id);
    const section = document.getElementById(item.id);
    const hiddenByTab = section?.dataset.sectionTabHidden === "true";
    return `
      <div class="section-menu-item">
        <button type="button" class="section-menu-jump" data-jump="${escapeHtml(item.id)}">
          <span>${escapeHtml(item.label)}</span>
          <small>${hiddenByTab ? `In ${escapeHtml(SECTION_TABS[tabForSection(item.id)]?.label || "another")} tab` : (collapsed ? "Collapsed" : "Visible")}</small>
        </button>
        <button type="button" class="section-menu-toggle" data-section-collapse="${escapeHtml(item.id)}" aria-expanded="${String(!collapsed)}">
          ${collapsed ? "Show" : "Hide"}
        </button>
      </div>
    `;
  }).join("");
}

function openSectionDrawer() {
  const drawer = document.getElementById("sectionDrawer");
  const scrim = document.getElementById("sectionScrim");
  const toggle = document.getElementById("sectionMenuToggle");
  if (!drawer || !scrim || !toggle) return;
  drawer.hidden = false;
  scrim.hidden = false;
  requestAnimationFrame(() => {
    drawer.classList.add("is-open");
    scrim.classList.add("is-open");
  });
  toggle.setAttribute("aria-expanded", "true");
}

function closeSectionDrawer() {
  const drawer = document.getElementById("sectionDrawer");
  const scrim = document.getElementById("sectionScrim");
  const toggle = document.getElementById("sectionMenuToggle");
  if (!drawer || !scrim || !toggle) return;
  drawer.classList.remove("is-open");
  scrim.classList.remove("is-open");
  toggle.setAttribute("aria-expanded", "false");
  window.setTimeout(() => {
    if (!drawer.classList.contains("is-open")) drawer.hidden = true;
    if (!scrim.classList.contains("is-open")) scrim.hidden = true;
  }, 160);
}

function clubMedia(name) {
  return (state.payload.club_media || {})[name] || {};
}

function clubLogoUrl(name) {
  return clubMedia(name).logo_url || "";
}

function clubChip(name) {
  const logo = clubLogoUrl(name);
  const attrs = name ? ` data-club-route="${escapeHtml(name)}" tabindex="0" role="button"` : "";
  if (!logo) return `<span class="club-chip club-chip-link"${attrs}><span>${escapeHtml(name || "-")}</span></span>`;
  return `
    <span class="club-chip club-chip-link"${attrs}>
      <img class="club-logo" src="${escapeHtml(logo)}" alt="${escapeHtml(name || "Club")} logo" loading="lazy">
      <span>${escapeHtml(name || "-")}</span>
    </span>
  `;
}

function playerChip(name, subtitle = "") {
  return `
    <span class="player-chip">
      <span>
        <strong>${escapeHtml(name || "-")}</strong>
        ${subtitle ? `<span class="detail-meta">${subtitle}</span>` : ""}
      </span>
    </span>
  `;
}

function displayModelLabel(row) {
  if (row.predicted_label) return row.predicted_label;
  if (row.prediction_scope === "none") return "n/a";
  return "-";
}

function displayBlendLabel(row) {
  if (row.prediction_scope === "none") return "intel";
  return row.blended_label || "-";
}

function currentSeasonSignals() {
  return state.payload.signals_by_season[state.selectedSeason] || [];
}

function currentSeasonTransfers() {
  return state.payload.transfers_by_season[state.selectedSeason] || [];
}

function allCurrentPublicClubs() {
  const names = new Set();
  (state.payload.current_signals || []).forEach((row) => {
    const name = row.target_club || row.club;
    if (name) names.add(name);
  });
  (state.payload.live_watchlist || []).forEach((row) => {
    const name = row.target_club || row.club;
    if (name) names.add(name);
  });
  return Array.from(names).sort();
}

function availableClubNames() {
  return Object.keys(state.payload.club_dossiers || {}).sort();
}

function normalizeQuery(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function allAnalystSignals() {
  const rows = [];
  Object.values(state.payload.signals_by_season || {}).forEach((seasonRows) => rows.push(...(seasonRows || [])));
  rows.push(...(state.payload.live_watchlist || []));
  Object.values(state.payload.watchlist_details || {}).forEach((row) => rows.push(row));
  const seen = new Set();
  return rows.filter((row) => {
    const key = row.group_key || `${row.club || row.target_club || ""}:${row.player || ""}:${row.latest_published_at || row.published_at || ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function allAnalystTransfers() {
  return Object.values(state.payload.transfers_by_season || {}).flatMap((rows) => rows || []);
}

function analystNames(kind) {
  if (kind === "club") return availableClubNames();
  if (kind === "reporter") {
    const names = new Set(Object.keys(state.payload.reporter_profiles || {}));
    (state.payload.leaderboards?.journalists || []).forEach((row) => {
      if (row.journalist) names.add(row.journalist);
    });
    return Array.from(names).sort();
  }
  if (kind === "player") {
    const names = new Set();
    allAnalystSignals().forEach((row) => row.player && names.add(row.player));
    allAnalystTransfers().forEach((row) => row.player && names.add(row.player));
    return Array.from(names).sort();
  }
  return [];
}

function analystMatchName(question, names) {
  const query = ` ${normalizeQuery(question)} `;
  let best = "";
  let bestScore = 0;
  names.forEach((name) => {
    const normalized = normalizeQuery(name);
    if (!normalized) return;
    const tokens = normalized.split(" ").filter((token) => token.length > 2);
    let score = 0;
    if (query.includes(` ${normalized} `)) {
      score = 100 + normalized.length;
    } else if (tokens.length && tokens.every((token) => query.includes(` ${token} `))) {
      score = 70 + tokens.length;
    } else if (tokens.length) {
      score = tokens.filter((token) => query.includes(` ${token} `)).length;
    }
    if (score > bestScore) {
      best = name;
      bestScore = score;
    }
  });
  return best;
}

function analystMatchClubs(question) {
  const query = ` ${normalizeQuery(question)} `;
  const matches = [];
  analystNames("club").forEach((name) => {
    const normalized = normalizeQuery(name);
    const tokens = normalized.split(" ").filter((token) => token.length > 2);
    let index = query.indexOf(` ${normalized} `);
    if (index < 0 && tokens.length && tokens.every((token) => query.includes(` ${token} `))) {
      index = Math.min(...tokens.map((token) => query.indexOf(` ${token} `)).filter((value) => value >= 0));
    }
    if (index >= 0) matches.push({ index, name });
  });
  if (matches.length >= 2) return matches.sort((a, b) => a.index - b.index).map((item) => item.name);
  const best = analystMatchName(question, analystNames("club"));
  return best ? [best] : [];
}

function analystExtractSeason(question) {
  const match = String(question || "").match(/\b(20\d{2}-\d{2})\b/);
  return match ? match[1] : state.payload.latest_season;
}

function analystDetectIntent(question) {
  const normalized = ` ${normalizeQuery(question)} `;
  const clubs = analystMatchClubs(question);
  const reporter = analystMatchName(question, analystNames("reporter"));
  const player = analystMatchName(question, analystNames("player"));
  const compare = normalized.includes(" compare ") || normalized.includes(" vs ") || normalized.includes(" versus ");
  if ((compare || normalized.includes(" and ")) && clubs.length >= 2) return { intent: "compare_clubs", clubs: clubs.slice(0, 2) };
  if (reporter) return { intent: "reporter_profile", reporter };
  if (clubs.length && [" reporter ", " reporters ", " journalist ", " journalists ", " source ", " credibility "].some((token) => normalized.includes(token))) {
    return { intent: "club_reporters", club: clubs[0] };
  }
  if (player && normalized.includes(" similar ")) return { intent: "similar_cases", player };
  if (player) return { intent: "explain_rumor", player };
  if (clubs.length && [" match ", " result ", " stock ", " price ", " path "].some((token) => normalized.includes(token))) {
    return { intent: "match_stock_context", club: clubs[0] };
  }
  if (clubs.length && [" confirmed ", " transfer ", " transfers ", " past ", " history "].some((token) => normalized.includes(token))) {
    return { intent: "confirmed_transfers", club: clubs[0], season: analystExtractSeason(question) };
  }
  if (clubs.length) return { intent: "club_signals", club: clubs[0] };
  return { intent: "unknown" };
}

function analystAnswer(question, intent, shortAnswer, options = {}) {
  return {
    question,
    intent,
    shortAnswer,
    confidence: options.confidence ?? 0.5,
    evidenceCards: options.evidenceCards || [],
    tables: options.tables || [],
    warnings: options.warnings || [],
    sourcePaths: options.sourcePaths || ["app/static/data/dashboard_data.json"],
  };
}

function analystRowClub(row) {
  return row.target_club || row.club || "";
}

function analystRowDate(row) {
  return fmtDate(row.published_at || row.latest_published_at || row.date || "");
}

function analystSignalTable(rows) {
  return {
    title: "Signals",
    columns: ["Date", "Club", "Player", "Stage", "Cred", "Model", "Blend"],
    rows: rows.map((row) => ({
      Date: analystRowDate(row),
      Club: analystRowClub(row),
      Player: row.player || "",
      Stage: row.rumor_stage || row.latest_rumor_stage || "",
      Cred: fmtNumber(row.credibility_score, 3),
      Model: row.predicted_label || "",
      Blend: row.blended_label || "",
      _groupKey: row.group_key || "",
    })),
  };
}

function analystClubSignals(club, limit = 5) {
  const liveRows = (state.payload.live_watchlist || []).filter((row) => analystRowClub(row) === club || row.club === club);
  if (liveRows.length) return liveRows.slice(0, limit);
  return (state.payload.signals_by_season?.[state.payload.latest_season] || [])
    .filter((row) => analystRowClub(row) === club || row.club === club)
    .slice(0, limit);
}

function analystFindPlayerSignal(player) {
  const normalized = normalizeQuery(player);
  return allAnalystSignals()
    .filter((row) => normalizeQuery(row.player) === normalized)
    .sort((a, b) => String(b.latest_published_at || b.published_at || b.date || "").localeCompare(String(a.latest_published_at || a.published_at || a.date || "")))[0] || null;
}

function analystAnswerClubSignals(question, club) {
  const dossier = state.payload.club_dossiers?.[club] || {};
  const rows = analystClubSignals(club);
  const evidenceCards = [
    { title: "Live events", value: dossier.live_signal_count || 0, detail: "Current watchlist rows" },
    { title: "Avg credibility", value: fmtNumber(dossier.avg_live_credibility, 3), detail: "Mean live credibility" },
    { title: "Transfer index", value: fmtNumber(dossier.avg_transfer_index, 3), detail: "Recent transfer quality" },
    { title: "Realized CAR t+3", value: fmtNumber(dossier.avg_realized_car_p3, 4), detail: "Historical context" },
  ];
  if (!rows.length) {
    return analystAnswer(question, "club_signals", `No current direct-target signals are available for ${club} in this payload.`, {
      evidenceCards,
      warnings: ["Refresh live data if this looks stale."],
      confidence: 0.72,
    });
  }
  const top = rows[0];
  return analystAnswer(question, "club_signals", `${club} has ${rows.length} visible signal(s). Top row: ${top.player || "-"} at ${top.rumor_stage || top.latest_rumor_stage || "-"} with credibility ${fmtNumber(top.credibility_score, 3)}.`, {
    evidenceCards,
    tables: [analystSignalTable(rows)],
    warnings: ["This is research triage, not a trading recommendation."],
    confidence: 0.86,
  });
}

function analystAnswerCompare(question, clubA, clubB) {
  const a = state.payload.club_dossiers?.[clubA] || {};
  const b = state.payload.club_dossiers?.[clubB] || {};
  const stockPaths = state.payload.club_stock_paths || {};
  const rows = [
    { Metric: "Live signals", [clubA]: a.live_signal_count || 0, [clubB]: b.live_signal_count || 0 },
    { Metric: "Avg credibility", [clubA]: fmtNumber(a.avg_live_credibility, 3), [clubB]: fmtNumber(b.avg_live_credibility, 3) },
    { Metric: "Transfer index", [clubA]: fmtNumber(a.avg_transfer_index, 3), [clubB]: fmtNumber(b.avg_transfer_index, 3) },
    { Metric: "Realized CAR t+3", [clubA]: fmtNumber(a.avg_realized_car_p3, 4), [clubB]: fmtNumber(b.avg_realized_car_p3, 4) },
    { Metric: "Positive share", [clubA]: fmtPct(a.realized_positive_share, 1), [clubB]: fmtPct(b.realized_positive_share, 1) },
    { Metric: "Match markers", [clubA]: (stockPaths[clubA]?.markers || []).length, [clubB]: (stockPaths[clubB]?.markers || []).length },
  ];
  const aLive = Number(a.live_signal_count || 0);
  const bLive = Number(b.live_signal_count || 0);
  const lead = aLive === bLive ? `${clubA} and ${clubB} have similar live signal volume.` : (aLive > bLive ? `${clubA} has more live signal volume.` : `${clubB} has more live signal volume.`);
  return analystAnswer(question, "compare_clubs", `${lead} Use the table to compare rumor volume, transfer index, realized CAR, and match-result context.`, {
    evidenceCards: [
      { title: clubA, value: a.top_confidence_tier || "-", detail: `${a.recent_transfer_count || 0} recent transfers` },
      { title: clubB, value: b.top_confidence_tier || "-", detail: `${b.recent_transfer_count || 0} recent transfers` },
    ],
    tables: [{ title: "Club comparison", columns: ["Metric", clubA, clubB], rows }],
    warnings: ["Club stocks can move on match results, ownership news, liquidity, and broad markets."],
    confidence: 0.9,
  });
}

function analystAnswerReporter(question, reporter) {
  const profile = state.payload.reporter_profiles?.[reporter] || {};
  if (!profile.journalist) {
    return analystAnswer(question, "reporter_profile", `No reporter profile is available for ${reporter}.`, {
      warnings: ["Reporter profiles require journalist stats in the dashboard payload."],
      confidence: 0.5,
    });
  }
  return analystAnswer(question, "reporter_profile", `${reporter} has ${profile.n_claims || 0} tracked claim(s), smoothed rate ${fmtNumber(profile.smoothed_rate, 3)}, and avg match score ${fmtNumber(profile.avg_match_score, 3)}.`, {
    evidenceCards: [
      { title: "Claims", value: profile.n_claims || 0, detail: "Tracked rows" },
      { title: "Smoothed rate", value: fmtNumber(profile.smoothed_rate, 3), detail: "Historical credibility" },
      { title: "Avg match", value: fmtNumber(profile.avg_match_score, 3), detail: "Entity matching confidence" },
      { title: "Avg CAR t+3", value: fmtNumber(profile.avg_realized_car_p3, 4), detail: "Where realized rows exist" },
    ],
    tables: [
      { title: "Club coverage", columns: ["club", "count"], rows: profile.clubs || [] },
      { title: "Recent claims", columns: ["date", "club", "player", "stage", "model"], rows: (profile.latest_claims || []).slice(0, 6).map((row) => ({ date: fmtDate(row.published_at), club: row.club || "", player: row.player || "", stage: row.rumor_stage || "", model: row.predicted_label || "" })) },
    ],
    warnings: ["Reporter scores can be sparse and sample-biased."],
    confidence: 0.88,
  });
}

function analystAnswerClubReporters(question, club) {
  const rows = (state.payload.leaderboards?.club_journalists || [])
    .filter((row) => row.club === club)
    .slice(0, 8);
  return analystAnswer(question, "club_reporters", `${club} has ${rows.length} club-specific reporter row(s) in the credibility table.`, {
    tables: [{
      title: `${club} reporters`,
      columns: ["Journalist", "Claims", "Smoothed", "Match"],
      rows: rows.map((row) => ({ Journalist: row.journalist || "", Claims: row.n_claims || 0, Smoothed: fmtNumber(row.smoothed_rate, 3), Match: fmtNumber(row.avg_match_score, 3) })),
    }],
    warnings: ["Sparse reporter rows should be read as leads, not proof."],
    confidence: rows.length ? 0.8 : 0.55,
  });
}

function analystAnswerExplain(question, player) {
  const row = analystFindPlayerSignal(player);
  if (!row) {
    return analystAnswer(question, "explain_rumor", `No signal for ${player} is available in the local payload.`, {
      warnings: ["Try a player in the current signal table or live watchlist."],
      confidence: 0.5,
    });
  }
  const links = row.confirmed_transfer_links || [];
  const tables = [analystSignalTable([row])];
  if (links.length) {
    tables.push({
      title: "Confirmed transfer links",
      columns: ["Date", "Player", "Club", "Role", "Actual", "CAR"],
      rows: links.slice(0, 5).map((item) => ({ Date: item.date || "", Player: item.player || "", Club: item.club || "", Role: item.target_role || "", Actual: item.actual_label || "", CAR: fmtNumber(item.actual_abnormal_return_p3, 4) })),
    });
  }
  return analystAnswer(question, "explain_rumor", `${row.player || player} maps to ${analystRowClub(row) || "-"} as ${row.target_role || "-"}. Signal: ${row.blended_label || "-"}, model: ${row.predicted_label || "-"}, confidence ${fmtPct(row.prediction_confidence, 1)}.`, {
    evidenceCards: [
      { title: "Credibility", value: fmtNumber(row.credibility_score, 3), detail: row.latest_source || row.source || "" },
      { title: "Transfer index", value: fmtNumber(row.transfer_indicator, 3), detail: `Stage ${row.rumor_stage || row.latest_rumor_stage || "-"}` },
      { title: "Scope", value: row.prediction_scope || "-", detail: "Direct only when mapped to a listed club" },
    ],
    tables,
    warnings: ["This is model-assisted research context, not a trade recommendation."],
    confidence: 0.86,
  });
}

function analystAnswerSimilar(question, player) {
  const row = analystFindPlayerSignal(player);
  const examples = row?.similar_examples || [];
  return analystAnswer(question, "similar_cases", examples.length ? `Found ${examples.length} similar historical case(s) for ${player}.` : `No similar cases are attached for ${player}.`, {
    tables: [{
      title: "Similar historical cases",
      columns: ["Similarity", "Date", "Club", "Player", "Actual", "CAR"],
      rows: examples.map((item) => ({ Similarity: fmtNumber(item.similarity, 3), Date: item.date || "", Club: item.club || "", Player: item.player || "", Actual: item.actual_label || "", CAR: fmtNumber(item.target_abnormal_return_p3, 4) })),
    }],
    warnings: ["Similar cases are context, not proof of repeated market reaction."],
    confidence: examples.length ? 0.82 : 0.55,
  });
}

function analystAnswerMatchStock(question, club) {
  const path = state.payload.club_stock_paths?.[club] || {};
  const markers = path.markers || [];
  return analystAnswer(question, "match_stock_context", `${club} has ${markers.length} match-result marker(s) on its local stock path. The chart spans ${(path.dates || [])[0] || "-"} to ${path.latest_date || "-"}.`, {
    evidenceCards: [
      { title: "Ticker", value: path.ticker || "-", detail: "Configured equity symbol" },
      { title: "Latest change", value: fmtPct(path.latest_change, 1), detail: "Loaded chart window" },
      { title: "Match markers", value: markers.length, detail: "Mapped to next trading date" },
    ],
    tables: [{
      title: "Recent match markers",
      columns: ["Match date", "Trading date", "Opponent", "Result", "Score"],
      rows: markers.slice(-6).reverse().map((row) => ({ "Match date": row.match_date || "", "Trading date": row.trading_date || "", Opponent: row.opponent || "", Result: row.result || "", Score: row.score || "" })),
    }],
    warnings: ["Match markers show timing context only; they do not isolate causality."],
    confidence: path.points?.length ? 0.86 : 0.5,
  });
}

function analystAnswerTransfers(question, club, season) {
  const rows = (state.payload.transfers_by_season?.[season] || [])
    .filter((row) => row.club === club || row.subject_club === club)
    .slice(0, 10);
  return analystAnswer(question, "confirmed_transfers", `${club} has ${rows.length} confirmed public-target transfer row(s) in ${season}.`, {
    tables: [{
      title: `${club} confirmed transfers`,
      columns: ["Date", "Player", "Role", "Seller", "Buyer", "T-index", "Actual"],
      rows: rows.map((row) => ({ Date: row.date || "", Player: row.player || "", Role: row.target_role || "", Seller: row.seller_club || "", Buyer: row.buyer_club || "", "T-index": fmtNumber(row.transfer_indicator, 3), Actual: row.actual_label || "" })),
    }],
    warnings: ["Confirmed transfers can be later than initial rumor dates, so stock reaction may already be priced in."],
    confidence: rows.length ? 0.82 : 0.6,
  });
}

function askAnalyst(question) {
  const detected = analystDetectIntent(question);
  if (detected.intent === "compare_clubs") return analystAnswerCompare(question, detected.clubs[0], detected.clubs[1]);
  if (detected.intent === "reporter_profile") return analystAnswerReporter(question, detected.reporter);
  if (detected.intent === "club_reporters") return analystAnswerClubReporters(question, detected.club);
  if (detected.intent === "similar_cases") return analystAnswerSimilar(question, detected.player);
  if (detected.intent === "explain_rumor") return analystAnswerExplain(question, detected.player);
  if (detected.intent === "match_stock_context") return analystAnswerMatchStock(question, detected.club);
  if (detected.intent === "confirmed_transfers") return analystAnswerTransfers(question, detected.club, detected.season);
  if (detected.intent === "club_signals") return analystAnswerClubSignals(question, detected.club);
  return analystAnswer(question, "unknown", "I could not map this question to a club, reporter, player, comparison, stock-path, or transfer-history query in the local payload.", {
    warnings: ["Try naming a configured club, player, or reporter."],
    confidence: 0.25,
  });
}

function activeClubDossier() {
  if (state.page !== "club" || !state.routeClub) return null;
  return (state.payload.club_dossiers || {})[state.routeClub] || null;
}

function activeClubSeasonSummary() {
  const dossier = activeClubDossier();
  if (!dossier) return null;
  const rows = state.selectedView === "transfers"
    ? (dossier.transfer_season_history || [])
    : (dossier.rumor_season_history || []);
  return rows.find((row) => row.season === state.selectedSeason) || rows[0] || null;
}

function currentSeasonSummary() {
  const clubSeason = activeClubSeasonSummary();
  if (clubSeason) return clubSeason;
  if (state.selectedView === "transfers") {
    return state.payload.transfer_season_summaries[state.selectedSeason] || {
      transfer_count: 0,
      realized_count: 0,
      avg_transfer_index: 0,
      avg_realized_car_p3: 0,
      positive_share: 0,
      realized_label_mix: {},
    };
  }
  return state.payload.season_summaries[state.selectedSeason] || {
    signal_count: 0,
    realized_count: 0,
    avg_realized_car_p3: 0,
    positive_share: 0,
    realized_label_mix: {},
  };
}

function availableSeasonsForView() {
  const dossier = activeClubDossier();
  if (dossier) {
    const seasons = (state.selectedView === "transfers"
      ? (dossier.transfer_season_history || [])
      : (dossier.rumor_season_history || [])
    ).map((row) => row.season);
    return seasons.sort((a, b) => Number(b.slice(0, 4)) - Number(a.slice(0, 4)));
  }
  if (state.selectedView === "transfers") {
    return Object.keys(state.payload.transfer_season_summaries).sort((a, b) => Number(b.slice(0, 4)) - Number(a.slice(0, 4)));
  }
  return state.payload.available_seasons.slice();
}

function currentRows() {
  return state.selectedView === "transfers" ? currentSeasonTransfers() : currentSeasonSignals();
}

function selectedClubName() {
  if (state.page === "club" && state.routeClub) return state.routeClub;
  if (state.clubFilter && state.clubFilter !== "All") return state.clubFilter;
  const current = currentRows().find((row) => currentKey(row) === state.selectedKey);
  if (current) return current.club || current.target_club || null;
  const watchDetail = (state.payload.watchlist_details || {})[state.selectedKey];
  if (watchDetail) return watchDetail.target_club || watchDetail.club || null;
  const topLive = (state.payload.live_watchlist || [])[0];
  if (topLive) return topLive.target_club || topLive.club || null;
  const fallback = currentRows()[0];
  return fallback ? (fallback.club || fallback.target_club || null) : null;
}

function currentRouteHash() {
  if (state.page === "club" && state.routeClub) {
    return `#/club/${encodeURIComponent(state.routeClub)}`;
  }
  return "#/market";
}

function syncHash() {
  const next = currentRouteHash();
  if (window.location.hash !== next) {
    window.history.replaceState(null, "", next);
  }
}

function applyRouteFromHash() {
  const hash = window.location.hash || "#/market";
  const clubMatch = hash.match(/^#\/club\/(.+)$/);
  if (clubMatch) {
    state.page = "club";
    state.routeClub = decodeURIComponent(clubMatch[1]);
    state.clubFilter = "All";
    state.sectionTab = "clubs";
    return;
  }
  state.page = "market";
  state.routeClub = null;
}

function goToClub(clubName) {
  if (!clubName) return;
  state.page = "club";
  state.routeClub = clubName;
  state.clubFilter = "All";
  state.selectedKey = null;
  state.sectionTab = "clubs";
  saveSectionTab();
  syncHash();
  renderAll();
}

function goToMarket() {
  state.page = "market";
  state.routeClub = null;
  if (state.sectionTab === "clubs") {
    state.sectionTab = "main";
    saveSectionTab();
  }
  syncHash();
  renderAll();
}

function filterCurrentRows() {
  const rows = currentRows().slice();
  const term = state.search.trim().toLowerCase();
  const routeClub = state.page === "club" ? state.routeClub : null;
  const filtered = rows
    .filter((row) => !routeClub || row.club === routeClub)
    .filter((row) => state.clubFilter === "All" || row.club === state.clubFilter)
    .filter((row) => {
      if (!term) return true;
      const haystack = state.selectedView === "transfers"
        ? [row.club, row.player, row.buyer_club, row.seller_club, row.position, row.target_ticker]
        : [row.club, row.player, row.latest_journalist, row.latest_source, row.position, row.target_ticker];
      return haystack.join(" ").toLowerCase().includes(term);
    });

  return filtered.sort((a, b) => {
    if (state.sortMode === "latest") {
      const aDate = state.selectedView === "transfers" ? a.date : a.latest_published_at;
      const bDate = state.selectedView === "transfers" ? b.date : b.latest_published_at;
      return String(bDate).localeCompare(String(aDate));
    }
    if (state.selectedView === "transfers") {
      return Number(b.transfer_indicator || 0) - Number(a.transfer_indicator || 0) || String(b.date).localeCompare(String(a.date));
    }
    return Math.abs(b.blended_score) - Math.abs(a.blended_score) || String(b.latest_published_at).localeCompare(String(a.latest_published_at));
  });
}

function currentKey(row) {
  return state.selectedView === "transfers" ? row.transfer_key : row.group_key;
}

function realizedMixText(realizedMix) {
  const entries = Object.entries(realizedMix || {});
  if (!entries.length) return "-";
  return entries.map(([label, count]) => `${label}: ${count}`).join(" · ");
}

function signalActionText(row) {
  if (row.prediction_scope === "none") {
    return "Use this as rumor intelligence only. There is no direct public-club equity target mapped yet.";
  }
  const credibility = Number(row.credibility_score || 0);
  const blended = Number(row.blended_score || 0);
  const stage = String(row.latest_rumor_stage || "").toLowerCase();
  if (credibility >= 0.6 && blended >= 35 && ["agreed", "advanced", "medical", "official"].includes(stage)) {
    return "This is one of the stronger direct-target signals in the current set. It is worth tracking around the next trading session and comparing with similar past cases.";
  }
  if (credibility >= 0.45 && blended >= 20) {
    return "This looks monitor-worthy, but not strong enough to trust by itself. Treat it as a ranked lead, then read the supporting articles and compare the reporter history.";
  }
  return "This is weaker evidence right now. The useful move is to monitor for a better source mix, a clearer rumor stage, or more article confirmation.";
}

function mixText(mix) {
  const entries = Object.entries(mix || {});
  if (!entries.length) return "-";
  return entries.map(([label, count]) => `${label}: ${count}`).join(" · ");
}

function timelineMarkup(timeline) {
  const steps = Array.isArray(timeline) ? timeline : [];
  if (!steps.length) return "";
  return `
    <div class="timeline-strip">
      ${steps.map((step) => `
        <div class="timeline-step ${step.seen ? "is-seen" : ""} ${step.active ? "is-active" : ""}">
          <span class="timeline-dot"></span>
          <span class="timeline-label">${escapeHtml(step.label || step.stage || "-")}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function chartMarkersForRow(row) {
  const chart = row?.stock_chart;
  const dates = chart?.dates || [];
  if (!dates.length) return [];
  const knownDates = new Set(dates);
  const grouped = new Map();
  (row?.evidence_articles || []).forEach((item) => {
    const day = fmtDate(item.published_at);
    if (!day || !knownDates.has(day)) return;
    if (!grouped.has(day)) {
      grouped.set(day, {
        date: day,
        count: 0,
        sources: new Set(),
        articles: [],
      });
    }
    const entry = grouped.get(day);
    entry.count += 1;
    if (item.source) entry.sources.add(item.source);
    entry.articles.push({
      title: item.title || "Untitled article",
      url: item.url || "#",
      source: item.source || "-",
      journalist: item.journalist || "-",
    });
  });
  return Array.from(grouped.values())
    .map((entry) => ({
      date: entry.date,
      index: dates.indexOf(entry.date),
      count: entry.count,
      sourceCount: entry.sources.size,
      sources: Array.from(entry.sources).sort(),
      articles: entry.articles,
    }))
    .filter((entry) => entry.index >= 0)
    .sort((a, b) => a.index - b.index);
}

function chartPointChange(points) {
  if (!Array.isArray(points) || points.length < 2) return null;
  const first = Number(points[0]);
  const last = Number(points[points.length - 1]);
  if (!Number.isFinite(first) || !Number.isFinite(last) || first === 0) return null;
  return (last / first) - 1;
}

function markerSentimentClass(marker) {
  if (marker.sentiment === "positive") return "positive";
  if (marker.sentiment === "negative") return "negative";
  return "neutral";
}

function markerLabel(marker) {
  if (marker.kind === "match") {
    return `${marker.result || "Match"} ${marker.score || ""} vs ${marker.opponent || ""}`.trim();
  }
  if (marker.count) {
    return `${marker.count} article${marker.count === 1 ? "" : "s"}`;
  }
  return marker.date || "Event";
}

function groupChartMarkers(markers = [], pointCount = 0) {
  const grouped = new Map();
  markers.forEach((marker) => {
    const index = Number(marker.index);
    if (!Number.isFinite(index) || index < 0 || index >= pointCount) return;
    const key = `${index}:${marker.kind || "event"}`;
    if (!grouped.has(key)) {
      grouped.set(key, {
        ...marker,
        index,
        count: 0,
        sentimentCounts: { positive: 0, negative: 0, neutral: 0 },
        items: [],
      });
    }
    const entry = grouped.get(key);
    const sentiment = markerSentimentClass(marker);
    entry.count += Number(marker.count || 1);
    entry.sentimentCounts[sentiment] += 1;
    entry.items.push(marker);
    if (marker.match_date || marker.date) entry.match_date = marker.match_date || marker.date;
    if (marker.trading_date) entry.trading_date = marker.trading_date;
  });
  return Array.from(grouped.values()).map((entry) => {
    const counts = entry.sentimentCounts || {};
    const sentiment = counts.negative > counts.positive && counts.negative >= counts.neutral
      ? "negative"
      : counts.positive >= counts.neutral
        ? "positive"
        : "neutral";
    const sample = entry.items[entry.items.length - 1] || entry;
    return {
      ...entry,
      sentiment,
      result: sample.result || entry.result,
      score: sample.score || entry.score,
      opponent: sample.opponent || entry.opponent,
      title: markerLabel(sample),
    };
  }).sort((a, b) => a.index - b.index);
}

function sparklineSvg(chart, markers = []) {
  const points = chart?.points || [];
  if (!points.length) return "";
  const width = 720;
  const height = 210;
  const paddingX = 18;
  const paddingY = 16;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = Math.max(max - min, 1e-6);
  const xFor = (index) => paddingX + (index * (width - paddingX * 2)) / Math.max(points.length - 1, 1);
  const yFor = (value) => height - paddingY - ((value - min) / span) * (height - paddingY * 2);
  const linePath = points.map((value, index) => `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(2)} ${yFor(value).toFixed(2)}`).join(" ");
  const bottomY = height - paddingY;
  const areaPath = `${linePath} L ${xFor(points.length - 1).toFixed(2)} ${bottomY} L ${xFor(0).toFixed(2)} ${bottomY} Z`;
  const baselineY = yFor(100);
  const hasEvent = chart.event_index !== undefined && chart.event_index !== null && chart.event_index !== "";
  const eventX = hasEvent ? xFor(Number(chart.event_index)) : 0;
  const latestX = xFor(points.length - 1);
  const latestY = yFor(points[points.length - 1]);
  const gridLines = [0.2, 0.4, 0.6, 0.8].map((ratio) => paddingY + ratio * (height - paddingY * 2));
  const groupedMarkers = groupChartMarkers(markers, points.length);
  const visibleMarkers = groupedMarkers.length > 26 ? groupedMarkers.slice(-26) : groupedMarkers;
  const markerSvg = visibleMarkers.map((marker) => {
    const x = xFor(marker.index);
    const y = yFor(points[marker.index]);
    const sentiment = marker.sentiment || "neutral";
    const title = marker.kind === "match"
      ? `${marker.result || "Match"} ${marker.score || ""} vs ${marker.opponent || ""} (${marker.match_date || marker.date || ""})`
      : `${marker.count || 1} linked article(s) on ${marker.date || ""}`;
    if (marker.kind === "match") {
      return `
        <g class="sparkline-match-point sparkline-match-group">
          <title>${escapeHtml(title)}</title>
          <line class="sparkline-marker-guide" x1="${x}" y1="${paddingY}" x2="${x}" y2="${height - paddingY}"></line>
          <circle class="sparkline-match-dot sparkline-match-${sentiment}" cx="${x}" cy="${y}" r="${marker.count > 1 ? 6 : 4.8}"></circle>
          ${marker.count > 1 ? `<text class="sparkline-marker-count" x="${x}" y="${Math.max(paddingY + 10, y - 9)}">${marker.count}</text>` : ""}
        </g>
      `;
    }
    return `
      <g>
        <title>${escapeHtml(title)}</title>
        <line class="sparkline-marker" x1="${x}" y1="${paddingY + 4}" x2="${x}" y2="${height - paddingY}"></line>
        <circle class="sparkline-marker-dot" cx="${x}" cy="${height - paddingY}" r="${marker.count > 1 ? 4.2 : 2.8}"></circle>
      </g>
    `;
  }).join("");
  const directionClass = chartPointChange(points) >= 0 ? "positive" : "negative";
  return `
    <svg class="sparkline-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      ${gridLines.map((y) => `<line class="sparkline-grid" x1="${paddingX}" y1="${y}" x2="${width - paddingX}" y2="${y}"></line>`).join("")}
      <line class="sparkline-baseline" x1="${paddingX}" y1="${baselineY}" x2="${width - paddingX}" y2="${baselineY}"></line>
      ${hasEvent ? `<line class="sparkline-event" x1="${eventX}" y1="${paddingY}" x2="${eventX}" y2="${height - paddingY}"></line>` : ""}
      <path class="sparkline-area sparkline-area-${directionClass}" d="${areaPath}"></path>
      <path class="sparkline-line sparkline-line-${directionClass}" d="${linePath}"></path>
      ${markerSvg}
      <circle class="sparkline-latest" cx="${latestX}" cy="${latestY}" r="5.2"></circle>
    </svg>
  `;
}

function stockChartMarkup(chart, markers = []) {
  if (!chart || !(chart.points || []).length) {
    return `<div class="sparkline-empty">No stock history slice yet</div>`;
  }
  const points = chart.points || [];
  const groupedMarkers = groupChartMarkers(markers, points.length);
  const plottedMarkers = groupedMarkers.length > 26 ? groupedMarkers.slice(-26) : groupedMarkers;
  const hasMatchMarkers = markers.some((marker) => marker.kind === "match");
  const markerLabel = hasMatchMarkers ? "match result" : "linked news date";
  const totalChange = chart.latest_change ?? chartPointChange(points);
  const high = Math.max(...points);
  const low = Math.min(...points);
  const latest = points[points.length - 1];
  const direction = Number(totalChange || 0) >= 0 ? "positive" : "negative";
  const latestDate = chart.latest_date || chart.dates?.[points.length - 1] || "";
  return `
    <div class="sparkline-card market-chart-card">
      <div class="market-chart-top">
        <div>
          <span class="metric-label">${escapeHtml(chart.ticker || "Stock Path")}</span>
          <strong class="market-chart-price">${fmtNumber(latest, 2)}</strong>
          <span class="detail-meta">${escapeHtml((chart.dates || [])[0] || "")} -> ${escapeHtml(latestDate)}</span>
        </div>
        <div class="market-chart-stats">
          <span class="market-chart-stat ${direction}">Window ${fmtSignedPct(totalChange, 1)}</span>
          <span class="market-chart-stat">High ${fmtNumber(high, 1)}</span>
          <span class="market-chart-stat">Low ${fmtNumber(low, 1)}</span>
          <span class="market-chart-stat">${plottedMarkers.length}/${groupedMarkers.length} ${markerLabel}${groupedMarkers.length === 1 ? "" : "s"}</span>
        </div>
      </div>
      <div class="sparkline-wrap">${sparklineSvg(chart, plottedMarkers)}</div>
      <div class="market-chart-bottom">
        <div class="market-chart-legend">
          ${hasMatchMarkers ? `
            <span><i class="legend-dot positive"></i>Win</span>
            <span><i class="legend-dot negative"></i>Loss</span>
            <span><i class="legend-dot neutral"></i>Draw/neutral</span>
          ` : `<span><i class="legend-dot news"></i>News date</span>`}
          ${groupedMarkers.length > plottedMarkers.length ? `<span>${groupedMarkers.length - plottedMarkers.length} older marker${groupedMarkers.length - plottedMarkers.length === 1 ? "" : "s"} hidden</span>` : ""}
        </div>
        <span>${chart.event_date ? `Event ${escapeHtml(chart.event_date)}` : "Indexed to 100"}</span>
      </div>
    </div>
  `;
}

function linkedCoverageMarkup(row) {
  const markers = chartMarkersForRow(row);
  return `
    <details class="detail-card collapsible-panel">
      <summary class="section-head">
        <h3>Stock + Event Links</h3>
        <span class="section-meta">${markers.length} news-date marker${markers.length === 1 ? "" : "s"} in the stock window</span>
      </summary>
      ${stockChartMarkup(row.stock_chart, markers)}
      ${markers.length ? `
        <div class="event-link-list">
          ${markers.map((marker) => `
            <div class="event-link-item">
              <div class="headline-row">
                <strong>${escapeHtml(marker.date)}</strong>
                <span class="detail-meta">${marker.count} article${marker.count === 1 ? "" : "s"} · ${marker.sourceCount} source${marker.sourceCount === 1 ? "" : "s"}</span>
              </div>
              ${(marker.articles || []).slice(0, 3).map((article) => `
                <a href="${escapeHtml(article.url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(article.title)}</a>
              `).join("")}
            </div>
          `).join("")}
        </div>
      ` : `<p class="detail-note">No supporting article dates landed inside the current stock window yet. The event line still anchors the rumor date to the chart.</p>`}
      <p class="detail-note">This links rumor/article timing to the target-club stock window. Match-result overlays can slot into the same panel later once we add a fixtures/results feed.</p>
    </details>
  `;
}

function confirmedRelationshipMarkup(row) {
  const links = row.confirmed_transfer_links || [];
  const scopeNote = row.prediction_scope === "direct"
    ? "These are confirmed transfer rows in the historical dataset that look closest to this rumor."
    : "This rumor does not map to a public equity target yet, so the panel stays as credibility intelligence.";
  return `
    <div class="detail-card">
      <div class="section-head">
        <h3>Confirmed vs Rumored</h3>
        <span class="section-meta">${links.length} linked transfer${links.length === 1 ? "" : "s"}</span>
      </div>
      ${links.length ? `
        <div class="confirmed-link-list">
          ${links.map((item) => `
            <div class="confirmed-link-item">
              <div class="headline-row">
                <strong>${escapeHtml(item.player || row.player || "-")}</strong>
                <span class="pill pill-neutral">Match ${fmtNumber(item.match_score, 2)}</span>
                <span class="${pillClass(item.actual_label)}">${escapeHtml(item.actual_label || "unlabeled")}</span>
              </div>
              <span class="detail-meta">${fmtDate(item.date)} · ${escapeHtml(item.seller_club || "-")} → ${escapeHtml(item.buyer_club || "-")} · ${escapeHtml(item.target_role || "-")}</span>
              <div class="mini-metric-row">
                <span>T-index ${fmtNumber(item.transfer_indicator, 3)}</span>
                <span>Fee EUR ${fmtNumber(item.transfer_fee_eur, 0)}</span>
                <span>Value EUR ${fmtNumber(item.market_value_eur, 0)}</span>
                <span>CAR t+3 ${fmtNumber(item.actual_abnormal_return_p3, 4)}</span>
              </div>
            </div>
          `).join("")}
        </div>
      ` : `<p class="detail-note">No confirmed transfer match is attached yet. That usually means the rumor is current, unmatched, or outside the public-club transfer table.</p>`}
      <p class="detail-note">${scopeNote}</p>
    </div>
  `;
}

function clubStockPathPanel(clubName) {
  const path = (state.payload.club_stock_paths || {})[clubName];
  if (!path || !(path.points || []).length) {
    return `
      <div class="detail-card">
        <div class="section-head"><h3>Stock Path + Match Results</h3></div>
        <div class="sparkline-empty">No stock path is available for this club yet</div>
      </div>
    `;
  }
  const markers = path.markers || [];
  return `
    <div class="detail-card">
      <div class="section-head">
        <h3>Stock Path + Match Results</h3>
        <span class="section-meta">${escapeHtml(path.ticker || "-")} · ${markers.length} match marker${markers.length === 1 ? "" : "s"}</span>
      </div>
      ${stockChartMarkup(path, markers)}
      ${markers.length ? `
        <div class="match-marker-list">
          ${markers.slice(-6).reverse().map((marker) => `
            <div class="match-marker-item ${marker.sentiment || "neutral"}">
              <strong>${escapeHtml(marker.result || "-")} ${escapeHtml(marker.score || "")}</strong>
              <span>${escapeHtml(marker.match_date || "")} · ${escapeHtml(marker.opponent || "Opponent unknown")}</span>
              <span class="detail-meta">${escapeHtml(marker.competition || "-")} · stock date ${escapeHtml(marker.trading_date || "-")}</span>
            </div>
          `).join("")}
        </div>
      ` : `
        <p class="detail-note">No match result CSV is loaded for this club yet. Add rows to ${escapeHtml(path.match_results_path || "data/raw/matches/<club>.csv")} to mark results on this stock path.</p>
      `}
    </div>
  `;
}

function setSectionHidden(id, hidden) {
  const element = document.getElementById(id);
  if (element) element.hidden = hidden;
}

function renderOverview() {
  const overview = state.payload.overview;
  const quality = state.payload.quality_summary || {};
  const season = currentSeasonSummary();
  const dossier = activeClubDossier();
  document.getElementById("seasonLabel").textContent = dossier ? `${state.selectedSeason} · ${dossier.club}` : state.selectedSeason;
  document.getElementById("countLabel").textContent = state.selectedView === "transfers" ? "Transfers" : "Signals";
  document.getElementById("signalCount").textContent = String(
    dossier
      ? (state.selectedView === "transfers" ? season.transfer_count || 0 : season.signal_count || 0)
      : (state.selectedView === "transfers" ? season.transfer_count || 0 : season.signal_count || 0)
  );
  document.getElementById("metricSeasonReturn").textContent = fmtNumber(season.avg_realized_car_p3, 4);
  document.getElementById("metricSeasonPositive").textContent = fmtPct(season.positive_share, 1);
  if (state.selectedView === "transfers") {
    document.querySelector("#metricAccuracy").previousElementSibling.textContent = "Public Transfers";
    document.querySelector("#metricF1").previousElementSibling.textContent = "Avg Transfer Index";
    document.getElementById("metricAccuracy").textContent = String(season.transfer_count || 0);
    document.getElementById("metricF1").textContent = fmtNumber(season.avg_transfer_index, 3);
  } else {
    document.querySelector("#metricAccuracy").previousElementSibling.textContent = "XGBoost Holdout Accuracy";
    document.querySelector("#metricF1").previousElementSibling.textContent = "XGBoost Holdout Macro F1";
    document.getElementById("metricAccuracy").textContent = fmtPct(overview.xgboost_test_accuracy);
    document.getElementById("metricF1").textContent = fmtNumber(overview.xgboost_test_macro_f1, 3);
  }
  document.getElementById("metricBestStrategy").textContent = overview.best_backtest_strategy || "-";
  document.getElementById("metricBestReturn").textContent = `${fmtPct(overview.best_backtest_total_return)} total return`;
  document.getElementById("metricHistory").textContent = String(overview.historical_reference_count);
  document.getElementById("refreshStamp").textContent = fmtDate(state.payload.generated_at);
  if (dossier) {
    document.getElementById("qualityMeta").textContent = `${dossier.club} focus mode. ${dossier.live_signal_count || 0} live events on the board, ${season.realized_count || 0} realized rows in ${state.selectedSeason}, and strongest tier ${confidenceTierLabel(dossier.top_confidence_tier)}.`;
  } else {
    document.getElementById("qualityMeta").textContent = quality.live_status === "stale"
      ? `Live status: stale. Latest stored live article: ${quality.latest_live_date || "-"}. Model evidence: ${quality.model_evidence || "experimental"}.`
      : `Live status: fresh. Recent live clusters: ${quality.recent_live_clusters || 0}. Model evidence: ${quality.model_evidence || "experimental"}.`;
  }
}

function renderRouteChrome() {
  const routeBand = document.getElementById("routeBand");
  const routeTitle = document.getElementById("routeClubTitle");
  const routeMeta = document.getElementById("routeClubMeta");
  const dossier = activeClubDossier();
  const isClubPage = state.page === "club" && Boolean(state.routeClub);

  routeBand.hidden = !isClubPage;
  setSectionHidden("insightSection", isClubPage);
  setSectionHidden("watchlistSection", isClubPage);
  setSectionHidden("signalCardsSection", isClubPage);
  setSectionHidden("coverageSection", isClubPage);
  setSectionHidden("agentRunSection", isClubPage);
  setSectionHidden("scenarioSwarmSection", isClubPage);
  setSectionHidden("scenarioSimulatorSection", isClubPage);
  setSectionHidden("leaderboardsSection", isClubPage);
  setSectionHidden("trustGraphSection", isClubPage);
  setSectionHidden("clubComparisonSection", isClubPage);
  setSectionHidden("reporterProfilesSection", isClubPage);
  setSectionHidden("backtestsSection", isClubPage);
  setSectionHidden("dataFlowSection", isClubPage);

  if (!isClubPage) return;
  if (!dossier) {
    routeTitle.textContent = state.routeClub || "Club";
    routeMeta.textContent = "No dossier is available for this club in the current payload yet.";
    return;
  }
  const season = currentSeasonSummary();
  routeTitle.textContent = dossier.club;
  routeMeta.textContent = `${state.selectedSeason} · ${dossier.live_signal_count} live events · ${season.realized_count || 0} realized rows · ${dossier.recent_transfer_count} tracked transfers`;
}

function renderClubDossier() {
  const container = document.getElementById("clubDossier");
  const clubName = selectedClubName();
  const meta = document.getElementById("clubDossierMeta");
  const dossiers = state.payload.club_dossiers || {};
  const dossier = clubName ? dossiers[clubName] : null;
  if (!dossier) {
    meta.textContent = "No club dossier is available for the current selection yet.";
    container.innerHTML = `<div class="empty-detail"><h2>Club Dossier</h2><p>Select a club or click a live signal to build context around one public target.</p></div>`;
    return;
  }
  const season = activeClubSeasonSummary();
  const seasonSignalCount = state.selectedView === "transfers"
    ? (season?.transfer_count || 0)
    : (season?.signal_count || 0);
  meta.textContent = `${dossier.club} · ${state.selectedSeason} · ${seasonSignalCount} season rows · ${dossier.live_signal_count} live events · ${dossier.recent_transfer_count} recent transfers`;
  const media = clubMedia(dossier.club);
  const peak = dossier.peak_examples || {};
  const liveEvents = dossier.live_events || [];
  const reporters = dossier.reporters || [];
  const transfers = dossier.recent_transfers || [];
  const currentSignals = dossier.current_signals || [];
  container.innerHTML = `
    <div class="club-dossier">
      <div class="club-dossier-header">
        <div class="club-dossier-title">
          ${clubChip(dossier.club)}
          <div>
            <h3>${escapeHtml(dossier.club)}</h3>
            <p class="detail-note">${escapeHtml(media.entity_type || "club")} · ${escapeHtml(media.ticker || "-")} · strongest tier ${confidenceTierLabel(dossier.top_confidence_tier)}</p>
          </div>
        </div>
        <div class="headline-row">
          <span class="${confidencePillClass(dossier.top_confidence_tier)}">${confidenceTierLabel(dossier.top_confidence_tier)}</span>
          <span class="pill pill-neutral">${state.payload.latest_season}</span>
        </div>
      </div>

      <div class="club-metric-grid">
        <div class="metric-card"><span class="metric-label">Live Events</span><strong>${dossier.live_signal_count}</strong></div>
        <div class="metric-card"><span class="metric-label">Current Signals</span><strong>${dossier.current_signal_count}</strong></div>
        <div class="metric-card"><span class="metric-label">Avg Live Credibility</span><strong>${fmtNumber(dossier.avg_live_credibility, 3)}</strong></div>
        <div class="metric-card"><span class="metric-label">Avg Transfer Index</span><strong>${fmtNumber(dossier.avg_transfer_index, 3)}</strong></div>
        <div class="metric-card"><span class="metric-label">Avg Realized CAR t+3</span><strong>${fmtNumber(dossier.avg_realized_car_p3, 4)}</strong></div>
        <div class="metric-card"><span class="metric-label">Recent Transfers</span><strong>${dossier.recent_transfer_count}</strong></div>
      </div>

      ${clubStockPathPanel(dossier.club)}

      <div class="club-dossier-grid">
        <div class="detail-card">
          <div class="section-head"><h3>Live Events</h3></div>
          ${liveEvents.length ? liveEvents.map((row) => `
            <button class="dossier-list-item" data-group-key="${row.group_key}">
              <strong>${escapeHtml(row.player)}</strong>
              <span class="detail-meta">${escapeHtml(row.deal_path || row.target_role || "-")} · ${confidenceTierLabel(row.confidence_tier)} · ${row.source_count || 1} outlets</span>
              <span class="detail-note">${escapeHtml(row.signal_summary || row.primary_headline || "")}</span>
            </button>
          `).join("") : `<p class="detail-note">No live direct-target events for this club in the current payload.</p>`}
        </div>

        <div class="detail-card">
          <div class="section-head"><h3>Trusted Reporters</h3></div>
          ${reporters.length ? reporters.map((row) => `
            <div class="dossier-list-item static">
              <strong>${escapeHtml(row.journalist || "-")}</strong>
              <span class="detail-meta">${row.n_claims} claims · smoothed ${fmtNumber(row.smoothed_rate, 3)} · avg match ${fmtNumber(row.avg_match_score, 3)}</span>
            </div>
          `).join("") : `<p class="detail-note">No club-specific reporter history in the current payload yet.</p>`}
        </div>

        <div class="detail-card">
          <div class="section-head"><h3>Recent Transfers</h3></div>
          ${transfers.length ? transfers.map((row) => `
            <button class="dossier-list-item" data-transfer-key="${row.transfer_key}" data-season="${row.season}">
              <strong>${escapeHtml(row.player)}</strong>
              <span class="detail-meta">${fmtDate(row.date)} · ${escapeHtml(row.seller_club || "-")} -> ${escapeHtml(row.buyer_club || "-")} · ${escapeHtml(row.target_role || "-")}</span>
              <span class="detail-note">T-index ${fmtNumber(row.transfer_indicator, 3)} · CAR t+3 ${fmtNumber(row.actual_abnormal_return_p3, 4)}</span>
            </button>
          `).join("") : `<p class="detail-note">No recent public-target transfers for this club in the current payload.</p>`}
        </div>

        <div class="detail-card">
          <div class="section-head"><h3>Current Season Signals</h3></div>
          ${currentSignals.length ? currentSignals.map((row) => `
            <button class="dossier-list-item" data-signal-key="${row.group_key}">
              <strong>${escapeHtml(row.player)}</strong>
              <span class="detail-meta">${escapeHtml(row.deal_path || row.target_role || "-")} · Blend ${fmtNumber(row.blended_score, 1)} · ${escapeHtml(displayBlendLabel(row))}</span>
              <span class="detail-note">${escapeHtml(row.signal_summary || "")}</span>
            </button>
          `).join("") : `<p class="detail-note">No current-season rumor signals for this club in the selected season.</p>`}
        </div>
      </div>

      <div class="detail-card">
        <div class="section-head"><h3>Historical Peaks</h3></div>
        <div class="detail-grid">
          <div class="kv"><span class="list-label">Best Positive</span><strong>${peak.best_positive ? `${peak.best_positive.player} · ${fmtNumber(peak.best_positive.car_p3, 4)}` : "-"}</strong></div>
          <div class="kv"><span class="list-label">Worst Negative</span><strong>${peak.worst_negative ? `${peak.worst_negative.player} · ${fmtNumber(peak.worst_negative.car_p3, 4)}` : "-"}</strong></div>
        </div>
      </div>
    </div>
  `;
  container.querySelectorAll("[data-group-key]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedView = "rumors";
      state.selectedSeason = state.payload.latest_season;
      state.selectedKey = button.dataset.groupKey;
      renderAll();
    });
  });
  container.querySelectorAll("[data-transfer-key]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedView = "transfers";
      state.selectedSeason = button.dataset.season || state.selectedSeason;
      state.selectedKey = button.dataset.transferKey;
      renderAll();
    });
  });
  container.querySelectorAll("[data-signal-key]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedView = "rumors";
      state.selectedKey = button.dataset.signalKey;
      renderAll();
    });
  });
}

function clubComparisonCard(clubName) {
  const dossier = (state.payload.club_dossiers || {})[clubName] || {};
  const path = (state.payload.club_stock_paths || {})[clubName] || {};
  const media = clubMedia(clubName);
  const markers = path.markers || [];
  const peak = dossier.peak_examples || {};
  return `
    <div class="compare-card">
      <div class="club-dossier-header compact">
        <div class="club-dossier-title">
          ${clubChip(clubName)}
          <div>
            <h3>${escapeHtml(clubName || "-")}</h3>
            <p class="detail-note">${escapeHtml(media.ticker || "-")} · ${escapeHtml(media.entity_type || "club")}</p>
          </div>
        </div>
        <button class="route-back" data-club-route="${escapeHtml(clubName)}">Open</button>
      </div>
      <div class="club-metric-grid compact">
        <div class="metric-card"><span class="metric-label">Live Events</span><strong>${dossier.live_signal_count || 0}</strong></div>
        <div class="metric-card"><span class="metric-label">Avg Credibility</span><strong>${fmtNumber(dossier.avg_live_credibility, 3)}</strong></div>
        <div class="metric-card"><span class="metric-label">Transfer Index</span><strong>${fmtNumber(dossier.avg_transfer_index, 3)}</strong></div>
        <div class="metric-card"><span class="metric-label">CAR t+3</span><strong>${fmtNumber(dossier.avg_realized_car_p3, 4)}</strong></div>
      </div>
      ${stockChartMarkup(path, markers)}
      <div class="detail-grid compact">
        <div class="kv"><span class="list-label">Positive Share</span><strong>${fmtPct(dossier.realized_positive_share, 1)}</strong></div>
        <div class="kv"><span class="list-label">Match Markers</span><strong>${markers.length}</strong></div>
        <div class="kv"><span class="list-label">Best Peak</span><strong>${peak.best_positive ? `${peak.best_positive.player} ${fmtNumber(peak.best_positive.car_p3, 3)}` : "-"}</strong></div>
        <div class="kv"><span class="list-label">Worst Peak</span><strong>${peak.worst_negative ? `${peak.worst_negative.player} ${fmtNumber(peak.worst_negative.car_p3, 3)}` : "-"}</strong></div>
      </div>
    </div>
  `;
}

function comparisonValue(row, field, formatter = fmtNumber) {
  return formatter(row?.[field], field.includes("car") ? 4 : 3);
}

function renderClubComparison() {
  const names = availableClubNames();
  const container = document.getElementById("clubComparisonGrid");
  const selectA = document.getElementById("compareClubA");
  const selectB = document.getElementById("compareClubB");
  if (!names.length) {
    container.innerHTML = `<div class="empty-detail"><h2>No club data yet</h2><p>Rebuild the dashboard payload after loading club dossiers.</p></div>`;
    return;
  }
  if (!state.compareClubA || !names.includes(state.compareClubA)) state.compareClubA = names[0];
  if (!state.compareClubB || !names.includes(state.compareClubB) || state.compareClubB === state.compareClubA) {
    state.compareClubB = names.find((name) => name !== state.compareClubA) || names[0];
  }
  const options = names.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  selectA.innerHTML = options;
  selectB.innerHTML = options;
  selectA.value = state.compareClubA;
  selectB.value = state.compareClubB;

  const a = (state.payload.club_dossiers || {})[state.compareClubA] || {};
  const b = (state.payload.club_dossiers || {})[state.compareClubB] || {};
  const comparisonRows = [
    ["Live events", a.live_signal_count || 0, b.live_signal_count || 0],
    ["Avg live credibility", comparisonValue(a, "avg_live_credibility"), comparisonValue(b, "avg_live_credibility")],
    ["Avg transfer index", comparisonValue(a, "avg_transfer_index"), comparisonValue(b, "avg_transfer_index")],
    ["Avg realized CAR t+3", comparisonValue(a, "avg_realized_car_p3"), comparisonValue(b, "avg_realized_car_p3")],
    ["Realized positive share", fmtPct(a.realized_positive_share, 1), fmtPct(b.realized_positive_share, 1)],
    ["Recent transfers", a.recent_transfer_count || 0, b.recent_transfer_count || 0],
  ];

  container.innerHTML = `
    <div class="compare-grid">
      ${clubComparisonCard(state.compareClubA)}
      ${clubComparisonCard(state.compareClubB)}
    </div>
    <div class="detail-card comparison-table-card">
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>${escapeHtml(state.compareClubA)}</th>
            <th>${escapeHtml(state.compareClubB)}</th>
          </tr>
        </thead>
        <tbody>
          ${comparisonRows.map(([label, left, right]) => `
            <tr>
              <td>${escapeHtml(label)}</td>
              <td>${escapeHtml(left)}</td>
              <td>${escapeHtml(right)}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function reporterNames() {
  const profiles = state.payload.reporter_profiles || {};
  return Object.values(profiles)
    .sort((a, b) => Number(b.smoothed_rate || 0) - Number(a.smoothed_rate || 0) || Number(b.n_claims || 0) - Number(a.n_claims || 0))
    .map((profile) => profile.journalist)
    .filter(Boolean);
}

function renderReporterProfiles() {
  const select = document.getElementById("reporterSelect");
  const container = document.getElementById("reporterProfile");
  const profiles = state.payload.reporter_profiles || {};
  const names = reporterNames();
  if (!names.length) {
    select.innerHTML = "";
    container.innerHTML = `<div class="empty-detail"><h2>No reporter profiles yet</h2><p>Run the credibility pipeline with journalist stats, then rebuild the dashboard payload.</p></div>`;
    return;
  }
  if (!state.selectedReporter || !profiles[state.selectedReporter]) {
    state.selectedReporter = names[0];
  }
  select.innerHTML = names.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
  select.value = state.selectedReporter;
  const profile = profiles[state.selectedReporter] || {};
  const clubs = profile.clubs || [];
  const sources = profile.sources || [];
  const claims = profile.latest_claims || [];
  container.innerHTML = `
    <div class="reporter-profile">
      <div class="detail-card reporter-hero">
        <div>
          <span class="list-label">Reporter</span>
          <h3>${escapeHtml(profile.journalist || "-")}</h3>
          <p class="detail-note">${profile.n_claims || 0} claims · ${profile.realized_count || 0} realized rows · avg realized CAR t+3 ${fmtNumber(profile.avg_realized_car_p3, 4)}</p>
        </div>
        <div class="headline-row">
          <span class="pill pill-info">Smoothed ${fmtNumber(profile.smoothed_rate, 3)}</span>
          <span class="pill pill-neutral">Match ${fmtNumber(profile.avg_match_score, 3)}</span>
        </div>
      </div>
      <div class="reporter-grid">
        <div class="detail-card">
          <div class="section-head"><h3>Club Coverage</h3></div>
          <div class="list-inline">${clubs.length ? clubs.map((item) => `<span>${clubChip(item.club)} ${item.count}</span>`).join("") : "<span>No club breakdown</span>"}</div>
        </div>
        <div class="detail-card">
          <div class="section-head"><h3>Source Mix</h3></div>
          <div class="list-inline">${sources.length ? sources.map((item) => `<span>${escapeHtml(item.source)} (${item.count})</span>`).join("") : "<span>No source breakdown</span>"}</div>
        </div>
      </div>
      <div class="detail-card">
        <div class="section-head"><h3>Recent Claims</h3></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Club</th>
                <th>Player</th>
                <th>Stage</th>
                <th>Model</th>
                <th>Article</th>
              </tr>
            </thead>
            <tbody>
              ${claims.length ? claims.map((claim) => `
                <tr>
                  <td>${fmtDate(claim.published_at)}</td>
                  <td>${clubChip(claim.club)}</td>
                  <td><strong>${escapeHtml(claim.player || "-")}</strong><br><span class="detail-meta">${escapeHtml(claim.source || "-")}</span></td>
                  <td>${escapeHtml(claim.rumor_stage || "-")}</td>
                  <td><span class="${pillClass(claim.predicted_label)}">${escapeHtml(claim.predicted_label || "-")}</span></td>
                  <td>${claim.url ? `<a href="${escapeHtml(claim.url)}" target="_blank" rel="noreferrer">${escapeHtml(claim.title || "Open")}</a>` : escapeHtml(claim.title || "-")}</td>
                </tr>
              `).join("") : `<tr><td colspan="6">No recent claims attached.</td></tr>`}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function renderViewTabs() {
  document.querySelectorAll("#viewTabs button").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === state.selectedView);
  });
  document.querySelectorAll("#sectionTabs button").forEach((button) => {
    const active = button.dataset.sectionTab === state.sectionTab;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
}

function renderSeasonFilters() {
  const container = document.getElementById("seasonFilters");
  const seasons = availableSeasonsForView();
  if (!seasons.includes(state.selectedSeason)) {
    state.selectedSeason = seasons[0] || null;
  }
  container.innerHTML = "";
  seasons.forEach((season) => {
    const button = document.createElement("button");
    button.textContent = season;
    if (season === state.selectedSeason) button.classList.add("is-active");
    button.addEventListener("click", () => {
      state.selectedSeason = season;
      state.clubFilter = "All";
      state.selectedKey = null;
      renderAll();
    });
    container.appendChild(button);
  });
}

function renderClubFilters() {
  const container = document.getElementById("clubFilters");
  container.innerHTML = "";
  if (state.page === "club") {
    const clubs = Object.keys(state.payload.club_dossiers || {}).sort();
    clubs.forEach((club) => {
      const button = document.createElement("button");
      button.textContent = club;
      if (club === state.routeClub) button.classList.add("is-active");
      button.addEventListener("click", () => goToClub(club));
      container.appendChild(button);
    });
    return;
  }
  const clubs = ["All", ...new Set(currentRows().map((row) => row.club).filter(Boolean))];
  if (!clubs.includes(state.clubFilter)) {
    state.clubFilter = "All";
  }
  clubs.forEach((club) => {
    const button = document.createElement("button");
    button.textContent = club;
    if (club === state.clubFilter) button.classList.add("is-active");
    button.addEventListener("click", () => {
      state.clubFilter = club;
      state.selectedKey = null;
      renderAll();
    });
    container.appendChild(button);
  });
}

function renderWorkspaceShell() {
  const head = document.getElementById("workspaceTableHead");
  document.getElementById("workspaceTitle").textContent = state.selectedView === "transfers" ? "Confirmed Transfer Index" : "Season Signals";
  if (state.selectedView === "transfers") {
    head.innerHTML = `
      <th>Date</th>
      <th>Target Club</th>
      <th>Player</th>
      <th>Role</th>
      <th>From / To</th>
      <th>Fee</th>
      <th>Value</th>
      <th>T-Index</th>
      <th>Actual</th>
    `;
  } else {
    head.innerHTML = `
      <th>Date</th>
      <th>Club</th>
      <th>Player</th>
      <th>Stage</th>
      <th>C</th>
      <th>T</th>
      <th>R</th>
      <th>S</th>
      <th>Model</th>
      <th>Blend</th>
    `;
  }
}

function renderWorkspaceTable() {
  const rows = filterCurrentRows();
  const body = document.getElementById("workspaceTableBody");
  body.innerHTML = "";
  const season = currentSeasonSummary();
  document.getElementById("tableMeta").textContent = state.selectedView === "transfers"
    ? `${rows.length} rows · ${season.realized_count || 0} realized`
    : `${rows.length} rows · ${season.realized_count || 0} realized`;

  if (!rows.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="${state.selectedView === "transfers" ? 9 : 10}">No rows match the current filters.</td>`;
    body.appendChild(tr);
    return;
  }

  const hasWatchlistDetail = Boolean((state.payload.watchlist_details || {})[state.selectedKey]);
  if (!state.selectedKey || (!rows.some((row) => currentKey(row) === state.selectedKey) && !hasWatchlistDetail)) {
    state.selectedKey = currentKey(rows[0]);
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    if (currentKey(row) === state.selectedKey) tr.classList.add("is-selected");
    if (state.selectedView === "transfers") {
      tr.innerHTML = `
        <td>${fmtDate(row.date)}</td>
        <td>${clubChip(row.club)}</td>
        <td>${playerChip(row.player, `${row.position || "-"} · ${row.target_ticker || "-"}`)}</td>
        <td>${row.target_role}</td>
        <td>${row.seller_club || "-"} → ${row.buyer_club || "-"}</td>
        <td>EUR ${fmtNumber(row.transfer_fee_eur, 0)}</td>
        <td>EUR ${fmtNumber(row.market_value_eur, 0)}</td>
        <td>${fmtNumber(row.transfer_indicator, 3)}</td>
        <td><span class="${pillClass(row.actual_label)}">${row.actual_label || "-"}</span></td>
      `;
    } else {
      tr.innerHTML = `
        <td>${fmtDate(row.latest_published_at)}</td>
        <td>${clubChip(row.club)}</td>
        <td>${playerChip(row.player, `${row.deal_path || row.target_role || "-"} · ${row.target_ticker || "no ticker"}`)}</td>
        <td>${row.latest_rumor_stage}</td>
        <td class="score-cell">${fmtNumber(row.credibility_score, 2)}</td>
        <td class="score-cell">${fmtNumber(row.transfer_indicator, 2)}</td>
        <td class="score-cell">${fmtNumber(row.rumor_indicator, 2)}</td>
        <td class="score-cell">${fmtNumber(row.stock_context_indicator, 2)}</td>
        <td><span class="${pillClass(row.predicted_label)}">${displayModelLabel(row)}</span></td>
        <td><span class="${pillClass(row.blended_label)}">${displayBlendLabel(row)}</span><br><span class="detail-meta">E ${fmtNumber(row.event_strength, 2)} · B ${fmtNumber(row.blended_score, 1)}</span></td>
      `;
    }
    tr.addEventListener("click", () => {
      state.selectedKey = currentKey(row);
      renderWorkspaceTable();
      renderDetail();
    });
    body.appendChild(tr);
  });
}

function probabilityCard(label, value, barClass) {
  return `
    <div class="detail-card">
      <span class="list-label">${label}</span>
      <strong>${fmtPct(value)}</strong>
      <div class="prob-bar"><span class="${barClass}" style="width:${Math.max(0, Math.min(100, Number(value || 0) * 100))}%"></span></div>
    </div>
  `;
}

function memoMetric(label, value) {
  const clean = value === "" || value === undefined || value === null ? "-" : value;
  return `- ${label}: ${clean}`;
}

function buildResearchMemo(row) {
  const player = row.player || "-";
  const club = row.target_club || row.club || "-";
  const ticker = row.target_ticker || "no public ticker";
  const scope = row.prediction_scope === "direct"
    ? "Direct listed-club target"
    : "Transfer intelligence only; no direct listed-club target";
  const chart = row.stock_chart || {};
  const similar = row.similar_examples || [];
  const confirmed = row.confirmed_transfer_links || [];
  const evidence = row.evidence_articles || [];
  const headline = row.primary_headline || row.signal_summary || "No primary headline attached.";
  const nextWatch = [
    "Look for a second credible outlet or official club disclosure.",
    "Check whether match results, ownership news, earnings, or broader markets could dominate the stock move.",
    "Re-run agent-autopilot after fresh articles arrive.",
    "Treat model output as research triage, not a trading instruction.",
  ];
  const lines = [
    "# Transfer-Stock Research Memo",
    "",
    `Subject: ${player} -> ${club}`,
    `Generated from dashboard payload: ${fmtDate(state.payload?.generated_at)}`,
    "",
    "## Bottom Line",
    row.signal_summary || `${player} is the selected rumor signal for ${club}.`,
    "",
    "## Signal Snapshot",
    memoMetric("Scope", scope),
    memoMetric("Deal path", row.deal_path || row.target_role || "-"),
    memoMetric("Rumor stage", row.latest_rumor_stage || row.rumor_stage || "-"),
    memoMetric("Consensus", `${row.consensus_label || "-"} (${fmtNumber(row.consensus_score, 2)})`),
    memoMetric("Credibility", fmtNumber(row.credibility_score, 3)),
    memoMetric("Transfer indicator", fmtNumber(row.transfer_indicator, 3)),
    memoMetric("Model label", `${displayModelLabel(row)} (${fmtPct(row.prediction_confidence, 0)} confidence)`),
    memoMetric("Blended label", `${displayBlendLabel(row)} (${fmtNumber(row.blended_score, 1)})`),
    "",
    "## Evidence Stack",
    memoMetric("Primary headline", headline),
    memoMetric("Sources", `${row.source_count || evidence.length || 0}`),
    memoMetric("Articles", `${row.article_count || evidence.length || 0}`),
    memoMetric("Latest source", row.latest_source || row.source || "-"),
    memoMetric("Latest journalist", row.latest_journalist || row.journalist || "-"),
    memoMetric("Confidence reason", row.confidence_reason || "-"),
    "",
    "## Market Context",
    memoMetric("Ticker", ticker),
    memoMetric("Event date", chart.event_date || row.latest_published_at || "-"),
    memoMetric("Latest stock window date", chart.latest_date || "-"),
    memoMetric("Window change", fmtSignedPct(chart.latest_change, 1)),
    memoMetric("Prediction scope", row.prediction_scope || "-"),
    "",
    "## Similar / Confirmed Context",
  ];
  if (similar.length) {
    similar.slice(0, 3).forEach((item, index) => {
      lines.push(`${index + 1}. ${item.player || "-"} / ${item.club || "-"} -> ${item.actual_label || "unlabeled"}; CAR t+3 ${fmtNumber(item.target_abnormal_return_p3, 4)}`);
    });
  } else if (row.top_similar_example?.player) {
    const item = row.top_similar_example;
    lines.push(`1. ${item.player || "-"} / ${item.club || "-"} -> ${item.actual_label || "unlabeled"}; CAR t+3 ${fmtNumber(item.target_abnormal_return_p3, 4)}`);
  } else {
    lines.push("- No similar historical examples are attached to this row.");
  }
  if (confirmed.length) {
    lines.push("", "Confirmed-transfer links:");
    confirmed.slice(0, 3).forEach((item, index) => {
      lines.push(`${index + 1}. ${item.date || "-"}: ${item.seller_club || "-"} -> ${item.buyer_club || "-"}; match ${fmtNumber(item.match_score, 2)}; actual ${item.actual_label || "-"}`);
    });
  }
  lines.push(
    "",
    "## Risk / Caveat",
    focusRiskText(row),
    "",
    "## Next Watch Checklist",
    ...nextWatch.map((item) => `- ${item}`),
    "",
    "This memo is deterministic research context generated from local project data. It is not investment advice.",
  );
  return lines.join("\n");
}

function researchMemoMarkup(row) {
  const memo = buildResearchMemo(row);
  const encoded = encodeURIComponent(memo);
  const title = `${row.player || "signal"} research memo`;
  return `
    <div class="detail-card research-memo-card">
      <div class="section-head">
        <div>
          <h3>Research Memo</h3>
          <span class="section-meta">One-click digest for notes, demo, or follow-up research.</span>
        </div>
        <div class="memo-actions">
          <button type="button" data-copy-memo="${encoded}">Copy</button>
          <button type="button" data-download-memo="${encoded}" data-memo-title="${escapeHtml(title)}">Download</button>
        </div>
      </div>
      <pre class="research-memo-preview"><code>${escapeHtml(memo)}</code></pre>
    </div>
  `;
}

function renderTransferDetail(row) {
  const pane = document.getElementById("detailPane");
  pane.innerHTML = `
    <div class="detail-stack">
      <div class="detail-card">
        <div class="detail-head">
          <div class="detail-title">
            <div class="hero-identity">
              <div>
                <span class="detail-meta">${fmtDate(row.date)} · ${escapeHtml(row.club)}</span>
                <h2>${escapeHtml(row.player)}</h2>
              </div>
            </div>
            <div class="headline-row">
              <span class="${pillClass(row.actual_label)}">Realized ${row.actual_label || "-"}</span>
              <span class="pill pill-neutral">${row.target_role}</span>
              <span class="pill pill-neutral">${row.transfer_type}</span>
            </div>
          </div>
          <div class="big-score">${fmtNumber(row.transfer_indicator, 2)}</div>
        </div>
        <div class="score-row">
          <div class="kv"><span class="list-label">Transfer Index</span><strong>${fmtNumber(row.transfer_indicator, 3)}</strong></div>
          <div class="kv"><span class="list-label">Transfer Quality</span><strong>${fmtNumber(row.transfer_quality, 3)}</strong></div>
          <div class="kv"><span class="list-label">Realized CAR t+3</span><strong>${fmtNumber(row.actual_abnormal_return_p3, 4)}</strong></div>
          <div class="kv"><span class="list-label">Market Status</span><strong>${row.market_feature_status || "-"}</strong></div>
        </div>
      </div>

      <div class="detail-grid">
        <div class="detail-card">
          <span class="list-label">Transfer Snapshot</span>
          <div class="detail-grid">
            <div class="kv"><span class="list-label">Buyer</span><strong>${row.buyer_club || "-"}</strong></div>
            <div class="kv"><span class="list-label">Seller</span><strong>${row.seller_club || "-"}</strong></div>
            <div class="kv"><span class="list-label">Target Club</span><strong>${row.club}</strong></div>
            <div class="kv"><span class="list-label">Role</span><strong>${row.target_role}</strong></div>
            <div class="kv"><span class="list-label">Position</span><strong>${row.position || "-"}</strong></div>
            <div class="kv"><span class="list-label">Age</span><strong>${row.age || "-"}</strong></div>
          </div>
        </div>
        <div class="detail-card">
          <span class="list-label">Financials</span>
          <div class="detail-grid">
            <div class="kv"><span class="list-label">Fee</span><strong>EUR ${fmtNumber(row.transfer_fee_eur, 0)}</strong></div>
            <div class="kv"><span class="list-label">Market Value</span><strong>EUR ${fmtNumber(row.market_value_eur, 0)}</strong></div>
            <div class="kv"><span class="list-label">Fee / Value</span><strong>${fmtNumber(row.fee_to_market, 3)}</strong></div>
            <div class="kv"><span class="list-label">Value Gap</span><strong>EUR ${fmtNumber(row.market_minus_fee_eur, 0)}</strong></div>
            <div class="kv"><span class="list-label">Ticker</span><strong>${row.target_ticker || "-"}</strong></div>
            <div class="kv"><span class="list-label">Entity Type</span><strong>${row.target_entity_type || "-"}</strong></div>
          </div>
        </div>
      </div>

      <div class="detail-card">
        <span class="list-label">Market Context</span>
        <div class="detail-grid">
          <div class="kv"><span class="list-label">Event Trading Date</span><strong>${row.event_trading_date || "-"}</strong></div>
          <div class="kv"><span class="list-label">Trading Offset</span><strong>${row.event_trading_offset_days || "-"}</strong></div>
          <div class="kv"><span class="list-label">Relative Volume</span><strong>${fmtNumber(row.relative_volume_20d, 3)}</strong></div>
          <div class="kv"><span class="list-label">Pre Volatility</span><strong>${fmtNumber(row.pre_volatility_20d, 4)}</strong></div>
        </div>
      </div>
    </div>
  `;
}

function renderRumorDetail(row) {
  const pane = document.getElementById("detailPane");
  const scopePill = row.prediction_scope === "direct"
    ? `<span class="pill pill-positive">Direct target</span>`
    : `<span class="pill pill-neutral">No public target</span>`;
  const evidenceRows = row.evidence_articles || [];
  const evidenceMarkup = evidenceRows.length
    ? evidenceRows.map((item) => `
        <div class="evidence-item">
          <a href="${escapeHtml(item.url || "#")}" target="_blank" rel="noreferrer">${escapeHtml(item.title || "Untitled article")}</a>
          <span class="detail-meta">${fmtDate(item.published_at)} · ${escapeHtml(item.source || "-")} · ${escapeHtml(item.journalist || "-")} · ${escapeHtml(item.rumor_stage || "unclear")}</span>
        </div>
      `).join("")
    : `<p class="detail-note">No article-level evidence was attached to this signal payload yet. Re-run the live analyze step after a fresh fetch to enrich the dossier.</p>`;
  const chartMarkers = chartMarkersForRow(row);

  pane.innerHTML = `
    <div class="detail-stack">
      <div class="detail-card">
        <div class="detail-head">
          <div class="detail-title">
            <div class="hero-identity">
              <div>
                <span class="detail-meta">${fmtDate(row.latest_published_at)} · ${escapeHtml(row.club)}</span>
                <h2>${escapeHtml(row.player)}</h2>
              </div>
            </div>
            <div class="headline-row">
              <span class="${pillClass(row.blended_label)}">Blend ${displayBlendLabel(row)}</span>
              <span class="${pillClass(row.predicted_label)}">Model ${displayModelLabel(row)}</span>
              <span class="${confidencePillClass(row.confidence_tier)}">${confidenceTierLabel(row.confidence_tier)}</span>
              <span class="pill pill-neutral">${row.latest_rumor_stage}</span>
              ${scopePill}
            </div>
          </div>
          <div class="big-score">${fmtNumber(row.blended_score, 1)}</div>
        </div>
        <div class="score-row">
          <div class="kv"><span class="list-label">Journalist</span><strong>${row.latest_journalist || "-"}</strong></div>
          <div class="kv"><span class="list-label">Source</span><strong>${row.latest_source || "-"}</strong></div>
          <div class="kv"><span class="list-label">Counterparty</span><strong>${row.counterparty_club || "-"}</strong></div>
          <div class="kv"><span class="list-label">Blend Confidence</span><strong>${fmtPct(row.blended_confidence)}</strong></div>
          <div class="kv"><span class="list-label">Model Confidence</span><strong>${fmtPct(row.prediction_confidence)}</strong></div>
        </div>
      </div>

      <div class="detail-grid">
        <div class="detail-card">
          <span class="list-label">Transfer Snapshot</span>
          <div class="detail-grid">
            <div class="kv"><span class="list-label">Direction</span><strong>${row.direction}</strong></div>
            <div class="kv"><span class="list-label">Deal Path</span><strong>${row.deal_path || "-"}</strong></div>
            <div class="kv"><span class="list-label">Type</span><strong>${row.transfer_type}</strong></div>
            <div class="kv"><span class="list-label">Position</span><strong>${row.position}</strong></div>
            <div class="kv"><span class="list-label">Age</span><strong>${row.age || "-"}</strong></div>
            <div class="kv"><span class="list-label">Market Value</span><strong>EUR ${fmtNumber(row.market_value_eur, 0)}</strong></div>
          </div>
        </div>
        <div class="detail-card">
          <span class="list-label">Target Mapping</span>
          <div class="detail-grid">
            <div class="kv"><span class="list-label">Buyer</span><strong>${row.buyer_club || "-"}</strong></div>
            <div class="kv"><span class="list-label">Seller</span><strong>${row.seller_club || "-"}</strong></div>
            <div class="kv"><span class="list-label">Target Club</span><strong>${row.target_club || "-"}</strong></div>
            <div class="kv"><span class="list-label">Ticker</span><strong>${row.target_ticker || "-"}</strong></div>
            <div class="kv"><span class="list-label">Role</span><strong>${row.target_role || "-"}</strong></div>
            <div class="kv"><span class="list-label">Scope</span><strong>${row.prediction_scope || "-"}</strong></div>
            <div class="kv"><span class="list-label">Fee</span><strong>EUR ${fmtNumber(row.transfer_fee_eur, 0)}</strong></div>
            <div class="kv"><span class="list-label">Market Index</span><strong>${row.target_market_index || "-"}</strong></div>
            <div class="kv"><span class="list-label">Exchange TZ</span><strong>${row.target_exchange_timezone || "-"}</strong></div>
          </div>
          <p class="detail-note">We only treat stock impact as a direct prediction when a rumor maps to a public target. Otherwise the right output is credibility plus transfer quality, not a fake equity forecast.</p>
        </div>
      </div>

      <div class="detail-card">
        <span class="list-label">How To Use This</span>
        <p class="detail-note">${signalActionText(row)}</p>
        <p class="detail-note">${escapeHtml(row.signal_summary || "")}</p>
      </div>

      ${researchMemoMarkup(row)}

      <div class="detail-grid">
        <div class="detail-card">
          <span class="list-label">Consensus + Timeline</span>
          <div class="headline-row">
            <span class="${consensusPillClass(row.consensus_label)}">${escapeHtml(row.consensus_label || "Mixed")}</span>
            <span class="pill pill-neutral">Score ${fmtNumber(row.consensus_score, 2)}</span>
          </div>
          <p class="detail-note">${escapeHtml(row.confidence_reason || "")}</p>
          ${timelineMarkup(row.timeline)}
        </div>
        <div class="detail-card">
          <span class="list-label">Target Stock Snapshot</span>
          ${stockChartMarkup(row.stock_chart, chartMarkers)}
        </div>
      </div>

      ${linkedCoverageMarkup(row)}

      ${confirmedRelationshipMarkup(row)}

      <div class="detail-card">
        <span class="list-label">Merged Rumor Event</span>
        <div class="detail-grid">
          <div class="kv"><span class="list-label">Event Strength</span><strong>${fmtNumber(row.event_strength, 3)}</strong></div>
          <div class="kv"><span class="list-label">Confidence Tier</span><strong>${confidenceTierLabel(row.confidence_tier)}</strong></div>
          <div class="kv"><span class="list-label">Unique Headlines</span><strong>${row.unique_headline_count || row.article_count || 0}</strong></div>
          <div class="kv"><span class="list-label">Duplicate Articles</span><strong>${row.duplicate_article_count || 0}</strong></div>
          <div class="kv"><span class="list-label">Outlet Count</span><strong>${row.source_count || 0}</strong></div>
          <div class="kv"><span class="list-label">Direct Articles</span><strong>${row.direct_article_count || 0}</strong></div>
          <div class="kv"><span class="list-label">Supporting Articles</span><strong>${row.supporting_article_count || 0}</strong></div>
          <div class="kv"><span class="list-label">Direction Mix</span><strong>${mixText(row.direction_mix)}</strong></div>
          <div class="kv"><span class="list-label">Stage Mix</span><strong>${mixText(row.stage_mix)}</strong></div>
        </div>
        <p class="detail-note">${escapeHtml(row.primary_headline || "No primary headline attached.")}</p>
        <p class="detail-note">${escapeHtml(row.confidence_reason || "")}</p>
        <div class="list-inline">${(row.source_breakdown || []).map((item) => `<span>${escapeHtml(item.source)} (${item.count})</span>`).join("")}</div>
      </div>

      <div class="detail-card">
        <span class="list-label">Indicators</span>
        <div class="detail-grid">
          <div class="kv"><span class="list-label">Credibility</span><strong>${fmtNumber(row.credibility_score, 3)}</strong></div>
          <div class="kv"><span class="list-label">Transfer</span><strong>${fmtNumber(row.transfer_indicator, 3)}</strong></div>
          <div class="kv"><span class="list-label">Rumor</span><strong>${fmtNumber(row.rumor_indicator, 3)}</strong></div>
          <div class="kv"><span class="list-label">Stock Context</span><strong>${fmtNumber(row.stock_context_indicator, 3)}</strong></div>
          <div class="kv"><span class="list-label">Entity Match</span><strong>${fmtNumber(row.entity_match_indicator, 3)}</strong></div>
          <div class="kv"><span class="list-label">Match Score</span><strong>${fmtNumber(row.match_score, 3)}</strong></div>
        </div>
      </div>

      <div class="probability-grid">
        ${probabilityCard("Negative", row.predicted_probabilities.negative, "bar-negative")}
        ${probabilityCard("Neutral", row.predicted_probabilities.neutral, "bar-neutral")}
        ${probabilityCard("Positive", row.predicted_probabilities.positive, "bar-positive")}
      </div>

      <div class="detail-card">
        <span class="list-label">Coverage</span>
        <div class="detail-grid">
          <div class="kv"><span class="list-label">Articles</span><strong>${row.article_count}</strong></div>
          <div class="kv"><span class="list-label">Unique Headlines</span><strong>${row.unique_headline_count || row.article_count || 0}</strong></div>
          <div class="kv"><span class="list-label">Outlets</span><strong>${row.source_count}</strong></div>
          <div class="kv"><span class="list-label">Realized Label</span><strong>${row.realized_label || "-"}</strong></div>
          <div class="kv"><span class="list-label">Realized CAR t+3</span><strong>${fmtNumber(row.target_abnormal_return_p3, 4)}</strong></div>
        </div>
        <div class="list-inline">${row.sources.map((source) => `<span>${source}</span>`).join("")}</div>
      </div>

      <div class="detail-card">
        <div class="section-head"><h3>Supporting Articles</h3></div>
        ${(row.headline_variants || []).length ? `
          <div class="headline-variants">
            ${(row.headline_variants || []).map((item) => `
              <div class="variant-pill">
                <strong>${escapeHtml(item.title || "-")}</strong>
                <span class="detail-meta">${item.article_count} articles · ${item.source_count} sources</span>
              </div>
            `).join("")}
          </div>
        ` : ""}
        <div class="evidence-list">${evidenceMarkup}</div>
      </div>

      <div class="detail-card">
        <div class="section-head"><h3>Similar Historical Cases</h3></div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Similarity</th>
                <th>Date</th>
                <th>Club</th>
                <th>Player</th>
                <th>Actual</th>
                <th>CAR t+3</th>
              </tr>
            </thead>
            <tbody>
              ${row.similar_examples.map((example) => `
                <tr>
                  <td>${fmtNumber(example.similarity, 3)}</td>
                  <td>${example.date}</td>
                  <td>${example.club}</td>
                  <td><strong>${example.player}</strong><br><span class="detail-meta">${example.rumor_stage} · ${example.journalist || "-"}</span></td>
                  <td><span class="${pillClass(example.actual_label)}">${example.actual_label}</span></td>
                  <td>${fmtNumber(example.target_abnormal_return_p3, 4)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function renderDetail() {
  let row = currentRows().find((item) => currentKey(item) === state.selectedKey);
  if (!row && state.selectedView === "rumors") {
    row = (state.payload.watchlist_details || {})[state.selectedKey];
  }
  if (!row) {
    const label = state.selectedView === "transfers" ? "Transfer Detail" : "Signal Detail";
    document.getElementById("detailPane").innerHTML = `<div class="empty-detail"><h2>${label}</h2><p>No row selected.</p></div>`;
    return;
  }
  if (state.selectedView === "transfers") {
    renderTransferDetail(row);
    return;
  }
  renderRumorDetail(row);
}

function renderSeasonHistory() {
  const body = document.getElementById("seasonHistoryTable");
  const head = document.getElementById("seasonHistoryHead");
  const dossier = activeClubDossier();
  if (state.selectedView === "transfers") {
    document.getElementById("seasonHistoryTitle").textContent = dossier ? `${dossier.club} Transfer Seasons` : "Transfer Seasons";
    document.getElementById("seasonHistoryMeta").textContent = dossier
      ? "Compare this club's confirmed transfer history and realized market reaction by season."
      : "Use this to compare confirmed transfer quality and realized market reaction by season.";
    const rows = dossier?.transfer_season_history || availableSeasonsForView().map((season) => state.payload.transfer_season_summaries[season]);
    head.innerHTML = `
      <th>Season</th>
      <th>Transfers</th>
      <th>Realized Rows</th>
      <th>Avg T-Index</th>
      <th>Avg CAR t+3</th>
      <th>Positive Share</th>
    `;
    body.innerHTML = rows
      .map((summary) => {
        const season = summary.season;
        const active = season === state.selectedSeason ? " class=\"is-selected\"" : "";
        return `
          <tr${active} data-season="${season}">
            <td><strong>${season}</strong></td>
            <td>${summary.transfer_count}</td>
            <td>${summary.realized_count}</td>
            <td>${fmtNumber(summary.avg_transfer_index, 3)}</td>
            <td>${fmtNumber(summary.avg_realized_car_p3, 4)}</td>
            <td>${fmtPct(summary.positive_share, 1)}</td>
          </tr>
        `;
      })
      .join("");
  } else {
    document.getElementById("seasonHistoryTitle").textContent = dossier ? `${dossier.club} Signal History` : "Season History";
    document.getElementById("seasonHistoryMeta").textContent = dossier
      ? "Compare this club's rumor signals and realized outcomes by season."
      : "Switch years above, or use this table to compare them side by side.";
    const rows = dossier?.rumor_season_history || availableSeasonsForView().map((season) => state.payload.season_summaries[season]);
    head.innerHTML = `
      <th>Season</th>
      <th>Signals</th>
      <th>Direct</th>
      <th>Realized Rows</th>
      <th>Avg CAR t+3</th>
      <th>Positive Share</th>
    `;
    body.innerHTML = rows
      .map((summary) => {
        const season = summary.season;
        const active = season === state.selectedSeason ? " class=\"is-selected\"" : "";
        return `
          <tr${active} data-season="${season}">
            <td><strong>${season}</strong></td>
            <td>${summary.signal_count}</td>
            <td>${summary.direct_count}</td>
            <td>${summary.realized_count}</td>
            <td>${fmtNumber(summary.avg_realized_car_p3, 4)}</td>
            <td>${fmtPct(summary.positive_share, 1)}</td>
          </tr>
        `;
      })
      .join("");
  }

  body.querySelectorAll("tr[data-season]").forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedSeason = row.dataset.season;
      state.clubFilter = "All";
      state.selectedKey = null;
      renderAll();
    });
  });
}

function renderWatchlist() {
  const body = document.getElementById("watchlistTable");
  const rows = state.payload.live_watchlist || [];
  const meta = state.payload.live_watchlist_meta || {};
  const latest = meta.latest_published_at ? fmtDate(meta.latest_published_at) : "unknown";
  const daysStale = meta.days_stale === "" || meta.days_stale === undefined ? "-" : meta.days_stale;
  document.getElementById("watchlistMeta").textContent = meta.is_stale
    ? `Latest article: ${latest} · stale by ${daysStale} days. Run the live refresh command for a fresher watchlist.`
    : `Latest article: ${latest} · ${meta.recent_cluster_count || rows.length} recent clusters in the last ${meta.window_days || 21} days.`;
  if (!rows.length || (meta.is_stale && !(meta.recent_cluster_count > 0))) {
    body.innerHTML = `<tr><td colspan="8">No fresh live direct-target rumors in the payload yet. Run the fetch step, then the analyze step.</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map((row) => `
      <tr data-group-key="${row.group_key}">
        <td>${fmtDate(row.published_at)}</td>
        <td>${clubChip(row.target_club || row.club)}</td>
        <td>${playerChip(row.player, `${row.deal_path || row.target_role || "-"} · ${row.target_ticker || "-"}`)}</td>
        <td>${confidenceTierLabel(row.confidence_tier)}</td>
        <td>${row.rumor_stage || "-"}</td>
        <td>${fmtNumber(row.credibility_score, 2)}</td>
        <td><span class="${pillClass(row.predicted_label)}">${row.predicted_label || "-"}</span></td>
        <td><span class="${pillClass(row.blended_label)}">${row.blended_label || "-"}</span><br><span class="detail-meta">E ${fmtNumber(row.event_strength, 2)} · ${confidenceTierLabel(row.confidence_tier)}</span></td>
      </tr>
    `)
    .join("");
  body.querySelectorAll("tr[data-group-key]").forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedView = "rumors";
      state.selectedSeason = state.payload.latest_season;
      state.clubFilter = "All";
      state.selectedKey = row.dataset.groupKey;
      renderAll();
    });
  });
}

function renderLiveSignalCards() {
  const container = document.getElementById("liveSignalCards");
  const rows = state.payload.live_watchlist || [];
  if (!rows.length) {
    container.innerHTML = `<div class="signal-card"><span class="metric-label">No live cards yet</span><strong>Run the live refresh workflow</strong><span class="detail-meta">The card view appears once direct-target live rumors are in the payload.</span></div>`;
    return;
  }
  container.innerHTML = rows.slice(0, 6).map((row) => `
    <button class="signal-card" data-group-key="${row.group_key}">
      <div class="signal-card-top">
        ${clubChip(row.target_club || row.club)}
        <span class="${pillClass(row.blended_label)}">${row.blended_label || "-"}</span>
        <span class="${confidencePillClass(row.confidence_tier)}">${confidenceTierLabel(row.confidence_tier)}</span>
      </div>
      <div class="signal-card-player">
        <div>
          <strong>${escapeHtml(row.player)}</strong>
          <span class="detail-meta">${fmtDate(row.published_at)} · ${escapeHtml(row.deal_path || row.target_role || "-")} · ${escapeHtml(row.target_ticker || "-")}</span>
        </div>
      </div>
      <div class="headline-row">
        <span class="${consensusPillClass(row.consensus_label)}">${escapeHtml(row.consensus_label || "Mixed")}</span>
        <span class="pill pill-neutral">Consensus ${fmtNumber(row.consensus_score, 2)}</span>
      </div>
      ${timelineMarkup(row.timeline)}
      ${stockChartMarkup(row.stock_chart)}
      <div class="signal-card-metrics">
        <span>${row.unique_headline_count || row.article_count || 1} headlines</span>
        <span>${row.source_count || 1} outlets</span>
        <span>Cred ${fmtNumber(row.credibility_score, 2)}</span>
        <span>Model ${escapeHtml(row.predicted_label || "-")}</span>
        <span>${confidenceTierLabel(row.confidence_tier)}</span>
      </div>
      <div class="detail-meta">${escapeHtml(row.signal_summary || "")}</div>
      ${row.top_similar_example && row.top_similar_example.player ? `<div class="detail-meta">Closest comp: ${escapeHtml(row.top_similar_example.player)} / ${escapeHtml(row.top_similar_example.club)} · ${escapeHtml(row.top_similar_example.actual_label || "unlabeled")}</div>` : ""}
    </button>
  `).join("");
  container.querySelectorAll("button[data-group-key]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedView = "rumors";
      state.selectedSeason = state.payload.latest_season;
      state.clubFilter = "All";
      state.selectedKey = button.dataset.groupKey;
      renderAll();
    });
  });
}

function renderTakeaways() {
  const container = document.getElementById("takeawayCards");
  const rows = state.payload.takeaways || [];
  if (!rows.length) {
    container.innerHTML = `<div class="insight-card"><span class="metric-label">No summary yet</span><strong>Run a fresh analyze step</strong><span class="detail-meta">The dashboard can build takeaways once the live and historical files are in sync.</span></div>`;
    return;
  }
  container.innerHTML = rows.map((row) => `
    <div class="insight-card ${row.tone || ""}">
      <span class="metric-label">${row.title || ""}</span>
      <strong>${row.primary || "-"}</strong>
      <span class="detail-meta">${row.secondary || ""}</span>
    </div>
  `).join("");
}

function renderHeroObservatory() {
  const container = document.getElementById("heroSignalVisual");
  const freshness = document.getElementById("heroFreshness");
  if (!container || !state.payload) return;
  const row = topFocusSignal();
  const meta = state.payload.live_watchlist_meta || {};
  if (freshness) {
    freshness.textContent = meta.latest_published_at
      ? `${meta.is_stale ? "Archive window" : "Live window"} · ${fmtDate(meta.latest_published_at)}`
      : "No live window";
  }
  if (!row) {
    container.innerHTML = `
      <div class="observatory-empty">
        <span class="metric-label">Evidence trajectory</span>
        <strong>No current signal loaded</strong>
        <span>Run today's research cycle to assemble the field.</span>
      </div>
    `;
    return;
  }
  const credibility = clampNumber(Number(row.credibility_score || 0), 0, 1);
  const confidence = clampNumber(Number(row.prediction_confidence || 0), 0, 1);
  const sources = Math.min(Number(row.source_count || 1), 5) / 5;
  const blend = clampNumber(Math.abs(Number(row.blended_score || 0)) / 100, 0.08, 1);
  const bars = [
    Math.max(18, credibility * 88),
    Math.max(14, sources * 74),
    Math.max(20, confidence * 94),
    Math.max(16, blend * 82),
    Math.max(24, ((credibility + confidence + sources) / 3) * 100),
    Math.max(15, ((credibility + blend) / 2) * 86),
    Math.max(22, ((confidence + sources) / 2) * 96),
  ];
  const targetClub = row.target_club || row.club || "-";
  const scope = row.prediction_scope === "direct" ? "Listed-club exposure" : "Transfer intelligence only";
  container.innerHTML = `
    <div class="observatory-trajectory" aria-hidden="true">
      <span class="trajectory-axis"></span>
      ${bars.map((height, index) => `<i style="--trajectory-height:${height.toFixed(0)}%; --trajectory-delay:${index * 55}ms"></i>`).join("")}
      <span class="trajectory-signal" style="--trajectory-position:${Math.max(10, Math.min(88, credibility * 92))}%"></span>
    </div>
    <div class="observatory-signal-copy">
      <span class="metric-label">${escapeHtml(scope)}</span>
      <h2>${escapeHtml(row.player || "-")}</h2>
      <div class="observatory-club">${clubChip(targetClub)}</div>
      <p>${escapeHtml(row.signal_summary || row.primary_headline || "Top current evidence cluster.")}</p>
    </div>
    <div class="observatory-score-row">
      <span><small>Credibility</small><strong>${fmtPct(credibility, 0)}</strong></span>
      <span><small>Consensus</small><strong>${row.source_count || 1}</strong></span>
      <span><small>Confidence</small><strong>${fmtPct(confidence, 0)}</strong></span>
    </div>
  `;
}

function topFocusSignal() {
  const rows = state.payload.live_watchlist || [];
  if (!rows.length) return null;
  return rows.slice().sort((a, b) => {
    const aScore = Math.abs(Number(a.blended_score || 0)) + Number(a.credibility_score || 0) + Number(a.prediction_confidence || 0);
    const bScore = Math.abs(Number(b.blended_score || 0)) + Number(b.credibility_score || 0) + Number(b.prediction_confidence || 0);
    return bScore - aScore;
  })[0];
}

function focusRiskText(row) {
  if (!row) return "No live signal is loaded yet, so the useful next move is refreshing live news and rebuilding the dashboard.";
  if (row.prediction_scope !== "direct") {
    return "This maps to transfer intelligence, not a direct public equity target. Do not invent a stock impact where no listed-club ticker is attached.";
  }
  if ((state.dataQuality || {}).overall_status === "needs_refresh") {
    return "Data quality says the board needs refresh, so treat the current read as stale until live news and market context are rebuilt.";
  }
  if (Number(row.source_count || 0) <= 1) {
    return "The source mix is thin. A second credible outlet or official confirmation would materially improve confidence.";
  }
  return "Even credible football rumors can be overwhelmed by match results, ownership news, liquidity, earnings, or broader markets.";
}

function focusTrustLabel(row) {
  if (!row) return "Needs data";
  const tier = row.confidence_tier || "";
  if (tier === "broad_consensus") return "High consensus";
  if (tier === "strong") return "Strong but monitor";
  if (tier === "developing") return "Developing";
  return "Thin evidence";
}

function daysSince(value, referenceValue = null) {
  if (!value) return null;
  const date = new Date(value);
  const reference = referenceValue ? new Date(referenceValue) : new Date();
  if (Number.isNaN(date.getTime()) || Number.isNaN(reference.getTime())) return null;
  return Math.max(0, (reference.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
}

function triageRead(row) {
  const quality = state.dataQuality || {};
  const credibility = Number(row.credibility_score || 0);
  const confidence = Number(row.prediction_confidence || 0);
  const sourceCount = Number(row.source_count || 0);
  const blend = Math.abs(Number(row.blended_score || 0));
  const stage = String(row.latest_rumor_stage || row.rumor_stage || "").toLowerCase();
  const direct = row.prediction_scope === "direct";
  const generatedAt = state.payload?.generated_at || null;
  const ageDays = daysSince(row.latest_published_at || row.published_at, generatedAt);
  const stageBoosts = {
    official: 0.2,
    medical: 0.18,
    agreed: 0.16,
    advanced: 0.13,
    bid: 0.1,
    talks: 0.07,
    linked: 0.03,
  };
  const recencyScore = ageDays === null ? 0.35 : clampNumber(1 - (ageDays / 10), 0, 1);
  const evidenceScore = clampNumber((credibility * 0.42) + (confidence * 0.24) + (Math.min(sourceCount, 4) / 4 * 0.2) + (stageBoosts[stage] || 0.04), 0, 1);
  const marketScore = direct ? clampNumber((blend / 70 * 0.66) + (confidence * 0.34), 0, 1) : 0;
  const readiness = clampNumber((evidenceScore * 0.48) + (marketScore * 0.32) + (recencyScore * 0.2), 0, 1);

  if (!direct) {
    return {
      label: "Intel only",
      className: "triage-intel",
      score: clampNumber((evidenceScore * 0.7) + (recencyScore * 0.3), 0, 1),
      action: "Track credibility",
      reason: "No listed-club equity target is mapped, so the useful output is source and transfer intelligence.",
    };
  }
  if (quality.available && quality.overall_status === "needs_refresh") {
    return {
      label: "Refresh first",
      className: "triage-refresh",
      score: readiness,
      action: "Audit data",
      reason: "The signal maps to a public club, but the latest data-quality audit says the board needs a refresh.",
    };
  }
  if (readiness >= 0.68 && sourceCount >= 2) {
    return {
      label: "Monitor",
      className: "triage-monitor",
      score: readiness,
      action: "Open signal",
      reason: "Direct public-club target with comparatively strong evidence, source breadth, and model confidence.",
    };
  }
  if (readiness >= 0.48 || sourceCount >= 2 || credibility >= 0.55) {
    return {
      label: "Verify",
      className: "triage-verify",
      score: readiness,
      action: "Check sources",
      reason: "Potentially relevant, but it needs better source mix, clearer stage, or a cleaner market link.",
    };
  }
  return {
    label: "Low priority",
    className: "triage-low",
    score: readiness,
    action: "Keep in queue",
    reason: "Evidence is thin relative to the rest of the watchlist.",
  };
}

function triageRows(limit = 4) {
  return (state.payload.live_watchlist || [])
    .map((row) => ({ row, triage: triageRead(row) }))
    .sort((a, b) => Number(b.triage.score || 0) - Number(a.triage.score || 0))
    .slice(0, limit);
}

function renderFocusBrief() {
  const container = document.getElementById("focusBrief");
  if (!container || !state.payload) return;
  const row = topFocusSignal();
  const quality = state.dataQuality || {};
  const agent = state.agent || {};
  const autopilot = state.autopilot || {};
  if (!row) {
    container.innerHTML = `
      <div class="focus-brief empty">
        <div>
          <span class="metric-label">Focus Brief</span>
          <h3>No live signal loaded yet</h3>
          <p>Run the refresh workflow, then this panel will compress the board into a first-read path.</p>
        </div>
        <button type="button" data-jump="dataQualitySection">Check refresh commands</button>
      </div>
    `;
    return;
  }
  const targetClub = row.target_club || row.club || "-";
  const groupKey = row.group_key || "";
  const impact = row.prediction_scope === "direct"
    ? `${escapeHtml(displayBlendLabel(row))} / ${escapeHtml(row.predicted_label || "-")}`
    : "intel only";
  const agentCitations = (agent.evidence_citations || []).length;
  const autopilotGoal = (autopilot.selected_goal || {}).goal || "";
  container.innerHTML = `
    <div class="focus-brief">
      <div class="focus-brief-main">
        <span class="metric-label">Start Here</span>
        <h3>${escapeHtml(row.player || "-")} -> ${escapeHtml(targetClub)}</h3>
        <p>${escapeHtml(row.signal_summary || row.primary_headline || "This is the strongest current item by credibility, model confidence, and signal magnitude.")}</p>
        <div class="focus-action-row">
          <button type="button" data-select-signal="${escapeHtml(groupKey)}">Open signal</button>
          <button type="button" data-jump="agentRunSection">View RAG lens</button>
          <button type="button" data-jump="signalCardsSection">Compare live cards</button>
        </div>
      </div>
      <div class="focus-brief-grid">
        <div class="focus-mini-card">
          <span class="metric-label">Trust</span>
          <strong>${escapeHtml(focusTrustLabel(row))}</strong>
          <span>${row.source_count || 1} source${Number(row.source_count || 1) === 1 ? "" : "s"} · cred ${fmtNumber(row.credibility_score, 2)}</span>
        </div>
        <div class="focus-mini-card">
          <span class="metric-label">Market Read</span>
          <strong>${impact}</strong>
          <span>${escapeHtml(row.target_ticker || "no public ticker")} · confidence ${fmtPct(row.prediction_confidence, 0)}</span>
        </div>
        <div class="focus-mini-card">
          <span class="metric-label">Evidence</span>
          <strong>${agentCitations || "-"} citations</strong>
          <span>${escapeHtml((agent.rag_lens || {}).retriever || "hybrid RAG")} · quality ${quality.overall_score !== undefined ? fmtPct(quality.overall_score, 0) : "-"}</span>
        </div>
        <div class="focus-mini-card">
          <span class="metric-label">Autopilot</span>
          <strong>${autopilot.available ? "Ready" : "Not run"}</strong>
          <span>${escapeHtml(autopilotGoal || "Run agent-autopilot for a compressed update")}</span>
        </div>
      </div>
      <div class="focus-caution">
        <span class="metric-label">Do Not Over-Read</span>
        <p>${escapeHtml(focusRiskText(row))}</p>
      </div>
    </div>
  `;
}

function renderMarketCockpit() {
  const container = document.getElementById("marketCockpit");
  if (!container || !state.payload) return;
  const watchlist = state.payload.live_watchlist || [];
  const meta = state.payload.live_watchlist_meta || {};
  const quality = state.dataQuality || {};
  const top = watchlist[0] || {};
  const publicClubs = allCurrentPublicClubs();
  const qualityScore = quality.available ? fmtPct(quality.overall_score, 0) : "-";
  const qualityStatus = quality.available ? (quality.overall_status || "unknown").replaceAll("_", " ") : "not audited";
  const freshnessLabel = meta.is_stale ? "Stale" : "Fresh";
  const freshnessDetail = meta.latest_published_at
    ? `${fmtDate(meta.latest_published_at)} · ${meta.recent_cluster_count || watchlist.length} recent clusters`
    : "No live window loaded";
  const warnings = quality.available ? (quality.warnings || []) : [];
  const topGroupKey = top.group_key || "";
  const triage = triageRows(4);
  const operator = state.operator || {};
  const operatorRuntime = state.operatorRuntime || {};
  const operatorStatus = operatorRuntime.status && operatorRuntime.status !== "idle"
    ? operatorRuntime.status
    : (operator.status || "not run");
  const operatorRunning = operatorStatus === "running";
  const operatorSummary = operatorRuntime.error || operator.summary || "One research cycle turns the full pipeline into a current evidence-backed brief.";
  container.innerHTML = `
    <div class="cockpit-shell">
      <div class="cockpit-main">
        <div class="cockpit-kicker">
          <span class="${meta.is_stale ? "status-dot status-warn" : "status-dot status-good"}"></span>
          <span>${escapeHtml(freshnessLabel)} live intelligence</span>
        </div>
        <div class="cockpit-title-row">
          <div>
            <span class="metric-label">Top Live Signal</span>
            <h2>${top.player ? `${escapeHtml(top.player)} · ${escapeHtml(top.target_club || top.club || "-")}` : "Run a live refresh to populate the board"}</h2>
          </div>
          ${top.confidence_tier ? `<span class="${confidencePillClass(top.confidence_tier)}">${confidenceTierLabel(top.confidence_tier)}</span>` : ""}
        </div>
        <p class="cockpit-summary">${escapeHtml(top.signal_summary || top.primary_headline || "The cockpit summarizes the latest direct-target rumor, data freshness, and audit warnings from local payload files.")}</p>
        <div class="cockpit-actions">
          ${topGroupKey ? `<button type="button" data-select-signal="${escapeHtml(topGroupKey)}">Inspect signal</button>` : ""}
          <button type="button" class="operator-run-button" data-run-research-cycle ${operatorRunning ? "disabled" : ""}>${operatorRunning ? "Research cycle running" : "Run today's cycle"}</button>
          <button type="button" data-jump="runbookSection">Choose runbook</button>
          <button type="button" data-jump="askAnalystSection">Ask analyst</button>
          <button type="button" data-jump="dataQualitySection">Audit details</button>
        </div>
        <div class="operator-status-line ${operatorRunning ? "is-running" : ""}">
          <span class="status-dot ${operatorStatus === "failed" ? "status-warn" : "status-good"}"></span>
          <strong>${escapeHtml(String(operatorStatus).replaceAll("_", " "))}</strong>
          <span>${escapeHtml(operatorSummary)}</span>
        </div>
      </div>
      <div class="cockpit-side">
        <div class="cockpit-metric">
          <span class="metric-label">Freshness</span>
          <strong>${escapeHtml(freshnessLabel)}</strong>
          <span class="detail-meta">${escapeHtml(freshnessDetail)}</span>
        </div>
        <div class="cockpit-metric">
          <span class="metric-label">Quality</span>
          <strong>${qualityScore}</strong>
          <span class="detail-meta">${escapeHtml(qualityStatus)}</span>
        </div>
        <div class="cockpit-metric">
          <span class="metric-label">Public Clubs</span>
          <strong>${publicClubs.length}</strong>
          <span class="detail-meta">${escapeHtml(publicClubs.slice(0, 4).join(", ") || "No current public targets")}</span>
        </div>
        <div class="cockpit-metric">
          <span class="metric-label">Warnings</span>
          <strong>${warnings.length}</strong>
          <span class="detail-meta">${escapeHtml(warnings[0] || "No audit warning loaded")}</span>
        </div>
      </div>
      <div class="cockpit-triage">
        <div class="cockpit-triage-head">
          <div>
            <span class="metric-label">Signal Triage Deck</span>
            <strong>What deserves attention first</strong>
          </div>
          <span class="detail-meta">Ranked by evidence, recency, direct public-club mapping, and model confidence.</span>
        </div>
        <div class="triage-card-grid">
          ${triage.length ? triage.map(({ row, triage: read }) => `
            <button type="button" class="triage-card ${escapeHtml(read.className)}" data-select-signal="${escapeHtml(row.group_key || "")}">
              <span class="triage-card-top">
                <span class="pill">${escapeHtml(read.label)}</span>
                <span class="triage-score">${fmtPct(read.score, 0)}</span>
              </span>
              <strong>${escapeHtml(row.player || "-")}</strong>
              <span class="detail-meta">${escapeHtml(row.target_club || row.club || "-")} · ${escapeHtml(row.target_role || row.deal_path || "rumor")} · ${fmtDate(row.latest_published_at)}</span>
              <span class="triage-meter"><i style="width:${clampNumber(read.score, 0, 1) * 100}%"></i></span>
              <span class="detail-note">${escapeHtml(read.reason)}</span>
              <span class="triage-action">${escapeHtml(read.action)}</span>
            </button>
          `).join("") : `
            <div class="triage-empty">
              <strong>No triage rows yet</strong>
              <span class="detail-meta">Run a live refresh and rebuild the dashboard to populate this queue.</span>
            </div>
          `}
        </div>
      </div>
    </div>
  `;
}

function renderRunbooks() {
  const container = document.getElementById("researchRunbooks");
  if (!container) return;
  const payload = state.runbooks || {};
  const runbooks = payload.runbooks || [];
  const runtime = state.operatorRuntime || {};
  const running = runtime.status === "running";
  if (!runbooks.length) {
    container.innerHTML = `
      <div class="runbook-empty">
        <div>
          <strong>No runbooks snapshot loaded</strong>
          <span class="detail-meta">Publish the static runbook contract, then refresh the dashboard.</span>
        </div>
        <code>PYTHONPATH=src python3 -m transfer_stock.cli list-runbooks --publish</code>
      </div>
    `;
    return;
  }
  container.innerHTML = `
    <div class="runbook-shell">
      <div class="runbook-intro">
        <div>
          <span class="metric-label">Workflow Gallery</span>
          <strong>${runbooks.length} research runbooks</strong>
          <p>${escapeHtml(payload.purpose || "Choose a workflow instead of memorizing CLI commands.")}</p>
        </div>
        <div class="operator-status-line ${running ? "is-running" : ""}">
          <span class="status-dot ${runtime.status === "failed" ? "status-warn" : "status-good"}"></span>
          <strong>${escapeHtml(String(runtime.status || "ready").replaceAll("_", " "))}</strong>
          <span>${escapeHtml(runtime.runbook_id ? `Running ${runtime.runbook_id}` : "Local API can execute supported runbooks.")}</span>
        </div>
      </div>
      <div class="runbook-grid">
        ${runbooks.map((runbook) => {
          const command = runbook.command || "";
          const canRun = runbook.api_supported && !running;
          return `
            <article class="runbook-card">
              <div class="runbook-card-top">
                <span class="pill pill-info">${escapeHtml(runbook.automation === "operator" ? "Runnable" : "CLI")}</span>
                <span class="detail-meta">${escapeHtml(runbook.estimated_time || "-")}</span>
              </div>
              <h3>${escapeHtml(runbook.title || runbook.id || "Runbook")}</h3>
              <p>${escapeHtml(runbook.tagline || "")}</p>
              <div class="runbook-meta-list">
                <span><strong>Best for</strong>${escapeHtml(runbook.best_for || "-")}</span>
                <span><strong>Pattern</strong>${escapeHtml(runbook.github_pattern || "-")}</span>
                <span><strong>Guardrail</strong>${escapeHtml(runbook.guardrail || "-")}</span>
              </div>
              <div class="runbook-output-list">
                ${(runbook.outputs || []).slice(0, 3).map((item) => `<code>${escapeHtml(item)}</code>`).join("")}
              </div>
              <div class="runbook-actions">
                ${runbook.api_supported ? `<button type="button" class="operator-run-button" data-run-runbook="${escapeHtml(runbook.id)}" ${canRun ? "" : "disabled"}>${running ? "Running" : "Run"}</button>` : ""}
                <button type="button" data-copy-memo="${encodeURIComponent(command)}">Copy command</button>
              </div>
            </article>
          `;
        }).join("")}
      </div>
      <p class="detail-note">${escapeHtml((payload.notes || [])[1] || "Static pages show commands; local FastAPI can run supported workflows.")}</p>
    </div>
  `;
}

function renderAgentAccess() {
  const panel = document.getElementById("agentAccessPanel");
  if (!panel) return;
  const manifest = state.agentManifest || {};
  const endpoint = manifest.endpoints?.ask || "/nlweb/ask";
  const staticManifest = manifest.endpoints?.static_manifest || "/.well-known/transfer-stock-agent.json";
  const example = (manifest.example_questions || [])[0] || "What changed today?";
  const curl = `curl -X POST http://127.0.0.1:8011${endpoint} -H "Content-Type: application/json" -d '{"question":"${example.replaceAll("'", "\\'")}"}'`;
  if (!manifest.name) {
    panel.innerHTML = `
      <div class="agent-access-empty">
        <div>
          <strong>Agent manifest not published</strong>
          <span class="detail-meta">Generate the NLWeb-style contract, then refresh the dashboard.</span>
        </div>
        <code>PYTHONPATH=src python3 -m transfer_stock.cli publish-agent-manifest</code>
      </div>
    `;
    return;
  }
  panel.innerHTML = `
    <div class="agent-access-shell">
      <div class="agent-access-hero">
        <div>
          <span class="metric-label">AI-Readable Website</span>
          <h3>${escapeHtml(manifest.name)}</h3>
          <p>${escapeHtml(manifest.description || "")}</p>
        </div>
        <span class="pill pill-info">NLWeb-style</span>
      </div>
      <div class="agent-access-grid">
        <div class="agent-access-card">
          <span class="metric-label">Ask Endpoint</span>
          <code>${escapeHtml(endpoint)}</code>
          <p>External agents can POST a natural-language question and receive grounded JSON.</p>
        </div>
        <div class="agent-access-card">
          <span class="metric-label">Static Manifest</span>
          <code>${escapeHtml(staticManifest)}</code>
          <p>GitHub Pages can advertise the contract even without running the backend.</p>
        </div>
        <div class="agent-access-card">
          <span class="metric-label">Safety</span>
          <strong>${manifest.safety?.trading_advice === false ? "Research only" : "Check manifest"}</strong>
          <p>${escapeHtml((manifest.safety?.notes || [])[0] || "Outputs should show uncertainty and source paths.")}</p>
        </div>
      </div>
      <div class="agent-access-examples">
        ${(manifest.example_questions || []).slice(0, 5).map((question) => `
          <button type="button" data-agent-question="${escapeHtml(question)}">${escapeHtml(question)}</button>
        `).join("")}
      </div>
      <div class="agent-access-command">
        <code>${escapeHtml(curl)}</code>
        <button type="button" data-copy-memo="${encodeURIComponent(curl)}">Copy curl</button>
      </div>
    </div>
  `;
}

function graphNodeColumns(nodes) {
  const columns = {
    reporter: [],
    source: [],
    player: [],
    club: [],
    stage: [],
    market: [],
  };
  (nodes || []).forEach((node) => {
    if (!columns[node.type]) return;
    columns[node.type].push(node);
  });
  Object.keys(columns).forEach((key) => {
    columns[key] = columns[key]
      .sort((a, b) => Number(b.weight || 0) - Number(a.weight || 0) || Number(b.score || 0) - Number(a.score || 0))
      .slice(0, key === "player" || key === "club" ? 5 : 4);
  });
  return columns;
}

function rumorGraphPositions(columns, width, height) {
  const order = ["reporter", "source", "player", "club", "stage", "market"];
  const positions = new Map();
  order.forEach((type, colIndex) => {
    const nodes = columns[type] || [];
    const x = 74 + colIndex * ((width - 148) / Math.max(order.length - 1, 1));
    const gap = height / Math.max(nodes.length + 1, 2);
    nodes.forEach((node, index) => {
      positions.set(node.id, {
        ...node,
        x: Math.round(x),
        y: Math.round(gap * (index + 1)),
      });
    });
  });
  return positions;
}

function rumorGraphNodeMarkup(node) {
  const isClub = node.type === "club";
  const width = node.type === "source" ? 135 : 128;
  const height = 38;
  const x = node.x - width / 2;
  const y = node.y - height / 2;
  const action = isClub ? `data-club-route="${escapeHtml(node.label)}"` : "";
  return `
    <g class="rumor-graph-node rumor-graph-node-${escapeHtml(node.type)}" ${action} tabindex="${isClub ? "0" : "-1"}" role="${isClub ? "button" : "img"}">
      <rect x="${x}" y="${y}" width="${width}" height="${height}" rx="8"></rect>
      <text x="${node.x}" y="${node.y - 3}" text-anchor="middle">${escapeHtml(node.label || "-").slice(0, 18)}</text>
      <text class="rumor-graph-node-sub" x="${node.x}" y="${node.y + 11}" text-anchor="middle">${node.weight || 0} · ${fmtNumber(node.score, 2)}</text>
    </g>
  `;
}

function rumorGraphEdgeMarkup(edge, positions) {
  const from = positions.get(edge.source);
  const to = positions.get(edge.target);
  if (!from || !to) return "";
  const strokeWidth = Math.max(1.1, Math.min(6, 1 + Number(edge.weight || 1) * 0.45));
  const opacity = Math.max(0.18, Math.min(0.76, Number(edge.score || 0.4)));
  const controlA = from.x + (to.x - from.x) * 0.45;
  const controlB = from.x + (to.x - from.x) * 0.55;
  return `
    <path class="rumor-graph-edge" d="M ${from.x} ${from.y} C ${controlA} ${from.y}, ${controlB} ${to.y}, ${to.x} ${to.y}" stroke-width="${strokeWidth}" opacity="${opacity}">
      <title>${escapeHtml(edge.type || "edge")} · ${escapeHtml(edge.first_seen || "")} to ${escapeHtml(edge.last_seen || "")}</title>
    </path>
  `;
}

function renderRumorGraph() {
  const panel = document.getElementById("rumorGraphPanel");
  if (!panel) return;
  const graph = state.rumorGraph || {};
  if (!graph.nodes?.length) {
    panel.innerHTML = `
      <div class="rumor-graph-empty">
        <div>
          <strong>No rumor graph built yet</strong>
          <span class="detail-meta">Build the temporal evidence graph, then refresh the dashboard.</span>
        </div>
        <code>PYTHONPATH=src python3 -m transfer_stock.cli build-rumor-graph</code>
      </div>
    `;
    return;
  }
  const columns = graphNodeColumns(graph.nodes);
  const width = 980;
  const height = 390;
  const positions = rumorGraphPositions(columns, width, height);
  const visibleIds = new Set(Array.from(positions.keys()));
  const visibleEdges = (graph.edges || [])
    .filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target))
    .slice(0, 80);
  const columnLabels = [
    ["Reporters", 74],
    ["Sources", 74 + ((width - 148) / 5)],
    ["Players", 74 + ((width - 148) / 5) * 2],
    ["Clubs", 74 + ((width - 148) / 5) * 3],
    ["Stages", 74 + ((width - 148) / 5) * 4],
    ["Market", width - 74],
  ];
  const timelines = graph.timelines || [];
  const summary = graph.summary || {};
  panel.innerHTML = `
    <div class="rumor-graph-shell">
      <div class="rumor-graph-hero">
        <div>
          <span class="metric-label">Temporal Knowledge Graph</span>
          <h3>${summary.timeline_count || 0} evolving rumor path${Number(summary.timeline_count || 0) === 1 ? "" : "s"}</h3>
          <p>${escapeHtml(graph.inspired_by?.idea || "Track changing relationships across transfer evidence.")}</p>
        </div>
        <div class="headline-row">
          <span class="pill pill-info">${summary.node_count || 0} nodes</span>
          <span class="pill pill-neutral">${summary.edge_count || 0} edges</span>
        </div>
      </div>
      <div class="rumor-graph-metrics">
        <div class="cockpit-metric"><span class="metric-label">Top Club</span><strong>${escapeHtml(summary.top_clubs?.[0]?.club || "-")}</strong><span class="detail-meta">${summary.top_clubs?.[0]?.count || 0} links</span></div>
        <div class="cockpit-metric"><span class="metric-label">Top Source</span><strong>${escapeHtml(summary.top_sources?.[0]?.source || "-")}</strong><span class="detail-meta">${summary.top_sources?.[0]?.count || 0} links</span></div>
        <div class="cockpit-metric"><span class="metric-label">Main Stage</span><strong>${escapeHtml(summary.stage_mix?.[0]?.stage || "-")}</strong><span class="detail-meta">${summary.stage_mix?.[0]?.count || 0} rows</span></div>
      </div>
      <div class="rumor-graph-wrap">
        <svg class="rumor-graph-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Temporal rumor graph">
          ${columnLabels.map(([label, x]) => `<text class="trust-column-label" x="${x}" y="20" text-anchor="middle">${label}</text>`).join("")}
          ${visibleEdges.map((edge) => rumorGraphEdgeMarkup(edge, positions)).join("")}
          ${Array.from(positions.values()).map(rumorGraphNodeMarkup).join("")}
        </svg>
      </div>
      <div class="rumor-timeline-grid">
        ${timelines.slice(0, 4).map((item) => `
          <article class="rumor-timeline-card">
            <div class="headline-row">
              <strong>${escapeHtml(item.player || "-")}</strong>
              <span class="pill pill-neutral">${escapeHtml(item.latest_stage || "-")}</span>
            </div>
            <span class="detail-meta">${clubChip(item.club || "")} · ${escapeHtml(item.first_seen || "-")} → ${escapeHtml(item.last_seen || "-")} · ${item.event_count || 0} events</span>
            <div class="rumor-timeline-events">
              ${(item.events || []).slice(-4).map((event) => `
                <span><b>${escapeHtml(event.date || "-")}</b>${escapeHtml(event.stage || "-")} · ${escapeHtml(event.source || "-")}</span>
              `).join("")}
            </div>
          </article>
        `).join("")}
      </div>
      <p class="detail-note">${escapeHtml((graph.warnings || [])[0] || "This graph shows evidence relationships, not causal proof.")}</p>
    </div>
  `;
}

async function reloadResearchSnapshots() {
  const response = await fetch("./data/dashboard_data.json", { cache: "no-store" });
  if (response.ok) state.payload = await response.json();
  state.agent = await loadAgentSnapshot();
  state.ragAudit = await loadRagAuditSnapshot();
  state.autopilot = await loadAutopilotSnapshot();
  state.operator = await loadOperatorSnapshot();
  state.runbooks = await loadRunbookSnapshot();
  state.agentManifest = await loadAgentManifest();
  state.rumorGraph = await loadRumorGraph();
  state.dataQuality = await loadDataQualitySnapshot();
  renderAll();
}

async function pollResearchCycle() {
  try {
    const response = await fetch("/operator/status", { cache: "no-store" });
    if (!response.ok) throw new Error("Operator API unavailable");
    state.operatorRuntime = await response.json();
    if (state.operatorRuntime.latest?.available) state.operator = state.operatorRuntime.latest;
    renderMarketCockpit();
    renderRunbooks();
    if (state.operatorRuntime.status === "running") {
      window.setTimeout(pollResearchCycle, 1800);
      return;
    }
    await reloadResearchSnapshots();
  } catch (error) {
    state.operatorRuntime = {
      status: "static_mode",
      error: "On-demand cycle is available from the FastAPI workbench; this static view uses the latest scheduled package.",
    };
    renderMarketCockpit();
    renderRunbooks();
  }
}

async function requestResearchCycle() {
  state.operatorRuntime = { status: "running", mode: "smart", error: "" };
  renderMarketCockpit();
  renderRunbooks();
  try {
    const response = await fetch("/operator/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "smart", allow_network: true }),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Research cycle request failed");
    }
    state.operatorRuntime = await response.json();
    window.setTimeout(pollResearchCycle, 900);
  } catch (error) {
    state.operatorRuntime = {
      status: "static_mode",
      error: "On-demand cycle is available from the FastAPI workbench; this static view uses the latest scheduled package.",
    };
    renderMarketCockpit();
  }
}

async function requestRunbook(runbookId) {
  state.operatorRuntime = { status: "running", mode: "runbook", runbook_id: runbookId, error: "" };
  renderMarketCockpit();
  renderRunbooks();
  try {
    const response = await fetch(`/runbooks/${encodeURIComponent(runbookId)}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Runbook request failed");
    }
    state.operatorRuntime = await response.json();
    window.setTimeout(pollResearchCycle, 900);
  } catch (error) {
    state.operatorRuntime = {
      status: "static_mode",
      runbook_id: runbookId,
      error: "Runbooks execute from the FastAPI workbench. On GitHub Pages, copy the command instead.",
    };
    renderMarketCockpit();
    renderRunbooks();
  }
}

function qualityStatusClass(status) {
  if (status === "strong") return "pill pill-positive";
  if (status === "usable") return "pill pill-info";
  if (status === "watch") return "pill pill-warning";
  return "pill pill-negative";
}

function renderDataQuality() {
  const panel = document.getElementById("dataQualityPanel");
  const meta = document.getElementById("dataQualityMeta");
  const audit = state.dataQuality;
  if (!panel) return;
  if (!audit || !audit.available) {
    meta.textContent = "No data-quality audit snapshot is published yet.";
    panel.innerHTML = `
      <div class="quality-empty">
        <div>
          <strong>No audit snapshot yet</strong>
          <span class="detail-meta">Run the local audit command, then refresh this page.</span>
        </div>
        <pre><code>PYTHONPATH=src python3 -m transfer_stock.cli audit-data-quality</code></pre>
      </div>
    `;
    return;
  }
  meta.textContent = `${fmtDate(audit.audit_generated_at)} · ${escapeHtml(audit.overall_status || "unknown").replaceAll("_", " ")} · ${(audit.warnings || []).length} warnings`;
  const dimensions = audit.dimensions || [];
  const warnings = audit.warnings || [];
  panel.innerHTML = `
    <div class="quality-shell">
      <div class="quality-summary">
        <div>
          <span class="metric-label">Overall Readiness</span>
          <strong>${fmtPct(audit.overall_score, 0)}</strong>
          <span class="detail-meta">${escapeHtml(audit.summary || "")}</span>
        </div>
        <span class="${qualityStatusClass(audit.overall_status)}">${escapeHtml((audit.overall_status || "unknown").replaceAll("_", " "))}</span>
      </div>
      <div class="quality-grid">
        ${dimensions.map((item) => `
          <div class="quality-card">
            <div class="headline-row">
              <strong>${escapeHtml(item.name || "-")}</strong>
              <span class="${qualityStatusClass(item.status)}">${escapeHtml((item.status || "").replaceAll("_", " "))}</span>
            </div>
            <div class="quality-meter" aria-label="${escapeHtml(item.name || "Quality")} score">
              <span style="width:${Math.max(0, Math.min(100, Number(item.score || 0) * 100))}%"></span>
            </div>
            <span class="detail-meta">${fmtPct(item.score, 0)} · ${escapeHtml(item.summary || "")}</span>
          </div>
        `).join("")}
      </div>
      <details class="quality-detail">
        <summary>
          <span>Warnings + next refresh commands</span>
          <strong>${warnings.length}</strong>
        </summary>
        <div class="quality-detail-grid">
          <div>
            <span class="metric-label">Warnings</span>
            ${warnings.length ? `
              <ul class="scenario-risk-list">
                ${warnings.slice(0, 10).map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}
              </ul>
            ` : `<p class="detail-note">No major warnings found in the latest audit.</p>`}
          </div>
          <div>
            <span class="metric-label">Commands</span>
            ${(audit.recommended_commands || []).length ? `
              <div class="quality-command-list">
                ${(audit.recommended_commands || []).slice(0, 5).map((command) => `<code>${escapeHtml(command)}</code>`).join("")}
              </div>
            ` : `<p class="detail-note">No commands suggested.</p>`}
          </div>
        </div>
      </details>
    </div>
  `;
}

function renderAskTable(table) {
  const columns = table.columns || [];
  const rows = table.rows || [];
  if (!columns.length) return "";
  return `
    <div class="ask-table">
      <div class="section-head"><h3>${escapeHtml(table.title || "Evidence")}</h3></div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>
          </thead>
          <tbody>
            ${rows.length ? rows.map((row) => `
              <tr ${row._groupKey ? `data-ask-group-key="${escapeHtml(row._groupKey)}"` : ""}>
                ${columns.map((column) => {
                  const value = row[column] ?? row[String(column).toLowerCase()] ?? "";
                  return `<td>${escapeHtml(value)}</td>`;
                }).join("")}
              </tr>
            `).join("") : `<tr><td colspan="${columns.length}">No rows available.</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderAskAnalyst() {
  const answer = document.getElementById("askAnalystAnswer");
  const input = document.getElementById("askAnalystInput");
  if (input && input.value !== state.askQuestion) {
    input.value = state.askQuestion;
  }
  if (!state.askResult) {
    answer.innerHTML = `
      <div class="ask-empty">
        <strong>Try a grounded question about clubs, reporters, players, match results, or confirmed transfers.</strong>
        <span class="detail-meta">Answers come from <code>app/static/data/dashboard_data.json</code>.</span>
      </div>
    `;
    return;
  }
  const result = state.askResult;
  answer.innerHTML = `
    <div class="ask-result">
      <div class="ask-result-head">
        <div>
          <span class="metric-label">${escapeHtml(result.intent.replaceAll("_", " "))}</span>
          <strong>${escapeHtml(result.shortAnswer)}</strong>
        </div>
        <span class="pill pill-info">Confidence ${fmtPct(result.confidence, 0)}</span>
      </div>
      ${(result.evidenceCards || []).length ? `
        <div class="ask-card-grid">
          ${(result.evidenceCards || []).map((card) => `
            <div class="metric-card ask-card">
              <span class="metric-label">${escapeHtml(card.title || "")}</span>
              <strong>${escapeHtml(card.value ?? "-")}</strong>
              <span class="metric-sub">${escapeHtml(card.detail || "")}</span>
            </div>
          `).join("")}
        </div>
      ` : ""}
      ${(result.tables || []).map(renderAskTable).join("")}
      ${(result.warnings || []).length ? `
        <div class="ask-warning-row">
          ${(result.warnings || []).map((warning) => `<span>${escapeHtml(warning)}</span>`).join("")}
        </div>
      ` : ""}
      <div class="detail-meta">Source: ${(result.sourcePaths || []).map((item) => `<code>${escapeHtml(item)}</code>`).join(" · ")}</div>
    </div>
  `;
  answer.querySelectorAll("[data-ask-group-key]").forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedView = "rumors";
      state.selectedSeason = state.payload.latest_season;
      state.clubFilter = "All";
      state.selectedKey = row.dataset.askGroupKey;
      renderAll();
    });
  });
}

function ragMethodLabel(method) {
  const labels = {
    lexical: "Lexical",
    semantic_chargram: "Fuzzy semantic",
    structured_entity: "Entity match",
    recency: "Recency",
  };
  return labels[method] || String(method || "Method").replaceAll("_", " ");
}

function ragCitationMarkup(hit, maxScore) {
  const score = Number(hit.score || 0);
  const scorePct = clampNumber(maxScore ? score / maxScore : Number(hit.normalized_score || 0), 0, 1) * 100;
  const breakdown = hit.score_breakdown || {};
  const components = ["lexical", "semantic_chargram", "structured_entity", "recency"]
    .map((key) => ({ key, value: Number(breakdown[key] || 0) }))
    .filter((item) => item.value > 0);
  const maxComponent = Math.max(...components.map((item) => item.value), 1);
  return `
    <a class="rag-citation-card" href="${escapeHtml(hit.url || "#")}" ${hit.url ? 'target="_blank" rel="noreferrer"' : ""}>
      <div class="rag-citation-head">
        <span class="pill pill-neutral">${escapeHtml(hit.doc_type || "evidence")}</span>
        <span class="rag-score">${fmtNumber(hit.normalized_score ?? scorePct / 100, 2)}</span>
      </div>
      <strong>${escapeHtml(hit.title || "-")}</strong>
      <span class="detail-meta">${fmtDate(hit.date)} · ${escapeHtml(hit.source || hit.source_path || "-")}</span>
      <span class="rag-scorebar"><i style="width:${scorePct.toFixed(0)}%"></i></span>
      ${components.length ? `
        <div class="rag-component-grid">
          ${components.map((item) => `
            <span class="rag-component">
              <span>${escapeHtml(ragMethodLabel(item.key))}</span>
              <i style="width:${clampNumber(item.value / maxComponent, 0, 1) * 100}%"></i>
            </span>
          `).join("")}
        </div>
      ` : ""}
    </a>
  `;
}

function ragEvidenceLensMarkup(agent) {
  const lens = agent.rag_lens || {};
  const citations = agent.evidence_citations || [];
  if (!lens.mode && !citations.length) return "";
  const maxScore = Math.max(...citations.map((hit) => Number(hit.score || 0)), 1);
  const methods = lens.retrieval_methods || [];
  const docMix = lens.doc_type_mix || [];
  const sourceMix = lens.source_mix || [];
  const queryPlan = lens.query_plan || [];
  const perQuery = lens.per_query || [];
  return `
    <details class="detail-card rag-lens-panel collapsible-panel" open>
      <summary class="section-head">
        <div>
          <h3>RAG Evidence Lens</h3>
          <span class="section-meta">${escapeHtml(lens.retriever || "local_hybrid")} · ${escapeHtml(lens.mode || "agentic retrieval")} · ${lens.total_candidates || citations.length} candidates</span>
        </div>
        <span class="pill pill-info">${methods.length || 0} retrieval signals</span>
      </summary>
      <div class="rag-lens-grid">
        <div class="rag-lens-main">
          <div class="rag-query-strip">
            ${queryPlan.slice(0, 6).map((item, index) => `
              <div class="rag-query-chip">
                <span>${index + 1}</span>
                <strong>${escapeHtml((item.purpose || "query").replaceAll("_", " "))}</strong>
                <em>${escapeHtml(item.query || "")}</em>
              </div>
            `).join("") || `<p class="detail-note">No query plan was published for this run.</p>`}
          </div>
          <div class="rag-citation-grid">
            ${citations.slice(0, 6).map((hit) => ragCitationMarkup(hit, maxScore)).join("") || `<p class="detail-note">No citations were attached.</p>`}
          </div>
        </div>
        <aside class="rag-lens-side">
          <div class="rag-mini-card">
            <span class="metric-label">Retrieval Methods</span>
            <div class="rag-pill-row">
              ${methods.map((item) => `<span>${escapeHtml(ragMethodLabel(item.method))} <strong>${item.count}</strong></span>`).join("") || "<span>Not published</span>"}
            </div>
          </div>
          <div class="rag-mini-card">
            <span class="metric-label">Evidence Mix</span>
            <div class="rag-mix-list">
              ${docMix.slice(0, 5).map((item) => `<span><b>${escapeHtml(item.doc_type)}</b><i>${item.count}</i></span>`).join("") || "<span><b>-</b><i>0</i></span>"}
            </div>
          </div>
          <div class="rag-mini-card">
            <span class="metric-label">Top Sources</span>
            <div class="rag-mix-list">
              ${sourceMix.slice(0, 4).map((item) => `<span><b>${escapeHtml(item.source)}</b><i>${item.count}</i></span>`).join("") || "<span><b>-</b><i>0</i></span>"}
            </div>
          </div>
          <div class="rag-mini-card">
            <span class="metric-label">Subquery Hit Counts</span>
            <div class="rag-mix-list">
              ${perQuery.slice(0, 5).map((item) => `<span><b>${escapeHtml((item.purpose || "query").replaceAll("_", " "))}</b><i>${item.count || 0}</i></span>`).join("") || "<span><b>-</b><i>0</i></span>"}
            </div>
          </div>
        </aside>
      </div>
      ${(lens.what_would_change_mind || []).length ? `
        <div class="rag-uncertainty">
          <span class="metric-label">What Would Change The Read</span>
          ${(lens.what_would_change_mind || []).slice(0, 4).map((item) => `<p>${escapeHtml(item)}</p>`).join("")}
        </div>
      ` : ""}
    </details>
  `;
}

function renderAgentRun() {
  const container = document.getElementById("agentRun");
  const meta = document.getElementById("agentRunMeta");
  const agent = state.agent;
  if (!agent || !agent.available) {
    meta.textContent = "No static agent snapshot is published yet.";
    container.innerHTML = `
      <div class="scenario-empty">
        <div>
          <strong>No Agent Run report yet</strong>
          <p class="detail-note">Run the local agent loop, then refresh this page.</p>
        </div>
        <pre><code>PYTHONPATH=src python3 -m transfer_stock.cli agent-run \\
  --goal "Find today's strongest Manchester United transfer-stock watch item"</code></pre>
      </div>
    `;
    return;
  }
  const answer = agent.answer || {};
  const freshness = agent.freshness || {};
  const memory = agent.memory || {};
  const citations = agent.evidence_citations || [];
  const scenario = agent.scenario || {};
  meta.textContent = `${fmtDate(agent.generated_at)} · ${agent.run_id || "latest"} · ${answer.citation_count || citations.length || 0} citations`;
  container.innerHTML = `
    <div class="agent-shell">
      <div class="scenario-hero agent-hero">
        <div>
          <span class="metric-label">Agent Goal</span>
          <h3>${escapeHtml(agent.goal || "-")}</h3>
          <p class="detail-note">${escapeHtml(agent.primary_question || "-")}</p>
        </div>
        <div class="scenario-verdict">
          <span class="pill pill-info">${escapeHtml((answer.intent || "answer").replaceAll("_", " "))}</span>
          <strong>${fmtPct(answer.confidence, 0)}</strong>
          <span class="detail-meta">Answer confidence</span>
        </div>
      </div>

      <div class="scenario-metrics">
        <div class="metric-card"><span class="metric-label">Live Status</span><strong>${escapeHtml(freshness.live_status || "unknown")}</strong><span class="metric-sub">${escapeHtml(freshness.latest_live_date || "-")}</span></div>
        <div class="metric-card"><span class="metric-label">Watchlist Rows</span><strong>${escapeHtml(freshness.live_watchlist_count ?? "-")}</strong></div>
        <div class="metric-card"><span class="metric-label">Evidence Citations</span><strong>${escapeHtml(answer.citation_count ?? citations.length)}</strong></div>
        <div class="metric-card"><span class="metric-label">Scenario</span><strong>${scenario.available ? escapeHtml((scenario.summary || {}).consensus_stance || "watch") : "Not run"}</strong><span class="metric-sub">${scenario.available ? fmtPct((scenario.summary || {}).consensus_confidence, 0) : "No player seed"}</span></div>
      </div>

      <div class="detail-card agent-answer-card">
        <div class="section-head"><h3>Answer</h3></div>
        <p>${escapeHtml(answer.short_answer || "-")}</p>
      </div>

      ${ragEvidenceLensMarkup(agent)}

      <div class="agent-grid">
        <div class="detail-card">
          <div class="section-head"><h3>What Changed</h3></div>
          ${(memory.changes || []).length ? `
            <ul class="scenario-risk-list">
              ${(memory.changes || []).slice(0, 6).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
            </ul>
          ` : `<p class="detail-note">No previous run comparison is available yet.</p>`}
          ${memory.previous_run_id ? `<p class="detail-meta">Previous run: <code>${escapeHtml(memory.previous_run_id)}</code></p>` : ""}
        </div>
        <div class="detail-card">
          <div class="section-head"><h3>Evidence Citations</h3></div>
          <div class="agent-citation-list">
            ${citations.slice(0, 6).map((hit) => `
              <a class="agent-citation" href="${escapeHtml(hit.url || "#")}" ${hit.url ? 'target="_blank" rel="noreferrer"' : ""}>
                <span class="pill pill-neutral">${escapeHtml(hit.doc_type || "evidence")}</span>
                <strong>${escapeHtml(hit.title || "-")}</strong>
                <span class="detail-meta">${fmtDate(hit.date)} · ${escapeHtml(hit.source || hit.source_path || "-")}</span>
              </a>
            `).join("") || `<p class="detail-note">No citations were attached.</p>`}
          </div>
        </div>
      </div>

      <details class="detail-card collapsible-panel">
        <summary class="section-head">
          <h3>Agent Trace Files</h3>
          <span class="section-meta">Machine-readable artifacts from this run.</span>
        </summary>
        <div class="flow-grid">
          ${Object.entries(agent.outputs || {}).map(([key, value]) => `
            <div class="flow-card">
              <span class="flow-path">${escapeHtml(key)}</span>
              <code>${escapeHtml(value)}</code>
            </div>
          `).join("")}
        </div>
        ${agent.report_href ? `<a class="route-back scenario-report-link" href="${escapeHtml(agent.report_href)}" target="_blank" rel="noreferrer">Open agent_report.md</a>` : ""}
      </details>
    </div>
  `;
}

function renderAutopilot() {
  const container = document.getElementById("autopilotPanel");
  const meta = document.getElementById("autopilotMeta");
  if (!container || !meta) return;
  const autopilot = state.autopilot;
  if (!autopilot || !autopilot.available) {
    meta.textContent = "No autopilot snapshot is published yet.";
    container.innerHTML = `
      <div class="scenario-empty">
        <div>
          <strong>No autopilot run yet</strong>
          <p class="detail-note">Run the bounded local operator, then refresh this page.</p>
        </div>
        <pre><code>PYTHONPATH=src python3 -m transfer_stock.cli agent-autopilot</code></pre>
      </div>
    `;
    return;
  }
  const selected = autopilot.selected_goal || {};
  const audit = autopilot.audit_summary || {};
  const agent = autopilot.agent_summary || {};
  const answer = agent.answer || {};
  const steps = autopilot.steps || [];
  const completed = steps.filter((step) => step.status === "completed").length;
  meta.textContent = `${fmtDate(autopilot.generated_at)} · ${completed}/${steps.length || 0} completed · ${escapeHtml(audit.overall_status || "unknown")}`;
  container.innerHTML = `
    <div class="agent-shell autopilot-shell">
      <div class="scenario-hero agent-hero">
        <div>
          <span class="metric-label">Autopilot Selected Goal</span>
          <h3>${escapeHtml(selected.goal || "-")}</h3>
          <p class="detail-note">${escapeHtml(selected.reason || "Local agent selected this goal from the latest payload.")}</p>
        </div>
        <div class="scenario-verdict">
          <span class="pill pill-info">${escapeHtml(audit.overall_status || "audit")}</span>
          <strong>${audit.overall_score !== "" && audit.overall_score !== undefined ? fmtPct(audit.overall_score, 0) : "-"}</strong>
          <span class="detail-meta">Data quality</span>
        </div>
      </div>
      <div class="scenario-metrics">
        <div class="metric-card"><span class="metric-label">Steps</span><strong>${completed}/${steps.length || 0}</strong><span class="metric-sub">bounded local run</span></div>
        <div class="metric-card"><span class="metric-label">Agent Run</span><strong>${escapeHtml(agent.run_id || "-")}</strong><span class="metric-sub">${escapeHtml((answer.intent || "").replaceAll("_", " ") || "not run")}</span></div>
        <div class="metric-card"><span class="metric-label">Confidence</span><strong>${answer.confidence !== undefined ? fmtPct(answer.confidence, 0) : "-"}</strong></div>
        <div class="metric-card"><span class="metric-label">Dry Run</span><strong>${autopilot.dry_run ? "Yes" : "No"}</strong></div>
      </div>
      ${answer.short_answer ? `
        <div class="detail-card agent-answer-card">
          <div class="section-head"><h3>Autopilot Read</h3></div>
          <p>${escapeHtml(answer.short_answer)}</p>
        </div>
      ` : ""}
      <div class="agent-grid">
        <div class="detail-card">
          <div class="section-head"><h3>Execution Trace</h3></div>
          <div class="autopilot-step-list">
            ${steps.map((step) => `
              <div class="autopilot-step ${step.status || "planned"}">
                <span class="pill ${step.status === "completed" ? "pill-positive" : "pill-neutral"}">${escapeHtml(step.status || "planned")}</span>
                <strong>${escapeHtml((step.id || "").replaceAll("_", " "))}</strong>
                <span class="detail-meta">${escapeHtml(step.output || step.time || "-")}</span>
              </div>
            `).join("")}
          </div>
        </div>
        <div class="detail-card">
          <div class="section-head"><h3>Recommended Commands</h3></div>
          <div class="quality-command-list">
            ${(autopilot.recommended_commands || []).slice(0, 5).map((command) => `<pre><code>${escapeHtml(command)}</code></pre>`).join("")}
          </div>
        </div>
      </div>
    </div>
  `;
}

function auditStatusClass(status) {
  if (status === "strong") return "pill pill-positive";
  if (status === "usable") return "pill pill-info";
  if (status === "watch") return "pill pill-warning";
  return "pill pill-negative";
}

function renderRagAudit() {
  const container = document.getElementById("ragAuditPanel");
  const meta = document.getElementById("ragAuditMeta");
  if (!container || !meta) return;
  const audit = state.ragAudit;
  if (!audit || !audit.available) {
    meta.textContent = "No RAG trust audit is published yet.";
    container.innerHTML = `
      <div class="scenario-empty">
        <div>
          <strong>No RAG audit yet</strong>
          <p class="detail-note">Run the local RAG evaluator after an agent run.</p>
        </div>
        <pre><code>PYTHONPATH=src python3 -m transfer_stock.cli audit-rag</code></pre>
      </div>
    `;
    return;
  }
  meta.textContent = `${fmtDate(audit.generated_at)} · ${audit.agent_run_id || "latest"} · ${escapeHtml((audit.overall_status || "unknown").replaceAll("_", " "))}`;
  container.innerHTML = `
    <div class="rag-audit-shell">
      <div class="rag-audit-hero">
        <div>
          <span class="metric-label">RAG Trust Score</span>
          <h3>${fmtPct(audit.overall_score, 0)}</h3>
          <p>${escapeHtml(audit.summary || "Audit summary unavailable.")}</p>
        </div>
        <span class="${auditStatusClass(audit.overall_status)}">${escapeHtml((audit.overall_status || "unknown").replaceAll("_", " "))}</span>
      </div>
      <div class="rag-audit-grid">
        ${(audit.dimensions || []).map((item) => `
          <div class="rag-audit-card">
            <div class="headline-row">
              <strong>${escapeHtml(item.name || "-")}</strong>
              <span class="${auditStatusClass(item.status)}">${escapeHtml((item.status || "").replaceAll("_", " "))}</span>
            </div>
            <div class="quality-meter" aria-label="${escapeHtml(item.name || "RAG dimension")} score">
              <span style="width:${clampNumber(Number(item.score || 0), 0, 1) * 100}%"></span>
            </div>
            <span class="detail-meta">${fmtPct(item.score, 0)}</span>
            ${(item.warnings || []).length ? `<p class="detail-note">${escapeHtml(item.warnings[0])}</p>` : ""}
          </div>
        `).join("")}
      </div>
      <div class="rag-audit-recommendations">
        <span class="metric-label">Recommended Fixes</span>
        ${(audit.recommendations || []).map((item) => `<p>${escapeHtml(item)}</p>`).join("")}
      </div>
    </div>
  `;
}

function renderScenarioSwarm() {
  const container = document.getElementById("scenarioSwarm");
  const meta = document.getElementById("scenarioSwarmMeta");
  const scenario = state.scenario;
  if (!scenario || !scenario.available) {
    meta.textContent = "No static scenario snapshot is published yet.";
    container.innerHTML = `
      <div class="scenario-empty">
        <div>
          <strong>No Scenario Swarm report yet</strong>
          <p class="detail-note">Run a bounded local simulation, then refresh this page.</p>
        </div>
        <pre><code>PYTHONPATH=src python3 -m transfer_stock.cli simulate-scenario \\
  --player Casemiro \\
  --club "Manchester United" \\
  --rounds 2</code></pre>
      </div>
    `;
    return;
  }
  const signal = scenario.signal || {};
  const summary = scenario.summary || {};
  const evidence = scenario.evidence || {};
  const stock = evidence.stock_path || {};
  const agents = scenario.agents || [];
  const risks = scenario.risk_notes || [];
  const confirmed = evidence.confirmed_transfer_links || [];
  const similar = evidence.similar_examples || [];
  const sourcePaths = scenario.source_paths || {};
  meta.textContent = `${fmtDate(scenario.generated_at)} · ${scenario.rounds || 0} rounds · ${scenario.simulation_id || "latest"}`;
  container.innerHTML = `
    <div class="scenario-shell">
      <div class="scenario-hero">
        <div>
          <span class="metric-label">Scenario Question</span>
          <h3>${escapeHtml(scenario.question || "-")}</h3>
          <p class="detail-note">${escapeHtml(signal.player || "-")} · ${clubChip(signal.target_club || signal.club || "")} · role ${escapeHtml(signal.target_role || "-")}</p>
        </div>
        <div class="scenario-verdict">
          <span class="${stancePillClass(summary.consensus_stance)}">${escapeHtml(summary.consensus_stance || "watch")}</span>
          <strong>${fmtPct(summary.consensus_confidence, 0)}</strong>
          <span class="detail-meta">Consensus confidence</span>
        </div>
      </div>

      <div class="scenario-metrics">
        <div class="metric-card"><span class="metric-label">Stage</span><strong>${escapeHtml(signal.rumor_stage || "-")}</strong></div>
        <div class="metric-card"><span class="metric-label">Credibility</span><strong>${fmtNumber(signal.credibility_score, 3)}</strong></div>
        <div class="metric-card"><span class="metric-label">Transfer Index</span><strong>${fmtNumber(signal.transfer_indicator, 3)}</strong></div>
        <div class="metric-card"><span class="metric-label">Model / Blend</span><strong>${escapeHtml(signal.predicted_label || "-")} / ${escapeHtml(signal.blended_label || "-")}</strong></div>
        <div class="metric-card"><span class="metric-label">Stock Path</span><strong>${escapeHtml(stock.ticker || "-")}</strong><span class="metric-sub">${fmtPct(stock.latest_change, 1)} latest change</span></div>
      </div>

      <div class="scenario-agent-grid">
        ${agents.map((agent) => `
          <div class="scenario-agent-card">
            <div class="headline-row">
              <strong>${escapeHtml(agent.name || agent.agent_id || "Agent")}</strong>
              <span class="${stancePillClass(agent.stance)}">${escapeHtml(agent.stance || "watch")}</span>
            </div>
            <span class="detail-meta">Confidence ${fmtPct(agent.confidence, 0)}</span>
            <ul>
              ${(agent.evidence_bullets || []).slice(0, 3).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
            </ul>
            ${(agent.risk_caveats || []).length ? `<p class="detail-note">${escapeHtml((agent.risk_caveats || [])[0])}</p>` : ""}
          </div>
        `).join("")}
      </div>

      <div class="scenario-evidence-grid">
        <div class="detail-card">
          <div class="section-head"><h3>Evidence Used</h3></div>
          <div class="detail-grid compact">
            <div class="kv"><span class="list-label">Confirmed links</span><strong>${confirmed.length}</strong></div>
            <div class="kv"><span class="list-label">Similar cases</span><strong>${similar.length}</strong></div>
            <div class="kv"><span class="list-label">Match markers</span><strong>${stock.match_marker_count || 0}</strong></div>
            <div class="kv"><span class="list-label">Latest source</span><strong>${escapeHtml(signal.latest_source || "-")}</strong></div>
          </div>
          ${confirmed.length ? `
            <div class="scenario-mini-list">
              ${confirmed.slice(0, 3).map((item) => `
                <span>${escapeHtml(item.player || signal.player || "-")} · ${fmtDate(item.date)} · ${escapeHtml(item.actual_label || "unlabeled")}</span>
              `).join("")}
            </div>
          ` : `<p class="detail-note">No confirmed-transfer link was attached to this scenario.</p>`}
        </div>

        <div class="detail-card">
          <div class="section-head"><h3>Disagreement + Risk</h3></div>
          ${risks.length ? `
            <ul class="scenario-risk-list">
              ${risks.slice(0, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
            </ul>
          ` : `<p class="detail-note">No extra risk notes were generated.</p>`}
        </div>
      </div>

      <details class="detail-card collapsible-panel">
        <summary class="section-head">
          <h3>Evidence Trace</h3>
          <span class="section-meta">Generated files and report link.</span>
        </summary>
        <div class="flow-grid">
          ${Object.entries(sourcePaths).map(([key, value]) => `
            <div class="flow-card">
              <span class="flow-path">${escapeHtml(key)}</span>
              <code>${escapeHtml(value)}</code>
            </div>
          `).join("")}
        </div>
        ${scenario.report_href ? `<a class="route-back scenario-report-link" href="${escapeHtml(scenario.report_href)}" target="_blank" rel="noreferrer">Open report.md</a>` : ""}
      </details>
    </div>
  `;
}

const SIM_STAGE_SCORES = {
  unclear: 0.40,
  linked: 0.44,
  talks: 0.52,
  bid: 0.62,
  advanced: 0.72,
  agreed: 0.84,
  medical: 0.90,
  official: 0.96,
};

function simulatorNumber(id, fallback = 0) {
  const value = Number(document.getElementById(id)?.value || "");
  return Number.isFinite(value) ? value : fallback;
}

function simulatorCredibility(source, journalist) {
  const sourceNorm = normalizeQuery(source);
  const journalistNorm = normalizeQuery(journalist);
  const sources = state.payload.leaderboards?.sources || [];
  const journalists = state.payload.leaderboards?.journalists || [];
  const sourceRow = sources.find((row) => normalizeQuery(row.source) === sourceNorm);
  const journalistRow = journalists.find((row) => normalizeQuery(row.journalist) === journalistNorm);
  const sourceScore = Number(sourceRow?.smoothed_rate || 0);
  const journalistScore = Number(journalistRow?.smoothed_rate || 0);
  const warnings = [];
  if (sourceScore && journalistScore) return { score: clampNumber(0.45 * sourceScore + 0.55 * journalistScore), warnings };
  if (journalistScore) return { score: clampNumber(journalistScore), warnings };
  if (sourceScore) return { score: clampNumber(sourceScore), warnings };
  warnings.push("No matching source or journalist history found; credibility defaults to neutral.");
  return { score: 0.5, warnings };
}

function simulatorDirection(role) {
  return role === "seller" ? "out" : "in";
}

function simulatorTransferQuality({ role, age, marketValue, fee, wage }) {
  const direction = simulatorDirection(role);
  let valueGap = 0;
  if (marketValue > 0) {
    valueGap = direction === "in" ? (marketValue - fee) / marketValue : (fee - marketValue) / marketValue;
  }
  const valueComponent = clampNumber(0.5 + valueGap / 2);
  const wageComponent = 1 - 0.35 * clampNumber(wage / 25000000);
  const ageComponent = direction === "in"
    ? clampNumber(1 - Math.abs(age - 24) / 12)
    : clampNumber(0.65 + Math.max(age - 27, 0) / 12);
  return clampNumber(0.45 * valueComponent + 0.30 * ageComponent + 0.25 * wageComponent);
}

function simulatorTransferIndicator(input) {
  const direction = simulatorDirection(input.role);
  const base = simulatorTransferQuality(input);
  const feeRatio = input.marketValue > 0 && input.fee > 0 ? input.fee / input.marketValue : 0;
  let feeComponent = 0.5;
  if (feeRatio > 0) {
    feeComponent = direction === "in" ? clampNumber(1.15 - feeRatio) : clampNumber(0.5 + (feeRatio - 1) / 2);
  }
  const ageComponent = direction === "in"
    ? clampNumber(1 - Math.abs(input.age - 24) / 12)
    : clampNumber(0.55 + Math.max(input.age - 26, 0) / 14);
  const loanPenalty = input.transferType.includes("loan") ? 0.08 : 0;
  return Number(clampNumber(0.50 * base + 0.30 * feeComponent + 0.20 * ageComponent - loanPenalty).toFixed(4));
}

function simulatorHistoryRows() {
  const latest = state.payload.latest_season;
  let rows = [];
  Object.entries(state.payload.signals_by_season || {}).forEach(([season, seasonRows]) => {
    if (season !== latest) rows.push(...(seasonRows || []));
  });
  if (!rows.length) {
    Object.values(state.payload.signals_by_season || {}).forEach((seasonRows) => rows.push(...(seasonRows || [])));
  }
  return rows;
}

function simulatorSimilarity(current, historical) {
  let score = 0;
  if (current.club === historical.club) score += 0.16;
  if (current.direction === historical.direction) score += 0.18;
  else if (current.direction && historical.direction) score -= 0.08;
  if (current.targetRole === historical.target_role) score += 0.10;
  if (current.position && current.position === historical.position) score += 0.12;
  score += Math.max(0, 0.18 - Math.abs(current.credibility - Number(historical.credibility_score || 0)) * 0.30);
  score += Math.max(0, 0.16 - Math.abs(current.transferIndicator - Number(historical.transfer_indicator || 0)) * 0.28);
  score += Math.max(0, 0.10 - Math.abs(current.stageScore - Number(historical.rumor_stage_score || 0)) * 0.20);
  score += Math.max(0, 0.08 - Math.abs((current.age || 0) - Number(historical.age || 0)) / 20);
  score += Math.max(0, 0.12 - Math.abs((current.marketValue || 0) - Number(historical.market_value_eur || 0)) / 250000000);
  return Number(score.toFixed(4));
}

function simulatorNearestExamples(current, limit = 3) {
  const seen = new Set();
  return simulatorHistoryRows()
    .map((row) => ({ row, similarity: simulatorSimilarity(current, row) }))
    .sort((a, b) => b.similarity - a.similarity)
    .filter(({ row }) => {
      const key = `${row.club || ""}:${row.player || ""}:${row.published_date || row.date || ""}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .slice(0, limit)
    .map(({ row, similarity }) => ({
      similarity,
      date: row.published_date || row.date || "",
      club: row.club || "",
      player: row.player || "",
      direction: row.direction || "",
      actual: row.actual_label || "",
      car: row.target_abnormal_return_p3 || "",
      credibility: row.credibility_score || "",
      transfer: row.transfer_indicator || "",
    }));
}

function collectSimulatorInputs() {
  return {
    targetClub: document.getElementById("simTargetClub").value,
    role: document.getElementById("simTargetRole").value,
    age: simulatorNumber("simAge", 27),
    position: document.getElementById("simPosition").value.trim(),
    marketValue: simulatorNumber("simMarketValue", 0),
    fee: simulatorNumber("simTransferFee", 0),
    wage: simulatorNumber("simWage", 0),
    rumorStage: document.getElementById("simRumorStage").value,
    source: document.getElementById("simSource").value.trim(),
    journalist: document.getElementById("simJournalist").value.trim(),
    transferType: document.getElementById("simTransferType").value,
  };
}

function runScenarioSimulator() {
  const input = collectSimulatorInputs();
  const direction = simulatorDirection(input.role);
  const transferIndicator = simulatorTransferIndicator(input);
  const credibility = simulatorCredibility(input.source, input.journalist);
  const stageScore = SIM_STAGE_SCORES[input.rumorStage] || SIM_STAGE_SCORES.unclear;
  const rumorIndicator = Number(clampNumber(0.58 * credibility.score + 0.32 * stageScore + 0.10 * (input.transferType.includes("loan") ? 0.35 : 0.55)).toFixed(4));
  const directionSign = direction === "in" ? 1 : 0.65;
  const midpoint = Math.max(-0.08, Math.min(0.08, (rumorIndicator - 0.5) * 0.05 + (transferIndicator - 0.5) * 0.06 * directionSign));
  const impactConfidence = clampNumber(0.35 + 0.45 * rumorIndicator);
  const confidence = Number(clampNumber(0.35 * credibility.score + 0.35 * stageScore + 0.30 * impactConfidence).toFixed(4));
  const halfWidth = 0.018 + (1 - confidence) * 0.045;
  const low = Math.max(-0.10, midpoint - halfWidth);
  const high = Math.min(0.10, midpoint + halfWidth);
  const label = low > 0.005 ? "positive" : (high < -0.005 ? "negative" : "watch");
  const warnings = [
    "Exploratory simulator only; this is not investment advice.",
    "Historical realized returns are used only as nearest examples, not as input features.",
    ...credibility.warnings,
  ];
  if (!(state.payload.club_media?.[input.targetClub]?.ticker)) {
    warnings.push("Target club has no configured public ticker; impact should be read as transfer intelligence only.");
  }
  if (input.transferType.includes("loan")) {
    warnings.push("Loan scenarios are discounted because fee, wage, and option terms are often incomplete.");
  }
  const current = {
    club: input.targetClub,
    direction,
    targetRole: input.role,
    position: input.position,
    credibility: credibility.score,
    transferIndicator,
    stageScore,
    age: input.age,
    marketValue: input.marketValue,
  };
  return {
    input,
    direction,
    transferIndicator,
    credibilityIndicator: Number(credibility.score.toFixed(4)),
    rumorIndicator,
    rumorStageScore: stageScore,
    estimatedImpact: {
      midpoint: Number(midpoint.toFixed(4)),
      low: Number(low.toFixed(4)),
      high: Number(high.toFixed(4)),
      label,
    },
    confidence,
    nearestHistoricalExamples: simulatorNearestExamples(current),
    scenarioSwarmSeed: {
      signal: {
        player: "Hypothetical Player",
        club: input.targetClub,
        target_club: input.targetClub,
        target_role: input.role,
        rumor_stage: input.rumorStage,
        credibility_score: Number(credibility.score.toFixed(4)),
        transfer_indicator: transferIndicator,
        rumor_indicator: rumorIndicator,
        predicted_label: label,
        blended_label: label,
        prediction_confidence: confidence,
        latest_source: input.source,
        latest_journalist: input.journalist,
      },
    },
    warnings,
  };
}

function renderScenarioSimulator() {
  const clubSelect = document.getElementById("simTargetClub");
  const sourceList = document.getElementById("simSourceOptions");
  const journalistList = document.getElementById("simJournalistOptions");
  if (clubSelect && !clubSelect.options.length) {
    clubSelect.innerHTML = availableClubNames().map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");
    if (availableClubNames().includes("Manchester United")) clubSelect.value = "Manchester United";
  }
  if (sourceList && !sourceList.children.length) {
    sourceList.innerHTML = (state.payload.leaderboards?.sources || []).slice(0, 20).map((row) => `<option value="${escapeHtml(row.source || "")}"></option>`).join("");
  }
  if (journalistList && !journalistList.children.length) {
    journalistList.innerHTML = (state.payload.leaderboards?.journalists || []).slice(0, 20).map((row) => `<option value="${escapeHtml(row.journalist || "")}"></option>`).join("");
  }
  const container = document.getElementById("scenarioSimulatorResult");
  if (!state.simulatorResult) {
    container.innerHTML = `
      <div class="simulator-empty">
        <strong>Build a what-if rumor.</strong>
        <span class="detail-meta">The simulator uses only your inputs plus local historical examples. It does not fetch news or make a trade recommendation.</span>
      </div>
    `;
    return;
  }
  const result = state.simulatorResult;
  container.innerHTML = `
    <div class="simulator-result">
      <div class="simulator-summary">
        <div>
          <span class="metric-label">Estimated Impact Range</span>
          <strong>${fmtSignedPct(result.estimatedImpact.low, 1)} to ${fmtSignedPct(result.estimatedImpact.high, 1)}</strong>
          <span class="detail-meta">Midpoint ${fmtSignedPct(result.estimatedImpact.midpoint, 1)} · confidence ${fmtPct(result.confidence, 0)}</span>
        </div>
        <span class="${stancePillClass(result.estimatedImpact.label === "watch" ? "watch" : (result.estimatedImpact.label === "positive" ? "bullish" : "bearish"))}">${escapeHtml(result.estimatedImpact.label)}</span>
      </div>
      <div class="scenario-metrics">
        <div class="metric-card"><span class="metric-label">Transfer indicator</span><strong>${fmtNumber(result.transferIndicator, 3)}</strong></div>
        <div class="metric-card"><span class="metric-label">Credibility</span><strong>${fmtNumber(result.credibilityIndicator, 3)}</strong></div>
        <div class="metric-card"><span class="metric-label">Rumor indicator</span><strong>${fmtNumber(result.rumorIndicator, 3)}</strong></div>
        <div class="metric-card"><span class="metric-label">Stage score</span><strong>${fmtNumber(result.rumorStageScore, 3)}</strong></div>
      </div>
      <div class="scenario-evidence-grid">
        <div class="detail-card">
          <div class="section-head"><h3>Nearest Historical Examples</h3></div>
          ${result.nearestHistoricalExamples.length ? `
            <div class="table-wrap">
              <table>
                <thead><tr><th>Player</th><th>Club</th><th>Similarity</th><th>Actual</th><th>CAR</th></tr></thead>
                <tbody>
                  ${result.nearestHistoricalExamples.map((row) => `
                    <tr>
                      <td>${escapeHtml(row.player || "-")}<br><span class="detail-meta">${escapeHtml(row.date || "")}</span></td>
                      <td>${clubChip(row.club)}</td>
                      <td>${fmtNumber(row.similarity, 3)}</td>
                      <td>${escapeHtml(row.actual || "-")}</td>
                      <td>${fmtNumber(row.car, 4)}</td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          ` : `<p class="detail-note">No historical examples available in the local payload.</p>`}
        </div>
        <div class="detail-card">
          <div class="section-head"><h3>Warnings</h3></div>
          <ul class="scenario-risk-list">
            ${result.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}
          </ul>
          <details class="simulator-seed">
            <summary>Scenario Swarm seed</summary>
            <pre><code>${escapeHtml(JSON.stringify(result.scenarioSwarmSeed.signal, null, 2))}</code></pre>
          </details>
        </div>
      </div>
    </div>
  `;
}

function leaderboardMarkup(rows, fields) {
  if (!rows.length) {
    return `<tr><td colspan="${fields.length}">No leaderboard rows yet.</td></tr>`;
  }
  return rows
    .map((row) => `
      <tr>
        ${fields.map((field) => {
          if (field === "smoothed_rate" || field === "avg_match_score") {
            return `<td>${fmtNumber(row[field], 3)}</td>`;
          }
          if (field === "match_rate") {
            return `<td>${fmtPct(row[field])}</td>`;
          }
          return `<td>${row[field] || "-"}</td>`;
        }).join("")}
      </tr>
    `)
    .join("");
}

function renderLeaderboards() {
  const leaderboards = state.payload.leaderboards || {};
  document.getElementById("journalistLeaderboard").innerHTML = leaderboardMarkup(
    leaderboards.journalists || [],
    ["journalist", "n_claims", "smoothed_rate", "avg_match_score"],
  );
  document.getElementById("sourceLeaderboard").innerHTML = leaderboardMarkup(
    leaderboards.sources || [],
    ["source", "n_claims", "smoothed_rate", "avg_match_score"],
  );
  document.getElementById("clubJournalistLeaderboard").innerHTML = leaderboardMarkup(
    leaderboards.club_journalists || [],
    ["club", "journalist", "smoothed_rate", "avg_match_score"],
  );
}

function trustGraphData(limit = 8) {
  const profiles = Object.values(state.payload.reporter_profiles || {})
    .filter((profile) => profile.journalist)
    .sort((a, b) => Number(b.smoothed_rate || 0) - Number(a.smoothed_rate || 0) || Number(b.n_claims || 0) - Number(a.n_claims || 0))
    .slice(0, limit);
  const reporters = profiles.map((profile) => ({
    id: `reporter:${profile.journalist}`,
    type: "reporter",
    label: profile.journalist,
    nClaims: Number(profile.n_claims || 0),
    score: Number(profile.smoothed_rate || 0),
  }));
  const sourceMap = new Map();
  const clubMap = new Map();
  const edges = [];
  profiles.forEach((profile) => {
    const reporterId = `reporter:${profile.journalist}`;
    (profile.sources || []).slice(0, 2).forEach((source) => {
      const name = source.source || "Unknown source";
      const sourceId = `source:${name}`;
      if (!sourceMap.has(sourceId)) {
        sourceMap.set(sourceId, { id: sourceId, type: "source", label: name, nClaims: 0, score: 0 });
      }
      const sourceNode = sourceMap.get(sourceId);
      sourceNode.nClaims += Number(source.count || 0);
      sourceNode.score = Math.max(sourceNode.score, Number(profile.smoothed_rate || 0));
      edges.push({
        from: reporterId,
        to: sourceId,
        weight: Number(source.count || 1),
        score: Number(profile.smoothed_rate || 0),
        kind: "reported via",
      });
    });
    (profile.clubs || []).slice(0, 3).forEach((club) => {
      const name = club.club || "Unknown club";
      const clubId = `club:${name}`;
      if (!clubMap.has(clubId)) {
        clubMap.set(clubId, { id: clubId, type: "club", label: name, nClaims: 0, score: 0 });
      }
      const clubNode = clubMap.get(clubId);
      clubNode.nClaims += Number(club.count || 0);
      clubNode.score = Math.max(clubNode.score, Number(profile.smoothed_rate || 0));
      const source = (profile.sources || [])[0]?.source || "Source mix";
      const sourceId = `source:${source}`;
      if (!sourceMap.has(sourceId)) {
        sourceMap.set(sourceId, { id: sourceId, type: "source", label: source, nClaims: 0, score: Number(profile.smoothed_rate || 0) });
      }
      edges.push({
        from: sourceId,
        to: clubId,
        weight: Number(club.count || 1),
        score: Number(profile.smoothed_rate || 0),
        kind: "covers",
        reporter: profile.journalist,
      });
    });
  });
  return {
    reporters,
    sources: Array.from(sourceMap.values()).sort((a, b) => b.nClaims - a.nClaims).slice(0, limit),
    clubs: Array.from(clubMap.values()).sort((a, b) => b.nClaims - a.nClaims).slice(0, limit),
    edges,
  };
}

function nodePositions(nodes, x, width, height) {
  const gap = height / Math.max(nodes.length + 1, 2);
  const positions = new Map();
  nodes.forEach((node, index) => {
    positions.set(node.id, { ...node, x, y: Math.round(gap * (index + 1)) });
  });
  return positions;
}

function trustNodeMarkup(node) {
  const isClub = node.type === "club";
  const isReporter = node.type === "reporter";
  const width = node.type === "source" ? 150 : 170;
  const height = 34;
  const x = node.x - width / 2;
  const y = node.y - height / 2;
  const action = isClub ? `data-club-route="${escapeHtml(node.label)}"` : (isReporter ? `data-reporter-node="${escapeHtml(node.label)}"` : "");
  return `
    <g class="trust-node trust-node-${node.type}" ${action} tabindex="${isClub || isReporter ? "0" : "-1"}" role="${isClub || isReporter ? "button" : "img"}">
      <rect x="${x}" y="${y}" width="${width}" height="${height}" rx="8"></rect>
      <text x="${node.x}" y="${node.y - 2}" text-anchor="middle">${escapeHtml(node.label).slice(0, 24)}</text>
      <text class="trust-node-sub" x="${node.x}" y="${node.y + 11}" text-anchor="middle">${node.nClaims || 0} claims · ${fmtNumber(node.score, 3)}</text>
    </g>
  `;
}

function trustEdgeMarkup(edge, positions) {
  const from = positions.get(edge.from);
  const to = positions.get(edge.to);
  if (!from || !to) return "";
  const strokeWidth = Math.max(1.2, Math.min(6, 1 + Number(edge.weight || 1) * 0.6));
  const opacity = Math.max(0.22, Math.min(0.78, Number(edge.score || 0.4)));
  const controlA = from.x + (to.x - from.x) * 0.45;
  const controlB = from.x + (to.x - from.x) * 0.55;
  return `
    <path class="trust-edge" d="M ${from.x + 80} ${from.y} C ${controlA} ${from.y}, ${controlB} ${to.y}, ${to.x - 80} ${to.y}" stroke-width="${strokeWidth}" opacity="${opacity}">
      <title>${escapeHtml(edge.kind)} · weight ${edge.weight} · score ${fmtNumber(edge.score, 3)}</title>
    </path>
  `;
}

function renderTrustGraph() {
  const container = document.getElementById("trustGraph");
  const data = trustGraphData();
  if (!data.reporters.length) {
    container.innerHTML = `<div class="empty-detail"><h2>No trust graph yet</h2><p>Run the credibility pipeline with reporter stats, then rebuild dashboard data.</p></div>`;
    return;
  }
  const width = 980;
  const height = Math.max(300, Math.max(data.reporters.length, data.sources.length, data.clubs.length) * 56 + 40);
  const positions = new Map([
    ...nodePositions(data.reporters, 120, width, height),
    ...nodePositions(data.sources, width / 2, width, height),
    ...nodePositions(data.clubs, width - 130, width, height),
  ]);
  const visibleIds = new Set(Array.from(positions.keys()));
  const visibleEdges = data.edges.filter((edge) => visibleIds.has(edge.from) && visibleIds.has(edge.to));
  container.innerHTML = `
    <div class="trust-graph-wrap">
      <svg class="trust-graph-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Reporter source club trust graph">
        <text class="trust-column-label" x="120" y="20" text-anchor="middle">Reporters</text>
        <text class="trust-column-label" x="${width / 2}" y="20" text-anchor="middle">Sources</text>
        <text class="trust-column-label" x="${width - 130}" y="20" text-anchor="middle">Clubs</text>
        ${visibleEdges.map((edge) => trustEdgeMarkup(edge, positions)).join("")}
        ${Array.from(positions.values()).map(trustNodeMarkup).join("")}
      </svg>
    </div>
    <div class="trust-table table-wrap">
      <table>
        <thead><tr><th>Reporter</th><th>Source</th><th>Club</th><th>Claims</th><th>Smoothed</th></tr></thead>
        <tbody>
          ${data.reporters.flatMap((reporter) => {
            const profile = (state.payload.reporter_profiles || {})[reporter.label] || {};
            const source = (profile.sources || [])[0]?.source || "-";
            return (profile.clubs || []).slice(0, 3).map((club) => `
              <tr>
                <td><button class="link-button" data-reporter-node="${escapeHtml(reporter.label)}">${escapeHtml(reporter.label)}</button></td>
                <td>${escapeHtml(source)}</td>
                <td><button class="link-button" data-club-route="${escapeHtml(club.club || "")}">${escapeHtml(club.club || "-")}</button></td>
                <td>${club.count || 0}</td>
                <td>${fmtNumber(reporter.score, 3)}</td>
              </tr>
            `);
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
  container.querySelectorAll("[data-reporter-node]").forEach((node) => {
    node.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      state.selectedReporter = node.dataset.reporterNode;
      renderReporterProfiles();
      document.getElementById("reporterProfilesSection")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    node.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      node.dispatchEvent(new Event("click", { bubbles: true }));
    });
  });
}

function renderSourceCoverage() {
  const body = document.getElementById("sourceCoverageTable");
  const rows = state.payload.live_source_coverage || [];
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="5">No recent direct-target live coverage rows yet.</td></tr>`;
    return;
  }
  body.innerHTML = rows
    .map((row) => `
      <tr>
        <td><strong>${row.source}</strong></td>
        <td>${row.n_rows}</td>
        <td>${row.n_unique_players}</td>
        <td>${fmtDate(row.latest_published_at)}</td>
        <td>${fmtNumber(row.avg_credibility, 3)}</td>
      </tr>
    `)
    .join("");
}

function renderBacktests() {
  const body = document.getElementById("backtestTable");
  body.innerHTML = state.payload.backtests
    .map((row) => `
      <tr>
        <td><strong>${row.strategy}</strong></td>
        <td>${row.n_trades}</td>
        <td>${fmtNumber(row.win_rate, 4)}</td>
        <td>${fmtNumber(row.avg_trade_return, 4)}</td>
        <td>${fmtNumber(row.portfolio_total_return, 4)}</td>
        <td>${fmtNumber(row.sharpe_like, 3)}</td>
        <td>${fmtNumber(row.max_drawdown, 4)}</td>
      </tr>
    `)
    .join("");
}

function renderDataFlow() {
  const flow = document.getElementById("dataFlow");
  flow.innerHTML = Object.entries(state.payload.data_flow)
    .map(([key, value]) => `
      <div class="flow-card">
        <span class="flow-path">${key}</span>
        <code>${value}</code>
      </div>
    `)
    .join("");
}

function renderAll() {
  renderViewTabs();
  renderSeasonFilters();
  renderClubFilters();
  renderRouteChrome();
  renderOverview();
  renderHeroObservatory();
  renderMarketCockpit();
  renderRunbooks();
  renderFocusBrief();
  renderTakeaways();
  renderDataQuality();
  renderAskAnalyst();
  renderAgentAccess();
  renderRumorGraph();
  renderAgentRun();
  renderRagAudit();
  renderAutopilot();
  renderScenarioSwarm();
  renderScenarioSimulator();
  renderClubDossier();
  renderClubComparison();
  renderWorkspaceShell();
  renderWorkspaceTable();
  renderDetail();
  renderWatchlist();
  renderLiveSignalCards();
  renderSourceCoverage();
  renderLeaderboards();
  renderTrustGraph();
  renderReporterProfiles();
  renderSeasonHistory();
  renderBacktests();
  renderDataFlow();
  applySectionTabVisibility();
  applySectionCollapseState();
}

function setupTasteReveals() {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const sections = Array.from(document.querySelectorAll(".shell > section"));
  if (!("IntersectionObserver" in window)) {
    sections.forEach((section) => section.classList.add("is-visible"));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.04, rootMargin: "0px 0px -7% 0px" });
  sections.forEach((section) => {
    section.classList.add("taste-reveal");
    observer.observe(section);
  });
}

function wireControls() {
  setupSectionChrome();
  document.getElementById("backToBoard").addEventListener("click", () => {
    goToMarket();
  });
  document.getElementById("sectionMenuToggle")?.addEventListener("click", () => {
    openSectionDrawer();
  });
  document.getElementById("sectionDrawerClose")?.addEventListener("click", () => {
    closeSectionDrawer();
  });
  document.getElementById("sectionScrim")?.addEventListener("click", () => {
    closeSectionDrawer();
  });
  document.getElementById("expandAllSections")?.addEventListener("click", () => {
    expandAllDashboardSections();
  });
  document.getElementById("collapseAllSections")?.addEventListener("click", () => {
    collapseDashboardSections({ reportsOnly: true });
  });
  document.getElementById("expandAllTop")?.addEventListener("click", () => {
    expandAllDashboardSections();
  });
  document.getElementById("collapseAllTop")?.addEventListener("click", () => {
    collapseDashboardSections();
  });
  document.getElementById("demoModeButton")?.addEventListener("click", () => {
    applyDemoMode();
  });
  document.querySelectorAll("#sectionTabs button").forEach((button) => {
    button.addEventListener("click", () => {
      state.sectionTab = button.dataset.sectionTab || "main";
      saveSectionTab();
      renderAll();
      document.getElementById("viewModeBand")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  document.getElementById("compareClubA").addEventListener("change", (event) => {
    state.compareClubA = event.target.value;
    renderClubComparison();
  });
  document.getElementById("compareClubB").addEventListener("change", (event) => {
    state.compareClubB = event.target.value;
    renderClubComparison();
  });
  document.getElementById("reporterSelect").addEventListener("change", (event) => {
    state.selectedReporter = event.target.value;
    renderReporterProfiles();
  });
  document.getElementById("askAnalystForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const question = document.getElementById("askAnalystInput").value.trim();
    if (!question) return;
    state.askQuestion = question;
    state.askResult = askAnalyst(question);
    renderAskAnalyst();
  });
  document.querySelectorAll("#askAnalystExamples button").forEach((button) => {
    button.addEventListener("click", () => {
      state.askQuestion = button.dataset.question || "";
      state.askResult = askAnalyst(state.askQuestion);
      renderAskAnalyst();
    });
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-agent-question]");
    if (!button) return;
    event.preventDefault();
    state.askQuestion = button.dataset.agentQuestion || "";
    state.askResult = askAnalyst(state.askQuestion);
    renderAskAnalyst();
    document.getElementById("askAnalystSection")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  document.getElementById("scenarioSimulatorForm").addEventListener("submit", (event) => {
    event.preventDefault();
    state.simulatorResult = runScenarioSimulator();
    renderScenarioSimulator();
  });
  document.getElementById("searchInput").addEventListener("input", (event) => {
    state.search = event.target.value;
    renderAll();
  });
  document.addEventListener("click", (event) => {
    const jump = event.target.closest("[data-jump]");
    if (!jump) return;
    const section = document.getElementById(jump.dataset.jump);
    if (!section) return;
    event.preventDefault();
    if (state.page !== "club") {
      const nextTab = tabForSection(jump.dataset.jump);
      if (nextTab !== state.sectionTab) {
        state.sectionTab = nextTab;
        saveSectionTab();
        renderAll();
      }
    }
    if (state.collapsedSections.has(jump.dataset.jump)) {
      toggleSectionCollapsed(jump.dataset.jump, false);
    }
    closeSectionDrawer();
    window.requestAnimationFrame(() => {
      document.getElementById(jump.dataset.jump)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-section-collapse]");
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    toggleSectionCollapsed(button.dataset.sectionCollapse);
  });
  document.addEventListener("click", (event) => {
    const signal = event.target.closest("[data-select-signal]");
    if (!signal) return;
    event.preventDefault();
    state.selectedView = "rumors";
    state.selectedSeason = state.payload.latest_season;
    state.clubFilter = "All";
    state.sectionTab = "signals";
    saveSectionTab();
    state.selectedKey = signal.dataset.selectSignal || null;
    renderAll();
    document.getElementById("workspaceSection")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-run-research-cycle]");
    if (!button) return;
    event.preventDefault();
    requestResearchCycle();
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-run-runbook]");
    if (!button) return;
    event.preventDefault();
    requestRunbook(button.dataset.runRunbook);
  });
  document.addEventListener("click", async (event) => {
    const copy = event.target.closest("[data-copy-memo]");
    if (!copy) return;
    event.preventDefault();
    const memo = decodeURIComponent(copy.dataset.copyMemo || "");
    try {
      await navigator.clipboard.writeText(memo);
      copy.textContent = "Copied";
      window.setTimeout(() => {
        copy.textContent = "Copy";
      }, 1400);
    } catch (error) {
      const textarea = document.createElement("textarea");
      textarea.value = memo;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
      copy.textContent = "Copied";
      window.setTimeout(() => {
        copy.textContent = "Copy";
      }, 1400);
    }
  });
  document.addEventListener("click", (event) => {
    const download = event.target.closest("[data-download-memo]");
    if (!download) return;
    event.preventDefault();
    const memo = decodeURIComponent(download.dataset.downloadMemo || "");
    const filename = `${(download.dataset.memoTitle || "research-memo").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "research-memo"}.md`;
    const blob = new Blob([memo], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });
  document.querySelectorAll("#sortFilters button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("#sortFilters button").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      state.sortMode = button.dataset.sort;
      renderAll();
    });
  });
  document.querySelectorAll("#viewTabs button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedView = button.dataset.view;
      if (state.page !== "club") {
        state.clubFilter = "All";
      }
      state.selectedKey = null;
      renderAll();
    });
  });
  document.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-club-route]");
    if (!chip) return;
    event.preventDefault();
    event.stopPropagation();
    goToClub(chip.dataset.clubRoute);
  }, true);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSectionDrawer();
      return;
    }
    const chip = event.target.closest?.("[data-club-route]");
    if (!chip) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    event.stopPropagation();
    goToClub(chip.dataset.clubRoute);
  });
}

async function boot() {
  const response = await fetch("./data/dashboard_data.json", { cache: "no-store" });
  state.payload = await response.json();
  state.agent = await loadAgentSnapshot();
  state.ragAudit = await loadRagAuditSnapshot();
  state.autopilot = await loadAutopilotSnapshot();
  state.operator = await loadOperatorSnapshot();
  state.runbooks = await loadRunbookSnapshot();
  state.agentManifest = await loadAgentManifest();
  state.rumorGraph = await loadRumorGraph();
  state.scenario = await loadScenarioSnapshot();
  state.dataQuality = await loadDataQualitySnapshot();
  state.collapsedSections = loadCollapsedSections();
  state.sectionTab = loadSectionTab();
  state.selectedSeason = state.payload.latest_season;
  applyRouteFromHash();
  wireControls();
  window.addEventListener("hashchange", () => {
    applyRouteFromHash();
    renderAll();
  });
  syncHash();
  renderAll();
  setupTasteReveals();
}

async function loadScenarioSnapshot() {
  try {
    const response = await fetch("./data/scenario_latest.json", { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

async function loadAgentSnapshot() {
  try {
    const response = await fetch("./data/agent_latest.json", { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

async function loadRagAuditSnapshot() {
  try {
    const response = await fetch("./data/rag_audit_latest.json", { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

async function loadAutopilotSnapshot() {
  try {
    const response = await fetch("./data/autopilot_latest.json", { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

async function loadOperatorSnapshot() {
  try {
    const response = await fetch("./data/operator_latest.json", { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

async function loadRunbookSnapshot() {
  try {
    const response = await fetch("./data/runbooks.json", { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

async function loadAgentManifest() {
  try {
    const response = await fetch("./.well-known/transfer-stock-agent.json", { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

async function loadRumorGraph() {
  try {
    const response = await fetch("./data/rumor_graph.json", { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

async function loadDataQualitySnapshot() {
  try {
    const response = await fetch("./data/data_quality_latest.json", { cache: "no-store" });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    return null;
  }
}

boot().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<main style="padding:24px;font-family:sans-serif"><h1>Dashboard failed to load</h1><p>${error.message}</p></main>`;
});
