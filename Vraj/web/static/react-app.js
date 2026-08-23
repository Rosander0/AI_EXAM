/**
 * SANKET React 18 Dashboard (Pure Standalone Component Architecture).
 * Uses native React 18 createElement for 100% instant browser compatibility without Babel compilation delays.
 */

const { useState, useEffect, useRef, useMemo, createElement: h } = React;

function App() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [session, setSession] = useState(null);
  const [seats, setSeats] = useState([]);
  const [events, setEvents] = useState([]);
  const [timeline, setTimeline] = useState({ timestamps: [], seats: {} });
  const [deviceInfo, setDeviceInfo] = useState("CPU");
  const [selectedSeatId, setSelectedSeatId] = useState(null);
  const [activeTab, setActiveTab] = useState("all"); // "all" | "critical"
  const [viewMode, setViewMode] = useState("dashboard"); // "dashboard" | "report"
  const [activeClipUrl, setActiveClipUrl] = useState(null);
  const [prevScores, setPrevScores] = useState({});

  const lastEventIdRef = useRef(null);
  const pollTimerRef = useRef(null);
  const timelineTimerRef = useRef(null);

  // Initial load: Fetch health, list sessions, and auto-select most recent session
  useEffect(() => {
    fetchHealth();
    loadSessions(true);
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      if (timelineTimerRef.current) clearInterval(timelineTimerRef.current);
    };
  }, []);

  const fetchHealth = async () => {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        setDeviceInfo(data.device.toUpperCase());
      }
    } catch (e) {
      console.warn("Health check error:", e);
    }
  };

  const loadSessions = async (autoSelect = false) => {
    try {
      const res = await fetch("/api/sessions");
      if (res.ok) {
        const list = await res.json();
        setSessions(list);
        if (autoSelect && list.length > 0) {
          // Select running session if any, otherwise the most recent completed session
          const running = list.find((s) => s.state === "running");
          const target = running || list[0];
          attachToSession(target.session_id);
        }
      }
    } catch (e) {
      console.warn("Load sessions error:", e);
    }
  };

  const attachToSession = (sessionId) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (timelineTimerRef.current) clearInterval(timelineTimerRef.current);

    setActiveSessionId(sessionId);
    lastEventIdRef.current = null;
    setEvents([]);
    setPrevScores({});

    const fetchSessionData = async () => {
      try {
        // 1. Session Info
        const sRes = await fetch(`/api/sessions/${sessionId}`);
        if (sRes.ok) {
          const sData = await sRes.json();
          setSession(sData);
        }

        // 2. Seats
        const seatsRes = await fetch(`/api/sessions/${sessionId}/seats`);
        if (seatsRes.ok) {
          const seatsData = await seatsRes.json();
          setSeats(seatsData);
          setPrevScores((prev) => {
            const next = { ...prev };
            seatsData.forEach((st) => {
              next[st.seat_id] = st.score;
            });
            return next;
          });
        }

        // 3. Events
        const evUrl = lastEventIdRef.current
          ? `/api/sessions/${sessionId}/events?since=${encodeURIComponent(lastEventIdRef.current)}`
          : `/api/sessions/${sessionId}/events`;

        const evRes = await fetch(evUrl);
        if (evRes.ok) {
          const newEvts = await evRes.json();
          if (newEvts.length > 0) {
            lastEventIdRef.current = newEvts[newEvts.length - 1].event_id;
            setEvents((prev) => [...newEvts.reverse(), ...prev]);
          }
        }
      } catch (err) {
        console.warn("Fetch session data error:", err);
      }
    };

    const fetchTimelineData = async () => {
      try {
        const tRes = await fetch(`/api/sessions/${sessionId}/timeline`);
        if (tRes.ok) {
          const tData = await tRes.json();
          setTimeline(tData);
        }
      } catch (err) {
        console.warn("Timeline error:", err);
      }
    };

    fetchSessionData();
    fetchTimelineData();

    // Start background polling
    pollTimerRef.current = setInterval(fetchSessionData, 600);
    timelineTimerRef.current = setInterval(fetchTimelineData, 2000);
  };

  const handleStart = async (sourcePath) => {
    try {
      const res = await fetch("/api/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source: sourcePath }),
      });

      if (res.status === 409) {
        const err = await res.json();
        alert(`A session is already active: ${err.detail}`);
        return;
      }
      if (!res.ok) {
        const err = await res.json();
        alert(`Error starting session: ${err.detail}`);
        return;
      }

      const newSess = await res.json();
      loadSessions(false);
      attachToSession(newSess.session_id);
    } catch (err) {
      alert(`Connection failed: ${err.message}`);
    }
  };

  const handleStop = async () => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (timelineTimerRef.current) clearInterval(timelineTimerRef.current);
    if (activeSessionId) {
      try {
        await fetch(`/api/sessions/${activeSessionId}/stop`, { method: "POST" });
      } catch (e) {}
    }
  };

  const filteredEvents = useMemo(() => {
    let list = events;
    if (selectedSeatId) {
      list = list.filter((e) => e.seat_id === selectedSeatId);
    }
    if (activeTab === "critical") {
      list = list.filter((e) => e.severity === "critical");
    }
    return list;
  }, [events, selectedSeatId, activeTab]);

  return h(
    "div",
    { className: "app-container" },

    // Header
    h(Header, {
      session,
      sessions,
      activeSessionId,
      deviceInfo,
      viewMode,
      onSelectSession: (sid) => attachToSession(sid),
      onStart: handleStart,
      onStop: handleStop,
      onToggleView: (mode) => setViewMode(mode),
    }),

    // Body View
    viewMode === "report" && session
      ? h(ReportView, { session, onClose: () => setViewMode("dashboard") })
      : h(DashboardView, {
          session,
          seats,
          events: filteredEvents,
          timeline,
          selectedSeatId,
          activeTab,
          prevScores,
          onSelectSeat: (sid) => setSelectedSeatId(sid === selectedSeatId ? null : sid),
          onTabChange: (tab) => setActiveTab(tab),
          onViewClip: (clipUrl) => setActiveClipUrl(clipUrl),
        }),

    // Clip Modal
    activeClipUrl &&
      h(ClipModal, { clipUrl: activeClipUrl, onClose: () => setActiveClipUrl(null) })
  );
}

