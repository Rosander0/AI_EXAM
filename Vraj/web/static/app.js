/**
 * SANKET Invigilator Dashboard Frontend Logic.
 * Plain vanilla ES6 JavaScript. Zero external dependencies.
 */

let activeSessionId = null;
let pollTimer = null;
let timelineTimer = null;
let lastEventId = null;
let allEvents = [];
let allSeats = [];
let selectedSeatFilter = null;
let timelineData = { timestamps: [], seats: {} };
let previousScores = {};

// Palette Constants
const STATUS_COLORS = {
  calm: "#3E7A5E",
  accumulating: "#C8873A",
  alert: "#C4453D",
  line: "#24384F",
  muted: "#7C8FA6",
};

document.addEventListener("DOMContentLoaded", () => {
  initUI();
  fetchHealth();
  fetchSessionsList();
});

function initUI() {
  const startBtn = document.getElementById("btn-start");
  const stopBtn = document.getElementById("btn-stop");
  const uploadInput = document.getElementById("file-upload");
  const uploadBtn = document.getElementById("btn-upload");
  const filterAll = document.getElementById("filter-all");
  const filterAlerts = document.getElementById("filter-alerts");

  if (startBtn) startBtn.addEventListener("click", handleStartSession);
  if (stopBtn) stopBtn.addEventListener("click", handleStopSession);
  if (uploadBtn && uploadInput) {
    uploadBtn.addEventListener("click", () => uploadInput.click());
    uploadInput.addEventListener("change", handleFileUpload);
  }

  if (filterAll) filterAll.addEventListener("click", () => setAlertFilter(null));
  if (filterAlerts) filterAlerts.addEventListener("click", () => setAlertFilter("critical"));
}

async function fetchHealth() {
  try {
    const res = await fetch("/api/health");
    if (res.ok) {
      const data = await res.json();
      const devEl = document.getElementById("val-device");
      if (devEl) devEl.textContent = data.device.toUpperCase();
    }
  } catch (err) {
    console.warn("Could not fetch health:", err);
  }
}

async function fetchSessionsList() {
  try {
    const res = await fetch("/api/sessions");
    if (!res.ok) return;
    const sessions = await res.json();
    const select = document.getElementById("source-select");
    if (!select) return;

    // Check if any session is currently running
    const running = sessions.find((s) => s.state === "running");
    if (running && !activeSessionId) {
      attachToSession(running.session_id);
    }
  } catch (err) {
    console.warn("Could not fetch sessions list:", err);
  }
}

async function handleStartSession() {
  const select = document.getElementById("source-select");
  const rtspInput = document.getElementById("rtsp-input");

  let sourceSpec = select ? select.value : "";
  if (rtspInput && rtspInput.value.trim()) {
    sourceSpec = rtspInput.value.trim();
  }

  if (!sourceSpec) {
    alert("Please select a recording or enter an RTSP / webcam source.");
    return;
  }

  try {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: sourceSpec }),
    });

    if (res.status === 409) {
      const err = await res.json();
      alert(`Session already running: ${err.detail}`);
      return;
    }

    if (!res.ok) {
      const err = await res.json();
      alert(`Error starting session: ${err.detail || res.statusText}`);
      return;
    }

    const session = await res.json();
    attachToSession(session.session_id);
  } catch (err) {
    alert(`Failed to connect to backend: ${err.message}`);
  }
}

async function handleFileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  const uploadBtn = document.getElementById("btn-upload");
  if (uploadBtn) uploadBtn.textContent = "Uploading...";

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      alert(`Upload error: ${err.detail}`);
      return;
    }

    const data = await res.json();
    const select = document.getElementById("source-select");
    if (select) {
      const opt = document.createElement("option");
      opt.value = data.source_path;
      opt.textContent = `Uploaded: ${data.filename}`;
      opt.selected = true;
      select.prepend(opt);
    }
    alert(`Uploaded '${data.filename}'. Click Start Session to begin analysis.`);
  } catch (err) {
    alert(`Upload failed: ${err.message}`);
  } finally {
    if (uploadBtn) uploadBtn.textContent = "Upload Video";
  }
}

