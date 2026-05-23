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
  const width = 240;
  const height = 72;
  const padding = 8;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = Math.max(max - min, 1e-6);
  const xFor = (index) => padding + (index * (width - padding * 2)) / Math.max(points.length - 1, 1);
  const yFor = (value) => height - padding - ((value - min) / span) * (height - padding * 2);
  const polyline = points.map((value, index) => `${xFor(index)},${yFor(value)}`).join(" ");
  const baselineY = yFor(100);
  const eventX = xFor(chart.event_index || 0);
  const latestX = xFor(points.length - 1);
  const latestY = yFor(points[points.length - 1]);
  return `
    <svg class="sparkline-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <line class="sparkline-baseline" x1="${padding}" y1="${baselineY}" x2="${width - padding}" y2="${baselineY}"></line>
      ${markers.map((marker) => {
        const x = xFor(marker.index);
        return `
          <line class="sparkline-marker" x1="${x}" y1="${padding + 6}" x2="${x}" y2="${height - padding}"></line>
          <circle class="sparkline-marker-dot" cx="${x}" cy="${height - padding + 1}" r="2.2"></circle>
        `;
      }).join("")}
      <line class="sparkline-event" x1="${eventX}" y1="${padding}" x2="${eventX}" y2="${height - padding}"></line>
      <polyline class="sparkline-line" points="${polyline}"></polyline>
      <circle class="sparkline-latest" cx="${latestX}" cy="${latestY}" r="2.8"></circle>
    </svg>
  `;
}

function stockChartMarkup(chart, markers = []) {
  if (!chart || !(chart.points || []).length) {
    return `<div class="sparkline-empty">No stock history slice yet</div>`;
  }
  return `
    <div class="sparkline-card">
      <div class="sparkline-meta">
        <span>Pre ${fmtSignedPct(chart.pre_change, 1)}</span>
        <span>Since event ${fmtSignedPct(chart.latest_change, 1)}</span>
        <span>${markers.length} linked news date${markers.length === 1 ? "" : "s"}</span>
      </div>
      <div class="sparkline-wrap">${sparklineSvg(chart, markers)}</div>
      <div class="sparkline-meta">
        <span>${escapeHtml(chart.dates?.[0] || "")}</span>
        <span>Event ${escapeHtml(chart.event_date || "")}</span>
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
  setSectionHidden("leaderboardsSection", isClubPage);
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
  renderTakeaways();
  renderClubDossier();
  renderWorkspaceShell();
  renderWorkspaceTable();
  renderDetail();
  renderWatchlist();
  renderLiveSignalCards();
  renderSourceCoverage();
  renderLeaderboards();
  renderSeasonHistory();
  renderBacktests();
  renderDataFlow();
}

function wireControls() {
  document.getElementById("backToBoard").addEventListener("click", () => {
    goToMarket();
  });
  document.getElementById("searchInput").addEventListener("input", (event) => {
    state.search = event.target.value;
    renderAll();
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

boot().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<main style="padding:24px;font-family:sans-serif"><h1>Dashboard failed to load</h1><p>${error.message}</p></main>`;
});
