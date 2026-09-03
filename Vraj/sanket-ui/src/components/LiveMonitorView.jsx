import React, { useState } from 'react';
import {
  Radio, Flame, Maximize2, Activity, User, Eye,
  Clock, ChevronRight, Video, Zap, CheckCircle2,
  StopCircle, Search, ShieldAlert
} from 'lucide-react';

const RULE_BADGES = {
  hand_phone_grip: { label: 'Phone Grip (MediaPipe)', color: 'bg-orange-500/10 text-orange-500 border-orange-500/20', points: '+80' },
  object_phone: { label: 'Prohibited Device', color: 'bg-red-500/10 text-red-500 border-red-500/20', points: '+100' },
  head_turn: { label: 'Head Deviation', color: 'bg-amber-500/10 text-amber-500 border-amber-500/20', points: '+10' },
  turning_back: { label: 'Turning Back', color: 'bg-rose-500/10 text-rose-500 border-rose-500/20', points: '+35' },
  neighbour_reach: { label: 'Neighbor Reach', color: 'bg-amber-500/10 text-amber-500 border-amber-500/20', points: '+25' },
  hidden_hands: { label: 'Hidden Hands', color: 'bg-stone-500/10 text-stone-300 border-stone-500/20', points: '+15' },
  repeated_action: { label: 'Repeated Pattern', color: 'bg-stone-500/10 text-stone-300 border-stone-500/20', points: '+30' },
  hand_chit_pinch: { label: 'Chit Pinch', color: 'bg-orange-500/10 text-orange-500 border-orange-500/20', points: '+50' },
  object_chit: { label: 'Chit Item', color: 'bg-red-500/10 text-red-500 border-red-500/20', points: '+60' },
  object_unregistered: { label: 'Unregistered Item', color: 'bg-stone-500/10 text-stone-300 border-stone-500/20', points: '+20' }
};

