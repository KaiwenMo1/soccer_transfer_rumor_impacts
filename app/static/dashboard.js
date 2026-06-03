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
  scenario: null,
  dataQuality: null,
  simulatorResult: null,
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
  syncHash();
  renderAll();
}

function goToMarket() {
  state.page = "market";
  state.routeClub = null;
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

function sparklineSvg(chart, markers = []) {
  const points = chart?.points || [];
  if (!points.length) return "";
  const width = 360;
  const height = 112;
  const padding = 12;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = Math.max(max - min, 1e-6);
  const xFor = (index) => padding + (index * (width - padding * 2)) / Math.max(points.length - 1, 1);
  const yFor = (value) => height - padding - ((value - min) / span) * (height - padding * 2);
  const polyline = points.map((value, index) => `${xFor(index)},${yFor(value)}`).join(" ");
  const baselineY = yFor(100);
  const hasEvent = chart.event_index !== undefined && chart.event_index !== null && chart.event_index !== "";
  const eventX = hasEvent ? xFor(Number(chart.event_index)) : 0;
  const latestX = xFor(points.length - 1);
  const latestY = yFor(points[points.length - 1]);
  const gridLines = [0.25, 0.5, 0.75].map((ratio) => padding + ratio * (height - padding * 2));
  const markerSvg = markers.map((marker) => {
    const markerIndex = Number(marker.index);
    if (!Number.isFinite(markerIndex) || markerIndex < 0 || markerIndex >= points.length) return "";
    const x = xFor(markerIndex);
    if (marker.kind === "match") {
      const y = yFor(points[markerIndex]);
      const sentiment = marker.sentiment || "neutral";
      const title = `${marker.result || "Match"} ${marker.score || ""} vs ${marker.opponent || ""} (${marker.match_date || marker.date || ""})`;
      return `
        <g class="sparkline-match-point">
          <title>${escapeHtml(title)}</title>
          <circle class="sparkline-match-dot sparkline-match-${sentiment}" cx="${x}" cy="${y}" r="4.4"></circle>
        </g>
      `;
    }
    return `
      <line class="sparkline-marker" x1="${x}" y1="${padding + 4}" x2="${x}" y2="${height - padding}"></line>
      <circle class="sparkline-marker-dot" cx="${x}" cy="${height - padding}" r="2.2"></circle>
    `;
  }).join("");
  return `
    <svg class="sparkline-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      ${gridLines.map((y) => `<line class="sparkline-grid" x1="${padding}" y1="${y}" x2="${width - padding}" y2="${y}"></line>`).join("")}
      <line class="sparkline-baseline" x1="${padding}" y1="${baselineY}" x2="${width - padding}" y2="${baselineY}"></line>
      ${hasEvent ? `<line class="sparkline-event" x1="${eventX}" y1="${padding}" x2="${eventX}" y2="${height - padding}"></line>` : ""}
      <polyline class="sparkline-line" points="${polyline}"></polyline>
      ${markerSvg}
      <circle class="sparkline-latest" cx="${latestX}" cy="${latestY}" r="2.8"></circle>
    </svg>
  `;
}

function stockChartMarkup(chart, markers = []) {
  if (!chart || !(chart.points || []).length) {
    return `<div class="sparkline-empty">No stock history slice yet</div>`;
  }
  const hasMatchMarkers = markers.some((marker) => marker.kind === "match");
  const markerLabel = hasMatchMarkers ? "match result" : "linked news date";
  return `
    <div class="sparkline-card">
      <div class="sparkline-meta">
        <span>Pre ${fmtSignedPct(chart.pre_change, 1)}</span>
        <span>Since event ${fmtSignedPct(chart.latest_change, 1)}</span>
        <span>${markers.length} ${markerLabel}${markers.length === 1 ? "" : "s"}</span>
      </div>
      <div class="sparkline-wrap">${sparklineSvg(chart, markers)}</div>
      <div class="sparkline-meta">
        <span>${escapeHtml(chart.dates?.[0] || "")}</span>
        <span>${chart.event_date ? `Event ${escapeHtml(chart.event_date)}` : escapeHtml(chart.ticker || "")}</span>
        <span>${escapeHtml(chart.latest_date || "")}</span>
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
          <button type="button" data-jump="askAnalystSection">Ask analyst</button>
          <button type="button" data-jump="dataQualitySection">Audit details</button>
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
    </div>
  `;
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
  renderMarketCockpit();
  renderTakeaways();
  renderDataQuality();
  renderAskAnalyst();
  renderAgentRun();
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
}

function wireControls() {
  document.getElementById("backToBoard").addEventListener("click", () => {
    goToMarket();
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
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  document.addEventListener("click", (event) => {
    const signal = event.target.closest("[data-select-signal]");
    if (!signal) return;
    event.preventDefault();
    state.selectedView = "rumors";
    state.selectedSeason = state.payload.latest_season;
    state.clubFilter = "All";
    state.selectedKey = signal.dataset.selectSignal || null;
    renderAll();
    document.getElementById("workspaceSection")?.scrollIntoView({ behavior: "smooth", block: "start" });
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
  state.scenario = await loadScenarioSnapshot();
  state.dataQuality = await loadDataQualitySnapshot();
  state.selectedSeason = state.payload.latest_season;
  applyRouteFromHash();
  wireControls();
  window.addEventListener("hashchange", () => {
    applyRouteFromHash();
    renderAll();
  });
  syncHash();
  renderAll();
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