async function handleStopSession() {
  if (!activeSessionId) return;
  // Clear poll timers
  clearInterval(pollTimer);
  clearInterval(timelineTimer);
  activeSessionId = null;
  resetUI();
}

function attachToSession(sessionId) {
  activeSessionId = sessionId;
  lastEventId = null;
  allEvents = [];
  previousScores = {};

  const streamImg = document.getElementById("mjpeg-stream");
  if (streamImg) {
    streamImg.src = `/api/stream/${sessionId}`;
  }

  const startBtn = document.getElementById("btn-start");
  const stopBtn = document.getElementById("btn-stop");
  if (startBtn) startBtn.disabled = true;
  if (stopBtn) stopBtn.disabled = false;

  // Start polling
  if (pollTimer) clearInterval(pollTimer);
  if (timelineTimer) clearInterval(timelineTimer);

  pollTimer = setInterval(pollSessionState, 500);
  timelineTimer = setInterval(pollTimeline, 2000);

  pollSessionState();
  pollTimeline();
}

async function pollSessionState() {
  if (!activeSessionId) return;

  try {
    // 1. Session Status
    const sRes = await fetch(`/api/sessions/${activeSessionId}`);
    if (sRes.ok) {
      const session = await sRes.json();
      updateSessionMetrics(session);
      if (session.state === "done" || session.state === "failed") {
        clearInterval(pollTimer);
        const startBtn = document.getElementById("btn-start");
        const stopBtn = document.getElementById("btn-stop");
        if (startBtn) startBtn.disabled = false;
        if (stopBtn) stopBtn.disabled = true;
      }
    }

    // 2. Seats State
    const seatsRes = await fetch(`/api/sessions/${activeSessionId}/seats`);
    if (seatsRes.ok) {
      allSeats = await seatsRes.json();
      renderSeatGrid(allSeats);
    }

    // 3. Incremental Events
    const evUrl = lastEventId
      ? `/api/sessions/${activeSessionId}/events?since=${encodeURIComponent(lastEventId)}`
      : `/api/sessions/${activeSessionId}/events`;

    const evRes = await fetch(evUrl);
    if (evRes.ok) {
      const newEvents = await evRes.json();
      if (newEvents.length > 0) {
        lastEventId = newEvents[newEvents.length - 1].event_id;
        for (const ev of newEvents) {
          allEvents.unshift(ev); // Newest at top
        }
        renderAlertFeed();
      }
    }
  } catch (err) {
    console.warn("Polling error:", err);
  }
}

async function pollTimeline() {
  if (!activeSessionId) return;
  try {
    const res = await fetch(`/api/sessions/${activeSessionId}/timeline`);
    if (res.ok) {
      timelineData = await res.json();
      renderTimelineSVG(timelineData);
    }
  } catch (err) {
    console.warn("Timeline polling error:", err);
  }
}

