/**
 * SANKET Modern React 18 Dashboard Application.
 * Full component architecture with real-time state management.
 */

const { useState, useEffect, useRef, useCallback, useMemo } = React;

// Main App Root Component
function App() {
  const [session, setSession] = useState(null);
  const [seats, setSeats] = useState([]);
  const [events, setEvents] = useState([]);
  const [timeline, setTimeline] = useState({ timestamps: [], seats: {} });
  const [deviceInfo, setDeviceInfo] = useState("CPU");
  const [selectedSeatId, setSelectedSeatId] = useState(null);
  const [activeTab, setActiveTab] = useState("all"); // "all" | "critical"
  const [activeClipUrl, setActiveClipUrl] = useState(null);
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [prevScores, setPrevScores] = useState({});

  const lastEventIdRef = useRef(null);
  const pollTimerRef = useRef(null);
  const timelineTimerRef = useRef(null);

  // Initial health check & active sessions scan
  useEffect(() => {
    fetchHealth();
    checkExistingSession();
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

  const checkExistingSession = async () => {
    try {
      const res = await fetch("/api/sessions");
      if (res.ok) {
        const sessions = await res.json();
        const running = sessions.find((s) => s.state === "running");
        if (running) {
          startPolling(running.session_id);
        }
      }
    } catch (e) {
      console.warn("Session check error:", e);
    }
  };

  const startPolling = (sessionId) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (timelineTimerRef.current) clearInterval(timelineTimerRef.current);

    lastEventIdRef.current = null;
    setEvents([]);
    setPrevScores({});

    const pollData = async () => {
      try {
        // 1. Session Status
        const sRes = await fetch(`/api/sessions/${sessionId}`);
        if (sRes.ok) {
          const sData = await sRes.json();
          setSession(sData);
          if (sData.state === "done" || sData.state === "failed") {
            clearInterval(pollTimerRef.current);
          }
        }

        // 2. Seats State
        const seatsRes = await fetch(`/api/sessions/${sessionId}/seats`);
        if (seatsRes.ok) {
          const seatsData = await seatsRes.json();
          setSeats(seatsData);

          // Update pulse records
          setPrevScores((prev) => {
            const next = { ...prev };
            seatsData.forEach((st) => {
              next[st.seat_id] = st.score;
            });
            return next;
          });
        }

        // 3. Incremental Events
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
        console.warn("Polling error:", err);
      }
    };

    const pollTimelineData = async () => {
      try {
        const tRes = await fetch(`/api/sessions/${sessionId}/timeline`);
        if (tRes.ok) {
          const tData = await tRes.json();
          setTimeline(tData);
        }
      } catch (err) {
        console.warn("Timeline poll error:", err);
      }
    };

    pollData();
    pollTimelineData();

    pollTimerRef.current = setInterval(pollData, 500);
    timelineTimerRef.current = setInterval(pollTimelineData, 2000);
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
      setSession(newSess);
      startPolling(newSess.session_id);
    } catch (err) {
      alert(`Connection failed: ${err.message}`);
    }
  };

  const handleStop = async () => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (timelineTimerRef.current) clearInterval(timelineTimerRef.current);
    if (session) {
      try {
        await fetch(`/api/sessions/${session.session_id}/stop`, { method: "POST" });
      } catch (e) {}
    }
    setSession(null);
    setSelectedSeatId(null);
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

  return (
    <div className="app-container">
      {/* Top Header Bar */}
      <Header
        session={session}
        deviceInfo={deviceInfo}
        onStart={handleStart}
        onStop={handleStop}
        onOpenReport={() => setIsReportOpen(true)}
      />

      {/* Main Multi-Region Workspace */}
      <main className="main-workspace">
        {/* Left Region: Seating Map & Video */}
        <section className="left-grid">
          {/* Seating Arrangement */}
          <div className="glass-card">
            <div className="card-header">
              <span className="card-title">
                <span className="indicator-dot"></span>
                Candidate Desks Arrangement
              </span>
              {selectedSeatId && (
                <button
                  className="btn btn-secondary"
                  style={{ padding: "2px 8px", fontSize: "10px" }}
                  onClick={() => setSelectedSeatId(null)}
                >
                  Clear Filter ({selectedSeatId})
                </button>
              )}
            </div>
            <div className="card-body">
              <SeatArrangementGrid
                seats={seats}
                selectedSeatId={selectedSeatId}
                onSelectSeat={(sid) => setSelectedSeatId(sid === selectedSeatId ? null : sid)}
                prevScores={prevScores}
              />
            </div>
          </div>

          {/* Live Video Feed */}
          <div className="glass-card">
            <div className="card-header">
              <span className="card-title">
                <span className={`indicator-dot ${session ? "" : "alert"}`}></span>
                Annotated Video Stream
              </span>
              <span className="brand-pill mono" style={{ fontSize: "10px" }}>
                {session ? "MJPEG LIVE" : "IDLE"}
              </span>
            </div>
            <div className="video-stage">
              <img
                className="mjpeg-canvas"
                src={session ? `/api/stream/${session.session_id}` : "/api/stream/idle"}
                alt="Exam Hall Live Stream"
              />
              <div className="video-watermark mono">
                Zero Biometric Storage &middot; Privacy HUD Filter
              </div>
            </div>
          </div>
        </section>

        {/* Right Sidebar: Observation & Audit Feed */}
        <aside className="right-sidebar">
          <div className="feed-header">
            <span style={{ fontWeight: 800, fontSize: "13px", letterSpacing: "0.5px" }}>
              OBSERVATION AUDIT LOG
            </span>
            <span className="mono" style={{ fontSize: "11px", color: "var(--text-dim)" }}>
              {filteredEvents.length} Events
            </span>
          </div>

          <div className="feed-tabs">
            <button
              className={`feed-tab ${activeTab === "all" ? "active" : ""}`}
              onClick={() => setActiveTab("all")}
            >
              All Observations
            </button>
            <button
              className={`feed-tab ${activeTab === "critical" ? "active" : ""}`}
              onClick={() => setActiveTab("critical")}
            >
              Critical Alerts Only
            </button>
          </div>

          <div className="feed-list">
            <AlertFeed
              events={filteredEvents}
              onViewClip={(clipPath) => setActiveClipUrl(clipPath)}
            />
          </div>
        </aside>

        {/* Bottom Strip: Inline SVG Timeline */}
        <section className="bottom-timeline-strip">
          <div className="card-header" style={{ padding: "6px 16px" }}>
            <span className="card-title" style={{ fontSize: "11px" }}>
              Suspicion Score Progression (Continuous Decay &middot; Alert Threshold = 100)
            </span>
            <span className="mono" style={{ fontSize: "10px", color: "var(--status-alert)" }}>
              D = 1.5 pts/s
            </span>
          </div>
          <div className="timeline-svg-wrapper">
            <TimelineChart timeline={timeline} selectedSeatId={selectedSeatId} />
          </div>
        </section>
      </main>

      {/* Evidence Clip Modal */}
      {activeClipUrl && (
        <ClipModal clipUrl={activeClipUrl} onClose={() => setActiveClipUrl(null)} />
      )}

      {/* Full Report Modal */}
      {isReportOpen && session && (
        <ReportModal session={session} onClose={() => setIsReportOpen(false)} />
      )}
    </div>
  );
}