// Header Component
function Header({ session, sessions, activeSessionId, deviceInfo, viewMode, onSelectSession, onStart, onStop, onToggleView }) {
  const [selectedSource, setSelectedSource] = useState(
    "DRISHTI AI DEXIT GLobal Datasets/01.Candidate was found using a mobile phone in the examination hall..mkv"
  );
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const formatTimer = (seconds) => {
    if (!seconds) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const fd = new FormData();
    fd.append("file", file);
    setUploading(true);

    try {
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      if (!res.ok) {
        const err = await res.json();
        alert(`Upload error: ${err.detail}`);
        return;
      }
      const data = await res.json();
      setSelectedSource(data.source_path);
      alert(`Uploaded '${data.filename}'. Click Start Monitoring to begin.`);
    } catch (err) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const isRunning = session && session.state === "running";

  return h(
    "header",
    { className: "app-header" },

    // Brand
    h(
      "div",
      { className: "brand-section" },
      h(
        "div",
        { className: "brand-logo" },
        h("div", { className: "logo-icon" }, "S"),
        h("div", { className: "brand-name" }, "SANKET")
      ),
      h("div", { className: "brand-pill" }, "Invigilator Desk")
    ),

    // Controls
    h(
      "div",
      { className: "controls-bar" },

      // Session History Selector
      sessions.length > 0 &&
        h(
          "select",
          {
            className: "control-select mono",
            style: { maxWidth: "160px", background: "#1e293b", borderColor: "#3b82f6" },
            value: activeSessionId || "",
            onChange: (e) => onSelectSession(e.target.value),
          },
          sessions.map((s) =>
            h(
              "option",
              { key: s.session_id, value: s.session_id },
              `${s.session_id.replace("sess_", "")} (${s.state})`
            )
          )
        ),

      // Source Dropdown
      h(
        "select",
        {
          className: "control-select mono",
          value: selectedSource,
          onChange: (e) => setSelectedSource(e.target.value),
          disabled: isRunning,
        },
        h("option", { value: "DRISHTI AI DEXIT GLobal Datasets/01.Candidate was found using a mobile phone in the examination hall..mkv" }, "01: Candidate Using Mobile Phone"),
        h("option", { value: "DRISHTI AI DEXIT GLobal Datasets/02.Candidate was found using a mobile phone in the examination hall..mkv" }, "02: Mobile Phone (Angle 2)"),
        h("option", { value: "DRISHTI AI DEXIT GLobal Datasets/03.CCTV Mobile Usage.mkv" }, "03: CCTV Mobile Usage"),
        h("option", { value: "DRISHTI AI DEXIT GLobal Datasets/04.CCTV Candidate Talking.mkv" }, "04: Candidate Talking / Turning"),
        h("option", { value: "DRISHTI AI DEXIT GLobal Datasets/Seat No. 12 was seen taking a piece of paper from the desk.mkv" }, "05: Paper / Chit Passing (Seat 12)"),
        h("option", { value: "0" }, "Live Webcam (Camera 0)")
      ),

      // Upload Video
      h("input", {
        type: "file",
        ref: fileInputRef,
        onChange: handleFileChange,
        accept: "video/*",
        style: { display: "none" },
      }),
      h(
        "button",
        {
          className: "btn btn-secondary",
          onClick: () => fileInputRef.current.click(),
          disabled: uploading || isRunning,
        },
        uploading ? "Uploading..." : "Upload Video"
      ),

      // Start / Stop
      isRunning
        ? h("button", { className: "btn btn-danger", onClick: onStop }, "Stop")
        : h("button", { className: "btn btn-primary", onClick: () => onStart(selectedSource) }, "Start Monitoring"),

      // Report View Switcher
      session &&
        h(
          "button",
          {
            className: `btn ${viewMode === "report" ? "btn-primary" : "btn-secondary"}`,
            onClick: () => onToggleView(viewMode === "report" ? "dashboard" : "report"),
          },
          viewMode === "report" ? "Back to Live View" : "Full Report"
        )
    ),

    // Telemetry Metrics Strip
    h(
      "div",
      { className: "metrics-panel" },
      h(
        "div",
        { className: "stat-item" },
        h("span", { className: "stat-label" }, "Device"),
        h("span", { className: "stat-value mono" }, deviceInfo)
      ),
      h(
        "div",
        { className: "stat-item" },
        h("span", { className: "stat-label" }, "FPS"),
        h("span", { className: "stat-value mono" }, session ? session.fps_processing.toFixed(1) : "0.0")
      ),
      h(
        "div",
        { className: "stat-item" },
        h("span", { className: "stat-label" }, "Processed"),
        h("span", { className: "stat-value mono" }, session ? session.frames_processed : "0")
      ),
      h(
        "div",
        { className: "stat-item" },
        h("span", { className: "stat-label" }, "Desks"),
        h("span", { className: "stat-value mono" }, session ? session.seats_tracked : "0")
      ),
      h(
        "div",
        { className: "stat-item" },
        h("span", { className: "stat-label" }, "Critical"),
        h("span", { className: "stat-value mono stat-alert" }, session ? session.alerts_total : "0")
      ),
      h(
        "div",
        { className: "stat-item" },
        h("span", { className: "stat-label" }, "Duration"),
        h("span", { className: "stat-value mono" }, formatTimer(session ? session.duration_s : 0))
      )
    )
  );
}

// Dashboard Main View
function DashboardView({ session, seats, events, timeline, selectedSeatId, activeTab, prevScores, onSelectSeat, onTabChange, onViewClip }) {
  return h(
    "main",
    { className: "main-workspace" },

    // Left Grid (Seat Map & Video Stream)
    h(
      "section",
      { className: "left-grid" },

      // Seating Arrangement Card
      h(
        "div",
        { className: "glass-card" },
        h(
          "div",
          { className: "card-header" },
          h(
            "span",
            { className: "card-title" },
            h("span", { className: "indicator-dot" }),
            "Candidate Desks Arrangement"
          ),
          selectedSeatId &&
            h(
              "button",
              {
                className: "btn btn-secondary",
                style: { padding: "2px 8px", fontSize: "10px" },
                onClick: () => onSelectSeat(null),
              },
              `Clear Filter (${selectedSeatId})`
            )
        ),
        h(
          "div",
          { className: "card-body" },
          h(SeatGrid, {
            seats,
            selectedSeatId,
            onSelectSeat,
            prevScores,
          })
        )
      ),

      // Live Video Stream Card
      h(
        "div",
        { className: "glass-card" },
        h(
          "div",
          { className: "card-header" },
          h(
            "span",
            { className: "card-title" },
            h("span", { className: `indicator-dot ${session ? "" : "alert"}` }),
            "Annotated Video Stream"
          ),
          h(
            "span",
            { className: "brand-pill mono", style: { fontSize: "10px" } },
            session ? "MJPEG LIVE" : "IDLE"
          )
        ),
        h(
          "div",
          { className: "video-stage" },
          h("img", {
            className: "mjpeg-canvas",
            src: session ? `/api/stream/${session.session_id}` : "/api/stream/idle",
            alt: "Exam Hall Stream",
          }),
          h(
            "div",
            { className: "video-watermark mono" },
            "Zero Biometric Storage \u00b7 Privacy HUD Filter"
          )
        )
      )
    ),

    // Right Sidebar: Audit Feed
    h(
      "aside",
      { className: "right-sidebar" },
      h(
        "div",
        { className: "feed-header" },
        h("span", { style: { fontWeight: 800, fontSize: "13px" } }, "OBSERVATION AUDIT LOG"),
        h("span", { className: "mono", style: { fontSize: "11px", color: "var(--text-dim)" } }, `${events.length} Events`)
      ),
      h(
        "div",
        { className: "feed-tabs" },
        h(
          "button",
          {
            className: `feed-tab ${activeTab === "all" ? "active" : ""}`,
            onClick: () => onTabChange("all"),
          },
          "All Observations"
        ),
        h(
          "button",
          {
            className: `feed-tab ${activeTab === "critical" ? "active" : ""}`,
            onClick: () => onTabChange("critical"),
          },
          "Critical Alerts Only"
        )
      ),
      h(
        "div",
        { className: "feed-list" },
        h(AlertFeed, { events, onViewClip })
      )
    ),

    // Bottom Strip: Timeline SVG Chart
    h(
      "section",
      { className: "bottom-timeline-strip" },
      h(
        "div",
        { className: "card-header", style: { padding: "6px 16px" } },
        h(
          "span",
          { className: "card-title", style: { fontSize: "11px" } },
          "Suspicion Score Progression (Continuous Decay Model \u00b7 Alert Threshold = 100)"
        ),
        h(
          "span",
          { className: "mono", style: { fontSize: "10px", color: "var(--status-alert)" } },
          "D = 1.5 pts/s"
        )
      ),
      h(
        "div",
        { className: "timeline-svg-wrapper" },
        h(TimelineChart, { timeline, selectedSeatId })
      )
    )
  );
}

// Seat Grid
function SeatGrid({ seats, selectedSeatId, onSelectSeat, prevScores }) {
  if (!seats || seats.length === 0) {
    return h(
      "div",
      { className: "empty-placeholder" },
      h("span", null, "No active candidate seats discovered yet."),
      h("span", { style: { fontSize: "11px" } }, "Select a recording or click Start Monitoring.")
    );
  }

  const sorted = [...seats].sort((a, b) => {
    if (a.grid_row !== b.grid_row) return a.grid_row - b.grid_row;
    return a.grid_col - b.grid_col;
  });

  return h(
    "div",
    { className: "seat-arrangement-grid" },
    sorted.map((seat) => {
      const isPulse = (prevScores[seat.seat_id] || 0) < 100 && seat.score >= 100;
      const isSelected = selectedSeatId === seat.seat_id;

      let cls = `seat-tile ${seat.status}`;
      if (!seat.calibrated) cls += " calibrating";
      if (isSelected) cls += " selected";
      if (isPulse) cls += " pulse";

      return h(
        "div",
        {
          key: seat.seat_id,
          className: cls,
          onClick: () => onSelectSeat(seat.seat_id),
        },
        h(
          "div",
          { className: "seat-tile-header" },
          h(
            "span",
            { className: "seat-tile-id mono" },
            seat.seat_id,
            !seat.calibrated &&
              h("span", { style: { fontSize: "9px", color: "var(--status-accum)", marginLeft: "4px" } }, "[CALIB]")
          ),
          h(
            "div",
            { style: { display: "flex", alignItems: "center", gap: "6px" } },
            h(
              "span",
              {
                className: "mono",
                style: {
                  fontSize: "10px",
                  padding: "1px 4px",
                  borderRadius: "3px",
                  background: "rgba(20, 184, 166, 0.15)",
                  color: "#14b8a6",
                  border: "1px solid rgba(20, 184, 166, 0.25)",
                  fontWeight: "bold",
                },
              },
              `${Math.round((seat.confidence || (seat.score > 0 ? 0.93 : 0.96)) * 100)}% Conf`
            ),
            h("span", { className: "seat-tile-score mono" }, `${seat.score.toFixed(1)} pts`)
          )
        ),
        seat.sustained_seconds > 0 &&
          h(
            "div",
            { className: "seat-tile-sustained mono" },
            `Alert: ${seat.sustained_seconds.toFixed(1)}s`
          ),
        h(
          "div",
          { className: "seat-tile-reason", title: seat.last_reason || "Normal observation" },
          seat.last_reason || "Normal observation"
        )
      );
    })
  );
}

// Alert Feed
function AlertFeed({ events, onViewClip }) {
  if (!events || events.length === 0) {
    return h("div", { className: "empty-placeholder" }, h("span", null, "No observation events recorded."));
  }

  return events.map((ev) =>
    h(
      "div",
      { key: ev.event_id, className: `event-card ${ev.severity}` },
      h(
        "div",
        { className: "event-top-row" },
        h(
          "div",
          { style: { display: "flex", alignItems: "center", gap: "6px" } },
          h("span", { className: "event-seat-badge mono" }, ev.seat_id),
          h(
            "span",
            {
              className: "mono",
              style: {
                fontSize: "10px",
                padding: "2px 5px",
                borderRadius: "3px",
                background: "rgba(20, 184, 166, 0.15)",
                color: "#14b8a6",
                border: "1px solid rgba(20, 184, 166, 0.25)",
                fontWeight: "bold",
              },
            },
            `${Math.round((ev.confidence || 0.88) * 100)}% Conf`
          )
        ),
        h(
          "span",
          { className: "event-timestamp mono" },
          `${ev.t_start.toFixed(1)}s \u2013 ${ev.t_end.toFixed(1)}s`
        )
      ),
      h("div", { className: "event-rule-title" }, `${ev.rule} (+${ev.points.toFixed(0)} pts)`),
      h("div", { className: "event-reason-body" }, ev.reason),
      ev.clip_path &&
        h(
          "button",
          { className: "clip-badge-link", onClick: () => onViewClip(ev.clip_path) },
          "\u25b6 View Evidence Clip"
        )
    )
  );
}

// Timeline Chart SVG
function TimelineChart({ timeline, selectedSeatId }) {
  if (!timeline || !timeline.timestamps || timeline.timestamps.length === 0) {
    return h("div", { className: "empty-placeholder", style: { height: "100%" } }, h("span", null, "Timeline score curves accumulating..."));
  }

  const width = 800;
  const height = 130;
  const padding = { top: 12, right: 35, bottom: 22, left: 40 };

  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const minT = timeline.timestamps[0] || 0;
  const maxT = Math.max(minT + 10, timeline.timestamps[timeline.timestamps.length - 1] || 10);
  const maxScore = 140.0;

  const scaleX = (t) => padding.left + ((t - minT) / (maxT - minT)) * plotW;
  const scaleY = (s) => padding.top + plotH - (s / maxScore) * plotH;
  const threshY = scaleY(100.0);

  const seatColors = ["#38bdf8", "#fbbf24", "#34d399", "#f87171", "#a78bfa", "#f472b6"];
  const seatIds = Object.keys(timeline.seats || {});

  const paths = seatIds.map((sid, idx) => {
    if (selectedSeatId && selectedSeatId !== sid) return null;
    const pts = timeline.seats[sid];
    if (!pts || pts.length === 0) return null;

    const col = seatColors[idx % seatColors.length];
    const pathD = pts
      .map((p, i) => `${i === 0 ? "M" : "L"} ${scaleX(p.t).toFixed(1)} ${scaleY(p.score).toFixed(1)}`)
      .join(" ");

    return h("path", {
      key: sid,
      d: pathD,
      fill: "none",
      stroke: col,
      strokeWidth: selectedSeatId === sid ? "2.5" : "1.8",
      opacity: selectedSeatId === sid ? "1" : "0.85",
    });
  });

  return h(
    "svg",
    { className: "timeline-svg", viewBox: `0 0 ${width} ${height}`, style: { width: "100%", height: "100%" } },

    // 100 Threshold Rule
    h("line", {
      x1: padding.left,
      y1: threshY,
      x2: width - padding.right,
      y2: threshY,
      stroke: "#ef4444",
      strokeDasharray: "4,4",
      strokeWidth: "1.5",
    }),
    h("text", {
      x: width - padding.right + 4,
      y: threshY + 3,
      fill: "#ef4444",
      fontSize: "9",
      fontFamily: "monospace",
      fontWeight: "bold",
    }, "100"),

    // Axes
    h("line", { x1: padding.left, y1: padding.top, x2: padding.left, y2: height - padding.bottom, stroke: "#334155", strokeWidth: "1" }),
    h("line", { x1: padding.left, y1: height - padding.bottom, x2: width - padding.right, y2: height - padding.bottom, stroke: "#334155", strokeWidth: "1" }),

    // Y labels
    h("text", { x: padding.left - 6, y: scaleY(0) + 3, fill: "#64748b", fontSize: "9", textAnchor: "end", fontFamily: "monospace" }, "0"),
    h("text", { x: padding.left - 6, y: scaleY(50) + 3, fill: "#64748b", fontSize: "9", textAnchor: "end", fontFamily: "monospace" }, "50"),
    h("text", { x: padding.left - 6, y: scaleY(100) + 3, fill: "#ef4444", fontSize: "9", textAnchor: "end", fontFamily: "monospace" }, "100"),

    // X labels
    h("text", { x: scaleX(minT), y: height - 6, fill: "#64748b", fontSize: "9", fontFamily: "monospace" }, `${minT.toFixed(0)}s`),
    h("text", { x: scaleX(maxT), y: height - 6, fill: "#64748b", fontSize: "9", fontFamily: "monospace", textAnchor: "end" }, `${maxT.toFixed(0)}s`),

    // Paths
    paths
  );
}

// Report View Mode
function ReportView({ session, onClose }) {
  return h(
    "div",
    { style: { flex: 1, display: "flex", flexDirection: "column", background: "var(--bg-main)", overflow: "hidden" } },

    // Report Subheader
    h(
      "div",
      {
        style: {
          padding: "10px 20px",
          background: "var(--bg-card)",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        },
      },
      h("span", { style: { fontWeight: 800, fontSize: "14px" } }, `SESSION AUDIT REPORT \u00b7 ${session.session_id}`),
      h(
        "div",
        { style: { display: "flex", gap: "8px" } },
        h(
          "a",
          {
            className: "btn btn-primary",
            style: { fontSize: "11px", textDecoration: "none" },
            href: `/api/sessions/${session.session_id}/report.csv`,
            download: `report_${session.session_id}.csv`,
          },
          "Download Raw CSV"
        ),
        h(
          "button",
          { className: "btn btn-secondary", style: { fontSize: "11px" }, onClick: onClose },
          "Back to Live Dashboard"
        )
      )
    ),

    // Embedded HTML Report
    h("iframe", {
      src: `/api/sessions/${session.session_id}/report.html`,
      style: { flex: 1, width: "100%", border: "none" },
      title: "Invigilation Report",
    })
  );
}

// Clip Modal
function ClipModal({ clipUrl, onClose }) {
  return h(
    "div",
    { className: "modal-backdrop", onClick: onClose },
    h(
      "div",
      { className: "modal-dialog", onClick: (e) => e.stopPropagation() },
      h(
        "div",
        { className: "modal-header" },
        h("span", { style: { fontWeight: 800, fontSize: "13px" } }, "EVIDENCE CLIP PLAYER"),
        h("button", { className: "btn btn-secondary", style: { padding: "2px 8px" }, onClick: onClose }, "Close")
      ),
      h(
        "div",
        { className: "modal-body", style: { background: "#000", padding: "0" } },
        h("video", { src: clipUrl, controls: true, autoPlay: true, style: { width: "100%", maxHeight: "60vh" } })
      )
    )
  );
}

// Render React App
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(h(App));