export default function LiveMonitorView({
  session,
  seats,
  events,
  onSelectCandidate,
  onOpenClipModal,
  onStopSession,
  isHalting
}) {
  const [streamError, setStreamError] = useState(false);
  const [sidebarTab, setSidebarTab] = useState('threats'); // 'threats' | 'feed'
  const [searchQuery, setSearchQuery] = useState('');

  const isRunning = session?.state === 'running';

  const rankedSeats = [...seats].sort((a, b) => {
    if ((b.sustained_seconds || 0) !== (a.sustained_seconds || 0)) {
      return (b.sustained_seconds || 0) - (a.sustained_seconds || 0);
    }
    return (b.score || 0) - (a.score || 0);
  });

  const filteredSeats = rankedSeats.filter(s => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return s.seat_id.toLowerCase().includes(q) || (s.last_reason && s.last_reason.toLowerCase().includes(q));
  });

  const filteredEvents = events.filter(e => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return e.seat_id?.toLowerCase().includes(q) || e.reason?.toLowerCase().includes(q) || e.rule?.toLowerCase().includes(q);
  });

  const criticalCount = seats.filter(s => s.status === 'alert' || s.score >= 100).length;
  const accumulatingCount = seats.filter(s => s.status === 'accumulating' || (s.score >= 40 && s.score < 100)).length;
  const calmCount = seats.filter(s => s.status === 'calm' || s.score < 40).length;

  const toggleFullscreen = () => {
    const el = document.getElementById('sanket-video-frame');
    if (!el) return;
    if (!document.fullscreenElement) {
      el.requestFullscreen?.().catch(console.error);
    } else {
      document.exitFullscreen?.().catch(console.error);
    }
  };

  return (
    <div className="flex-1 flex flex-col xl:flex-row gap-4 p-0 min-h-0 overflow-hidden">

      {/* LEFT / MAIN: Stream Viewport + Compact Metrics */}
      <div className="flex-1 flex flex-col gap-4 min-h-0">

        {/* Ultra-compact Metric Ribbon */}
        <div className="flex gap-3 shrink-0 overflow-x-auto pb-1">
          
          <div className="flex-1 neu-flat px-4 py-2.5 flex items-center justify-between min-w-[140px]">
            <span className="text-[10px] text-[var(--text-muted)] font-bold uppercase tracking-wider">Desks</span>
            <span className="text-xl font-bold text-[var(--text-primary)] font-mono">{seats.length}</span>
          </div>

          <div className="flex-1 neu-flat px-4 py-2.5 flex items-center justify-between min-w-[140px]">
            <span className="text-[10px] text-red-500 font-bold uppercase tracking-wider">Disqualified</span>
            <span className="text-xl font-bold text-red-500 font-mono">{criticalCount}</span>
          </div>

          <div className="flex-1 neu-flat px-4 py-2.5 flex items-center justify-between min-w-[140px]">
            <span className="text-[10px] text-[var(--accent-amber)] font-bold uppercase tracking-wider">Accumulating</span>
            <span className="text-xl font-bold text-[var(--accent-amber)] font-mono">{accumulatingCount}</span>
          </div>

          <div className="flex-1 neu-flat px-4 py-2.5 flex items-center justify-between min-w-[140px]">
            <span className="text-[10px] text-[var(--accent-emerald)] font-bold uppercase tracking-wider">Calm</span>
            <span className="text-xl font-bold text-[var(--accent-emerald)] font-mono">{calmCount}</span>
          </div>

        </div>

        {/* Stream Viewport Container */}
        <div
          id="sanket-video-frame"
          className="relative neu-pressed rounded-3xl overflow-hidden flex-1 flex items-center justify-center group min-h-0"
        >
          {session ? (
            !streamError ? (
              <img
                src={`/api/stream/${session.session_id}`}
                alt="SANKET Surveillance Stream"
                className="w-full h-full object-contain mix-blend-overlay opacity-90"
                onError={() => setStreamError(true)}
              />
            ) : (
              <div className="flex flex-col items-center justify-center p-8 text-center">
                <Video className="w-10 h-10 text-[var(--text-muted)] mb-3" />
                <p className="text-[var(--text-primary)] font-bold text-sm">Feed Offline or Concluded</p>
                <p className="text-[var(--text-muted)] text-xs font-mono mt-1">
                  Session: {session.session_id} • Status: {session.state}
                </p>
                <button
                  onClick={() => setStreamError(false)}
                  className="mt-4 px-4 py-2 rounded-xl neu-convex text-[var(--text-primary)] text-xs font-bold transition-all active:neu-pressed"
                >
                  Reconnect
                </button>
              </div>
            )
          ) : (
            <div className="flex flex-col items-center justify-center text-center p-8">
              <div className="w-12 h-12 rounded-2xl neu-convex flex items-center justify-center mb-4 text-[var(--accent-amber)]">
                <Radio className="w-6 h-6 animate-pulse" />
              </div>
              <h3 className="text-base font-bold text-[var(--text-primary)]">No Active Session Selected</h3>
              <p className="text-[var(--text-secondary)] text-xs max-w-xs mt-2">
                Choose a session from the top bar or initialize a new feed.
              </p>
            </div>
          )}

          {/* Top Left Status Badge */}
          <div className="absolute top-5 left-5 flex items-center gap-2 z-10">
            {isRunning ? (
              <div className="flex items-center gap-2 px-4 py-2 rounded-xl neu-convex text-red-500 text-xs font-mono font-bold">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                <span>REC &bull; LIVE</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 px-4 py-2 rounded-xl neu-convex text-[var(--text-secondary)] text-xs font-mono font-bold">
                <span className="w-2 h-2 rounded-full bg-[var(--text-muted)]"></span>
                <span>CONCLUDED</span>
              </div>
            )}
          </div>

          {/* Top Right Controls */}
          <div className="absolute top-5 right-5 flex items-center gap-2 z-10">
            <button
              onClick={toggleFullscreen}
              title="Fullscreen"
              className="p-3 rounded-xl neu-convex text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all active:neu-pressed"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>

          {/* Bottom Telemetry Bar */}
          {session && (
            <div className="absolute bottom-5 left-5 right-5 z-10">
              <div className="neu-convex rounded-2xl px-5 py-3 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">

                <div className="flex items-center gap-5 text-[var(--text-secondary)] font-bold">
                  <div className="flex items-center gap-2">
                    <span className="text-[var(--text-muted)] text-[10px] uppercase">ID:</span>
                    <span className="text-[var(--text-primary)]">{session.session_id.replace('sess_', '')}</span>
                  </div>

                  <div className="hidden sm:flex items-center gap-2">
                    <span className="text-[var(--text-muted)] text-[10px] uppercase">Time:</span>
                    <span className="text-[var(--text-primary)]">
                      t = {session.duration_s ? `${session.duration_s.toFixed(1)}s` : '0.0s'}
                    </span>
                  </div>

                  <div className="hidden md:flex items-center gap-2">
                    <span className="text-[var(--text-muted)] text-[10px] uppercase">FPS:</span>
                    <span className="text-[var(--accent-emerald)]">
                      {session.fps_processing ? session.fps_processing.toFixed(1) : '--'}
                    </span>
                  </div>
                </div>

                {isRunning ? (
                  <button
                    onClick={onStopSession}
                    disabled={isHalting}
                    className="px-4 py-2 rounded-xl neu-convex text-red-500 hover:text-red-400 font-bold text-xs uppercase tracking-wider transition-all flex items-center gap-2 active:neu-pressed disabled:opacity-50"
                  >
                    <StopCircle className="w-4 h-4" />
                    {isHalting ? 'Halting...' : 'Halt Engine'}
                  </button>
                ) : (
                  <span className="text-[11px] text-[var(--text-secondary)] font-mono font-bold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-[var(--accent-emerald)]" />
                    Finalized
                  </span>
                )}

              </div>
            </div>
          )}
        </div>

        {/* Live Candidate Scoring Matrix */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3 overflow-y-auto pb-4">
          {seats.length === 0 ? (
            <div className="col-span-full neu-flat p-8 flex flex-col items-center justify-center text-[var(--text-muted)] text-xs font-mono rounded-2xl">
              Waiting for candidate telemetry...
            </div>
          ) : (
            rankedSeats.map(seat => {
              const isAlert = seat.status === 'alert' || seat.score >= 100;
              const isWarning = seat.status === 'accumulating' || (seat.score >= 40 && seat.score < 100);
              const scoreNum = Math.round(seat.score || 0);

              return (
                <div
                  key={seat.seat_id}
                  onClick={() => onSelectCandidate(seat)}
                  className={`neu-convex hover:neu-flat rounded-xl p-3 transition-all cursor-pointer relative flex flex-col justify-between min-h-[110px] ${
                    isAlert ? 'border border-red-500/30' : isWarning ? 'border border-amber-500/30' : 'border border-[var(--border-subtle)]'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <span className="text-xs font-bold text-[var(--text-primary)] truncate">{seat.seat_id}</span>
                    <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                      isAlert ? 'bg-red-500/10 text-red-500' : isWarning ? 'bg-amber-500/10 text-amber-500' : 'bg-emerald-500/10 text-emerald-500'
                    }`}>
                      {isAlert ? 'Alert' : isWarning ? 'Warn' : 'Calm'}
                    </span>
                  </div>
                  
                  <div className="flex flex-col items-center justify-center py-2">
                    <span className={`text-3xl font-mono font-bold tracking-tighter ${
                      isAlert ? 'text-red-500' : isWarning ? 'text-amber-500' : 'text-emerald-500'
                    }`}>
                      {scoreNum}%
                    </span>
                  </div>

                  <div className="w-full h-1.5 rounded-full bg-[var(--bg-surface)] overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        isAlert ? 'bg-red-500' : isWarning ? 'bg-amber-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${Math.min(100, Math.max(3, scoreNum))}%` }}
                    ></div>
                  </div>
                </div>
              );
            })
          )}
        </div>

      </div>

      {/* RIGHT SIDEBAR: Linear-style Inspector Panel */}
      <div className="w-full xl:w-[340px] flex flex-col saas-card p-5 min-h-0 shrink-0">

        {/* Search */}
        <div className="relative mb-3">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="Search candidate, behavior..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xl pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-orange-500 transition-colors"
          />
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center p-1 bg-[var(--bg-surface)] rounded-xl border border-[var(--border-subtle)] mb-4 shrink-0">
          <button
            onClick={() => setSidebarTab('threats')}
            className={`flex-1 py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-all ${sidebarTab === 'threats'
                ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm font-semibold'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
          >
            <Flame className="w-3.5 h-3.5 text-amber-500" />
            <span>Threat Ranking</span>
            <span className="text-[10px] font-mono text-[var(--text-muted)]">({filteredSeats.length})</span>
          </button>

          <button
            onClick={() => setSidebarTab('feed')}
            className={`flex-1 py-2 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-all ${sidebarTab === 'feed'
                ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm font-semibold'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
          >
            <Zap className="w-3.5 h-3.5 text-orange-500" />
            <span>Observations</span>
            <span className="text-[10px] font-mono text-[var(--text-muted)]">({filteredEvents.length})</span>
          </button>
        </div>

        {/* Tab 1: Threat Leaderboard */}
        {sidebarTab === 'threats' && (
          <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-0">
            {filteredSeats.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 text-[var(--text-muted)] text-xs font-mono">
                <Activity className="w-5 h-5 mb-2 text-[var(--text-muted)] animate-spin" />
                Scanning for candidates...
              </div>
            ) : (
              filteredSeats.map((seat, index) => {
                const isAlert = seat.status === 'alert' || seat.score >= 100;
                const isWarning = seat.status === 'accumulating' || (seat.score >= 40 && seat.score < 100);

                return (
                  <div
                    key={seat.seat_id}
                    onClick={() => onSelectCandidate(seat)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 group ${isAlert
                        ? 'bg-red-500/5 border-red-500/30 hover:border-red-500'
                        : isWarning
                          ? 'bg-amber-500/5 border-amber-500/25 hover:border-amber-500'
                          : 'bg-[var(--bg-surface)] border-[var(--border-subtle)] hover:border-[var(--border-medium)]'
                      }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className={`w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-mono font-bold shrink-0 ${index === 0 ? 'bg-red-500 text-white' : index === 1 ? 'bg-amber-500 text-white' : 'bg-[var(--bg-card)] text-[var(--text-secondary)] border border-[var(--border-subtle)]'
                        }`}>
                        #{index + 1}
                      </span>

                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-[var(--text-primary)] truncate">
                            {seat.seat_id}
                          </span>
                          {seat.calibrated && (
                            <span className="text-[8px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                              CALIB
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-[var(--text-muted)] font-mono truncate mt-0.5">
                          Sustained: <strong className={seat.sustained_seconds > 0 ? 'text-red-500' : 'text-[var(--text-secondary)]'}>{(seat.sustained_seconds || 0).toFixed(1)}s</strong>
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <div className="text-right">
                        <span className={`text-base font-bold font-mono tracking-tight block ${isAlert ? 'text-red-500' : isWarning ? 'text-amber-500' : 'text-emerald-500'
                          }`}>
                          {Math.round(seat.score || 0)}%
                        </span>
                      </div>
                      <ChevronRight className="w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition-colors" />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Tab 2: Live Activity Feed */}
        {sidebarTab === 'feed' && (
          <div className="flex-1 overflow-y-auto space-y-2 pr-1 min-h-0">
            {filteredEvents.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 text-[var(--text-muted)] text-xs font-mono">
                <CheckCircle2 className="w-5 h-5 mb-2 text-emerald-500" />
                Nominal behavior. No infractions registered.
              </div>
            ) : (
              filteredEvents.slice(0, 35).map((evt) => {
                const ruleBadge = RULE_BADGES[evt.rule] || {
                  label: evt.rule,
                  color: 'bg-[var(--bg-surface)] text-[var(--text-secondary)] border-[var(--border-subtle)]',
                  points: `+${evt.points || 10}`
                };
                const isCritical = evt.severity === 'critical';

                return (
                  <div
                    key={evt.event_id}
                    onClick={() => onOpenClipModal(evt)}
                    className={`p-3 rounded-xl border transition-all cursor-pointer ${isCritical
                        ? 'bg-red-500/5 border-red-500/30 hover:border-red-500'
                        : 'bg-[var(--bg-surface)] border-[var(--border-subtle)] hover:border-[var(--border-medium)]'
                      }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-[var(--bg-card)] text-[var(--text-primary)] border border-[var(--border-subtle)]">
                          {evt.seat_id}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${ruleBadge.color}`}>
                          {ruleBadge.label}
                        </span>
                      </div>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">
                        {evt.t_start ? `t = ${evt.t_start.toFixed(1)}s` : ''}
                      </span>
                    </div>

                    <p className="text-xs text-[var(--text-secondary)] font-medium line-clamp-2 leading-relaxed">
                      {evt.reason}
                    </p>

                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-[var(--border-subtle)] text-[10px] font-mono text-[var(--text-muted)]">
                      <span>Score: <strong className="text-red-500">{Math.round(evt.score_after || 0)}%</strong></span>
                      <span className="text-orange-500 font-medium flex items-center gap-1 hover:underline">
                        <Video className="w-3 h-3" /> Play Clip &rarr;
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}

      </div>

    </div>
  );
}