// Header Component
function Header({ session, deviceInfo, onStart, onStop, onOpenReport }) {
  const [selectedSource, setSelectedSource] = useState(
    "DRISHTI AI DEXIT GLobal Datasets/01.Candidate was found using a mobile phone in the examination hall..mkv"
  );
  const [rtspUrl, setRtspUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const handleStartClick = () => {
    const src = rtspUrl.trim() ? rtspUrl.trim() : selectedSource;
    if (!src) {
      alert("Please select or enter a video source.");
      return;
    }
    onStart(src);
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

  const formatTimer = (seconds) => {
    if (!seconds) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo">
          <div className="logo-icon">S</div>
          <div>
            <div className="brand-name">SANKET</div>
          </div>
        </div>
        <div className="brand-pill">Invigilator Desk</div>
      </div>

      {/* Video Source Controls */}
      <div className="controls-bar">
        <select
          className="control-select mono"
          value={selectedSource}
          onChange={(e) => setSelectedSource(e.target.value)}
          disabled={session && session.state === "running"}
        >
          <option value="DRISHTI AI DEXIT GLobal Datasets/01.Candidate was found using a mobile phone in the examination hall..mkv">
            Dataset 01: Mobile Phone Footage
          </option>
          <option value="DRISHTI AI DEXIT GLobal Datasets/02.Candidates were found involved in conversation by turning back in the examination hall.mkv">
            Dataset 02: Turning Back Footage
          </option>
          <option value="DRISHTI AI DEXIT GLobal Datasets/03.Candidates were found passing chits in the examination hall..mkv">
            Dataset 03: Passing Chits Footage
          </option>
          <option value="DRISHTI AI DEXIT GLobal Datasets/04.Candidate was found peeping in others paper.mkv">
            Dataset 04: Peeping in Others Paper
          </option>
          <option value="DRISHTI AI DEXIT GLobal Datasets/05.Candidates were found discussing and sharing answers in the examination hall..mkv">
            Dataset 05: Discussing & Sharing
          </option>
          <option value="DRISHTI AI DEXIT GLobal Datasets/06.Candidate was found in sitting position (1).mkv">
            Dataset 06: Normal Seating Footage
          </option>
          <option value="0">Live Webcam (Camera 0)</option>
        </select>

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="video/*"
          style={{ display: "none" }}
        />
        <button
          className="btn btn-secondary"
          onClick={() => fileInputRef.current.click()}
          disabled={uploading || (session && session.state === "running")}
        >
          {uploading ? "Uploading..." : "Upload Video"}
        </button>

        {session && session.state === "running" ? (
          <button className="btn btn-danger" onClick={onStop}>
            Stop Monitoring
          </button>
        ) : (
          <button className="btn btn-primary" onClick={handleStartClick}>
            Start Monitoring
          </button>
        )}

        {session && (
          <button className="btn btn-secondary" onClick={onOpenReport}>
            Audit Report
          </button>
        )}
      </div>

      {/* Telemetry Metrics */}
      <div className="metrics-panel">
        <div className="stat-item">
          <span className="stat-label">Device</span>
          <span className="stat-value mono">{deviceInfo}</span>
        </div>
        <div className="stat-item">
          <span className="stat-label">FPS</span>
          <span className="stat-value mono">
            {session ? session.fps_processing.toFixed(1) : "0.0"}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Processed</span>
          <span className="stat-value mono">
            {session ? session.frames_processed : "0"}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Desks</span>
          <span className="stat-value mono">
            {session ? session.seats_tracked : "0"}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Critical</span>
          <span className="stat-value mono stat-alert">
            {session ? session.alerts_total : "0"}
          </span>
        </div>
        <div className="stat-item">
          <span className="stat-label">Duration</span>
          <span className="stat-value mono">
            {formatTimer(session ? session.duration_s : 0)}
          </span>
        </div>
      </div>
    </header>
  );
}

// Seating Grid Component
function SeatArrangementGrid({ seats, selectedSeatId, onSelectSeat, prevScores }) {
  if (!seats || seats.length === 0) {
    return (
      <div className="empty-placeholder">
        <span>No active candidate seats discovered yet.</span>
        <span style={{ fontSize: "11px" }}>Select a recording and click Start Monitoring.</span>
      </div>
    );
  }

  const sortedSeats = [...seats].sort((a, b) => {
    if (a.grid_row !== b.grid_row) return a.grid_row - b.grid_row;
    return a.grid_col - b.grid_col;
  });

  return (
    <div className="seat-arrangement-grid">
      {sortedSeats.map((seat) => {
        const isPulse = (prevScores[seat.seat_id] || 0) < 100 && seat.score >= 100;
        const isSelected = selectedSeatId === seat.seat_id;

        let statusCls = seat.status;
        if (!seat.calibrated) statusCls += " calibrating";
        if (isSelected) statusCls += " selected";
        if (isPulse) statusCls += " pulse";

        return (
          <div
            key={seat.seat_id}
            className={`seat-tile ${statusCls}`}
            onClick={() => onSelectSeat(seat.seat_id)}
          >
            <div className="seat-tile-header">
              <span className="seat-tile-id mono">
                {seat.seat_id}
                {!seat.calibrated && (
                  <span style={{ fontSize: "9px", color: "var(--status-accum)", marginLeft: "4px" }}>
                    [CALIB]
                  </span>
                )}
              </span>
              <span className="seat-tile-score mono">{seat.score.toFixed(1)}</span>
            </div>

            {seat.sustained_seconds > 0 && (
              <div className="seat-tile-sustained mono">
                Alert: {seat.sustained_seconds.toFixed(1)}s
              </div>
            )}

            <div className="seat-tile-reason" title={seat.last_reason || "Normal observation"}>
              {seat.last_reason || "Normal observation"}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Alert Feed Component
function AlertFeed({ events, onViewClip }) {
  if (!events || events.length === 0) {
    return (
      <div className="empty-placeholder">
        <span>No observation events recorded.</span>
      </div>
    );
  }

  return events.map((ev) => (
    <div key={ev.event_id} className={`event-card ${ev.severity}`}>
      <div className="event-top-row">
        <span className="event-seat-badge mono">{ev.seat_id}</span>
        <span className="event-timestamp mono">
          {ev.t_start.toFixed(1)}s &ndash; {ev.t_end.toFixed(1)}s
        </span>
      </div>
      <div className="event-rule-title">
        {ev.rule} (+{ev.points.toFixed(0)} pts)
      </div>
      <div className="event-reason-body">{ev.reason}</div>
      {ev.clip_path && (
        <button className="clip-badge-link" onClick={() => onViewClip(ev.clip_path)}>
          &#9654; View Evidence Clip
        </button>
      )}
    </div>
  ));
}

// Timeline Chart Component
function TimelineChart({ timeline, selectedSeatId }) {
  const containerRef = useRef(null);

  if (!timeline || !timeline.timestamps || timeline.timestamps.length === 0) {
    return (
      <div className="empty-placeholder" style={{ height: "100%" }}>
        <span>Timeline score curves accumulating...</span>
      </div>
    );
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

  return (
    <svg className="timeline-svg" viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "100%" }}>
      {/* 100 Alert Threshold Line */}
      <line
        x1={padding.left}
        y1={threshY}
        x2={width - padding.right}
        y2={threshY}
        stroke="#ef4444"
        strokeDasharray="4,4"
        strokeWidth="1.5"
      />
      <text
        x={width - padding.right + 4}
        y={threshY + 3}
        fill="#ef4444"
        fontSize="9"
        fontFamily="monospace"
        fontWeight="bold"
      >
        100
      </text>

      {/* Axis Lines */}
      <line
        x1={padding.left}
        y1={padding.top}
        x2={padding.left}
        y2={height - padding.bottom}
        stroke="#334155"
        strokeWidth="1"
      />
      <line
        x1={padding.left}
        y1={height - padding.bottom}
        x2={width - padding.right}
        y2={height - padding.bottom}
        stroke="#334155"
        strokeWidth="1"
      />

      {/* Y-Axis Labels */}
      <text x={padding.left - 6} y={scaleY(0) + 3} fill="#64748b" fontSize="9" textAnchor="end" fontFamily="monospace">0</text>
      <text x={padding.left - 6} y={scaleY(50) + 3} fill="#64748b" fontSize="9" textAnchor="end" fontFamily="monospace">50</text>
      <text x={padding.left - 6} y={scaleY(100) + 3} fill="#ef4444" fontSize="9" textAnchor="end" fontFamily="monospace">100</text>

      {/* X-Axis Labels */}
      <text x={scaleX(minT)} y={height - 6} fill="#64748b" fontSize="9" fontFamily="monospace">{minT.toFixed(0)}s</text>
      <text x={scaleX(maxT)} y={height - 6} fill="#64748b" fontSize="9" fontFamily="monospace" textAnchor="end">{maxT.toFixed(0)}s</text>

      {/* Dynamic Multi-Series Curves */}
      {seatIds.map((sid, idx) => {
        if (selectedSeatId && selectedSeatId !== sid) return null;
        const pts = timeline.seats[sid];
        if (!pts || pts.length === 0) return null;

        const col = seatColors[idx % seatColors.length];
        const pathD = pts
          .map((p, i) => `${i === 0 ? "M" : "L"} ${scaleX(p.t).toFixed(1)} ${scaleY(p.score).toFixed(1)}`)
          .join(" ");

        return (
          <path
            key={sid}
            d={pathD}
            fill="none"
            stroke={col}
            strokeWidth={selectedSeatId === sid ? "2.5" : "1.8"}
            opacity={selectedSeatId === sid ? "1" : "0.85"}
          />
        );
      })}
    </svg>
  );
}

// Clip Player Modal
function ClipModal({ clipUrl, onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span style={{ fontWeight: 800, fontSize: "13px" }}>EVIDENCE CLIP INSPECTION</span>
          <button className="btn btn-secondary" style={{ padding: "2px 8px" }} onClick={onClose}>
            Close
          </button>
        </div>
        <div className="modal-body" style={{ background: "#000", padding: "0" }}>
          <video src={clipUrl} controls autoPlay style={{ width: "100%", maxHeight: "60vh" }} />
        </div>
      </div>
    </div>
  );
}

// Audit Report Modal
function ReportModal({ session, onClose }) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-dialog" style={{ maxWidth: "900px", width: "95%" }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span style={{ fontWeight: 800, fontSize: "13px" }}>
            INVIGILATION SESSION REPORT &middot; {session.session_id}
          </span>
          <div style={{ display: "flex", gap: "8px" }}>
            <a
              className="btn btn-primary"
              style={{ fontSize: "11px", padding: "4px 10px", textDecoration: "none" }}
              href={`/api/sessions/${session.session_id}/report.csv`}
              download
            >
              Export CSV
            </a>
            <button className="btn btn-secondary" style={{ padding: "2px 8px" }} onClick={onClose}>
              Close
            </button>
          </div>
        </div>
        <div className="modal-body" style={{ padding: "0", height: "70vh" }}>
          <iframe
            src={`/api/sessions/${session.session_id}/report.html`}
            style={{ width: "100%", height: "100%", border: "none" }}
            title="Session Report"
          />
        </div>
      </div>
    </div>
  );
}

// Mount React Root
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