function updateSessionMetrics(session) {
  const fpsEl = document.getElementById("val-fps");
  const framesEl = document.getElementById("val-frames");
  const seatsEl = document.getElementById("val-seats");
  const alertsEl = document.getElementById("val-alerts");
  const durEl = document.getElementById("val-duration");

  if (fpsEl) fpsEl.textContent = session.fps_processing.toFixed(1);
  if (framesEl) framesEl.textContent = `${session.frames_processed}`;
  if (seatsEl) seatsEl.textContent = `${session.seats_tracked}`;
  if (alertsEl) alertsEl.textContent = `${session.alerts_total}`;
  if (durEl) {
    const mins = Math.floor(session.duration_s / 60);
    const secs = Math.floor(session.duration_s % 60);
    durEl.textContent = `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  }
}

function renderSeatGrid(seats) {
  const grid = document.getElementById("seat-grid");
  if (!grid) return;

  if (seats.length === 0) {
    grid.innerHTML = "<div class='empty-state'>Discovering candidate seating layout...</div>";
    return;
  }

  // Sort by grid_row, then grid_col
  const sorted = [...seats].sort((a, b) => {
    if (a.grid_row !== b.grid_row) return a.grid_row - b.grid_row;
    return a.grid_col - b.grid_col;
  });

  grid.innerHTML = "";
  for (const s of sorted) {
    const card = document.createElement("div");
    card.className = `seat-card ${s.status}`;
    if (!s.calibrated) card.classList.add("calibrating");
    if (selectedSeatFilter === s.seat_id) card.classList.add("selected");

    // Check pulse trigger
    const prevScore = previousScores[s.seat_id] || 0.0;
    if (prevScore < 100.0 && s.score >= 100.0) {
      card.classList.add("pulse");
    }
    previousScores[s.seat_id] = s.score;

    card.addEventListener("click", () => toggleSeatFilter(s.seat_id));

    const calibTag = s.calibrated ? "" : " <span style='font-size:10px; color:#F0B429'>[CALIB]</span>";
    const sustainedTxt = s.sustained_seconds > 0 ? `Alert: ${s.sustained_seconds.toFixed(1)}s` : "";

    card.innerHTML = `
      <div class="seat-header">
        <span class="seat-id mono">${s.seat_id}${calibTag}</span>
        <span class="seat-score mono">${s.score.toFixed(1)}</span>
      </div>
      <div class="seat-sustained mono">${sustainedTxt}</div>
      <div class="seat-reason" title="${s.last_reason || ''}">${s.last_reason || "Normal observation"}</div>
    `;

    grid.appendChild(card);
  }
}

function toggleSeatFilter(seatId) {
  if (selectedSeatFilter === seatId) {
    selectedSeatFilter = null;
  } else {
    selectedSeatFilter = seatId;
  }
  renderSeatGrid(allSeats);
  renderAlertFeed();
  renderTimelineSVG(timelineData);
}

function setAlertFilter(severity) {
  const filterAll = document.getElementById("filter-all");
  const filterAlerts = document.getElementById("filter-alerts");

  if (severity === "critical") {
    if (filterAll) filterAll.classList.remove("active");
    if (filterAlerts) filterAlerts.classList.add("active");
  } else {
    if (filterAll) filterAll.classList.add("active");
    if (filterAlerts) filterAlerts.classList.remove("active");
  }

  renderAlertFeed();
}

function renderAlertFeed() {
  const feed = document.getElementById("alert-feed");
  if (!feed) return;

  let filtered = allEvents;
  if (selectedSeatFilter) {
    filtered = filtered.filter((e) => e.seat_id === selectedSeatFilter);
  }

  const filterAlertsBtn = document.getElementById("filter-alerts");
  if (filterAlertsBtn && filterAlertsBtn.classList.contains("active")) {
    filtered = filtered.filter((e) => e.severity === "critical");
  }

  if (filtered.length === 0) {
    feed.innerHTML = "<div class='empty-state'>No observation events recorded.</div>";
    return;
  }

  feed.innerHTML = "";
  for (const e of filtered) {
    const item = document.createElement("div");
    item.className = `alert-item ${e.severity}`;

    const clipBtn = e.clip_path
      ? `<a class="clip-btn" href="${e.clip_path}" target="_blank">Evidence Clip</a>`
      : "";

    item.innerHTML = `
      <div class="alert-top">
        <span class="alert-seat mono">${e.seat_id}</span>
        <span class="alert-time mono">${e.t_start.toFixed(1)}s - ${e.t_end.toFixed(1)}s</span>
      </div>
      <div class="alert-rule">${e.rule} (+${e.points.toFixed(0)} pts)</div>
      <div class="alert-reason">${e.reason}</div>
      ${clipBtn}
    `;

    feed.appendChild(item);
  }
}

function renderTimelineSVG(data) {
  const container = document.getElementById("timeline-container");
  if (!container || !data || !data.timestamps || data.timestamps.length === 0) {
    if (container) container.innerHTML = "<div class='empty-state'>Timeline points accumulating...</div>";
    return;
  }

  const width = container.clientWidth || 800;
  const height = container.clientHeight || 140;
  const padding = { top: 15, right: 30, bottom: 25, left: 45 };

  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const minT = data.timestamps[0] || 0;
  const maxT = Math.max(minT + 10, data.timestamps[data.timestamps.length - 1] || 10);
  const maxScore = 140.0; // Fixed y-scale ceiling to keep threshold visible

  const scaleX = (t) => padding.left + ((t - minT) / (maxT - minT)) * plotW;
  const scaleY = (s) => padding.top + plotH - (s / maxScore) * plotH;

  const threshY = scaleY(100.0);

  // Build SVG elements
  let svgPaths = "";
  const seatIds = Object.keys(data.seats || {});

  const SEAT_COLORS = ["#58A6FF", "#F0B429", "#7EE787", "#FFA657", "#D2A8FF", "#FF7B72"];

  seatIds.forEach((sid, idx) => {
    if (selectedSeatFilter && selectedSeatFilter !== sid) return;

    const points = data.seats[sid];
    if (!points || points.length === 0) return;

    const color = SEAT_COLORS[idx % SEAT_COLORS.length];
    const pathD = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${scaleX(p.t).toFixed(1)} ${scaleY(p.score).toFixed(1)}`)
      .join(" ");

    svgPaths += `<path d="${pathD}" fill="none" stroke="${color}" stroke-width="2" opacity="0.85" />`;
  });

  const svgContent = `
    <svg class="timeline-svg" viewBox="0 0 ${width} ${height}">
      <!-- Background grid lines -->
      <line x1="${padding.left}" y1="${threshY}" x2="${width - padding.right}" y2="${threshY}" stroke="#C4453D" stroke-dasharray="4,4" stroke-width="1.5" />
      <text x="${width - padding.right + 4}" y="${threshY + 3}" fill="#C4453D" font-size="10" font-family="monospace">100 (Alert)</text>

      <!-- Axes -->
      <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}" stroke="#24384F" stroke-width="1" />
      <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" stroke="#24384F" stroke-width="1" />

      <!-- Y-Axis Labels -->
      <text x="${padding.left - 6}" y="${scaleY(0) + 3}" fill="#7C8FA6" font-size="10" text-anchor="end" font-family="monospace">0</text>
      <text x="${padding.left - 6}" y="${scaleY(50) + 3}" fill="#7C8FA6" font-size="10" text-anchor="end" font-family="monospace">50</text>
      <text x="${padding.left - 6}" y="${scaleY(100) + 3}" fill="#C4453D" font-size="10" text-anchor="end" font-family="monospace">100</text>

      <!-- X-Axis Labels -->
      <text x="${scaleX(minT)}" y="${height - 6}" fill="#7C8FA6" font-size="10" font-family="monospace">${minT.toFixed(0)}s</text>
      <text x="${scaleX(maxT)}" y="${height - 6}" fill="#7C8FA6" font-size="10" font-family="monospace" text-anchor="end">${maxT.toFixed(0)}s</text>

      <!-- Data Curves -->
      ${svgPaths}
    </svg>
  `;

  container.innerHTML = svgContent;
}

function resetUI() {
  const streamImg = document.getElementById("mjpeg-stream");
  if (streamImg) streamImg.src = "/api/stream/idle";

  const startBtn = document.getElementById("btn-start");
  const stopBtn = document.getElementById("btn-stop");
  if (startBtn) startBtn.disabled = false;
  if (stopBtn) stopBtn.disabled = true;
}
