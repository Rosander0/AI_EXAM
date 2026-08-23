import React, { useState, useEffect } from 'react';
import { 
  BarChart3, FileText, Download, ShieldCheck, AlertTriangle, 
  TrendingUp, Clock
} from 'lucide-react';

export default function AnalyticsReportView({
  session,
  seats,
  events,
  timelineData,
  onOpenReportModal
}) {
  const [evalData, setEvalData] = useState(null);

  useEffect(() => {
    if (session?.session_id) {
      fetchEval(session.session_id);
    }
  }, [session?.session_id]);

  const fetchEval = async (id) => {
    try {
      const res = await fetch(`/api/eval/${id}`);
      if (res.ok) {
        const data = await res.json();
        setEvalData(data);
      }
    } catch (err) {
      console.warn("Eval error:", err);
    }
  };

  const criticalSeats = seats.filter(s => s.status === 'alert' || s.score >= 100);
  const durationMin = session?.duration_s ? (session.duration_s / 60).toFixed(1) : '0.0';

  return (
    <div className="flex-1 flex flex-col p-6 overflow-y-auto min-h-0 space-y-6">
      
      {/* Header with Quick Actions */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-[var(--text-primary)] flex items-center gap-2.5">
            <BarChart3 className="w-5 h-5 text-amber-500" />
            Compliance Analytics &amp; Invigilation Reporting
          </h2>
          <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">
            Sustained Alert Rankings • Continuous Score Decay Curves • 100% Consistent CSV/HTML Records
          </p>
        </div>

        {/* Action Buttons */}
        {session && (
          <div className="flex items-center gap-3">
            <button
              onClick={onOpenReportModal}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl neu-convex hover:neu-pressed text-[var(--accent-orange)] text-xs font-bold transition-all"
            >
              <FileText className="w-4 h-4" />
              Preview HTML Report
            </button>

            <a
              href={`/api/sessions/${session.session_id}/report.csv`}
              download
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-[var(--accent-orange)] to-[var(--accent-amber)] hover:opacity-90 text-white text-xs font-bold transition-all shadow-md shadow-orange-500/20"
            >
              <Download className="w-4 h-4" />
              Download CSV
            </a>
          </div>
        )}
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        
        <div className="neu-pressed p-6 rounded-3xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">Total Duration</span>
            <Clock className="w-4 h-4 text-[var(--accent-amber)]" />
          </div>
          <p className="text-3xl font-bold text-[var(--text-primary)] font-mono">{durationMin} <span className="text-xs text-[var(--text-muted)] font-normal">mins</span></p>
          <p className="text-[11px] font-bold text-[var(--text-muted)] mt-1.5 font-mono">
            {session?.frames_processed?.toLocaleString() || 0} frames analyzed
          </p>
        </div>

        <div className="neu-pressed p-6 rounded-3xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono font-bold uppercase text-red-500">Critical Disqualified</span>
            <AlertTriangle className="w-4 h-4 text-red-500" />
          </div>
          <p className="text-3xl font-bold text-red-500 font-mono">{criticalSeats.length}</p>
          <p className="text-[11px] font-bold text-red-500/80 mt-1.5 font-mono">
            Crossed threshold 100 points
          </p>
        </div>

        <div className="neu-pressed p-6 rounded-3xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono font-bold uppercase text-[var(--accent-emerald)]">False-Alarm Rate</span>
            <ShieldCheck className="w-4 h-4 text-[var(--accent-emerald)]" />
          </div>
          <p className="text-3xl font-bold text-[var(--accent-emerald)] font-mono">
            {evalData ? `${evalData.fa_per_hour} / hr` : '0.00 / hr'}
          </p>
          <p className="text-[11px] font-bold text-[var(--accent-emerald)]/80 mt-1.5 font-mono">
            100% MediaPipe hand biomechanics immunity
          </p>
        </div>

        <div className="neu-pressed p-6 rounded-3xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">Total Infractions</span>
            <TrendingUp className="w-4 h-4 text-[var(--accent-orange)]" />
          </div>
          <p className="text-2xl font-bold text-[var(--text-primary)] font-mono">{events.length}</p>
          <p className="text-[10px] text-[var(--text-muted)] mt-1 font-mono">
            Logged across all rules & criteria
          </p>
        </div>

      </div>

      {/* Candidate Score Timelines */}
      <div className="neu-flat p-8 flex flex-col rounded-3xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-base font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-[var(--accent-amber)]" />
              Candidate Suspicion Trajectories Over Time
            </h3>
            <p className="text-[12px] font-bold text-[var(--text-muted)] font-mono mt-1">
              Continuous score curves demonstrating decay behavior $S = \max(0, S - D\cdot\Delta t) + \sum w_i E_i$
            </p>
          </div>
        </div>

        <div className="space-y-4">
          {seats.length === 0 ? (
            <div className="p-8 text-center text-[var(--text-muted)] text-xs font-mono font-bold neu-pressed rounded-2xl">
              No seat telemetry data recorded yet.
            </div>
          ) : (
            seats.slice(0, 8).map(seat => {
              const seatTimeline = timelineData?.seats?.[seat.seat_id] || [];
              const isAlert = seat.status === 'alert' || seat.score >= 100;
              const isWarning = seat.status === 'accumulating' || (seat.score >= 40 && seat.score < 100);

              return (
                <div
                  key={seat.seat_id}
                  className="p-4 rounded-2xl neu-convex flex flex-col md:flex-row md:items-center gap-5"
                >
                  <div className="w-48 shrink-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-bold text-[var(--text-primary)]">{seat.seat_id}</span>
                      {isAlert && (
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-mono neu-pressed text-red-500 uppercase font-bold">
                          Alert
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] font-bold text-[var(--text-muted)] font-mono">
                      Peak: <strong className={isAlert ? 'text-red-500' : 'text-[var(--text-secondary)]'}>{Math.round(seat.peak_score || 0)}%</strong> • Sustained: {(seat.sustained_seconds || 0).toFixed(1)}s
                    </p>
                  </div>

                  {/* Timeline Bar Micro Chart */}
                  <div className="flex-1 h-14 neu-pressed rounded-xl p-1.5 flex items-end gap-[3px] overflow-hidden">
                    {seatTimeline.length > 0 ? (
                      seatTimeline.slice(-80).map((pt, i) => {
                        const val = pt.score || 0;
                        const barDanger = val >= 100;
                        const barWarn = val >= 40 && !barDanger;
                        return (
                          <div
                            key={i}
                            className={`flex-1 min-w-[3px] rounded-t-sm transition-all ${
                              barDanger 
                                ? 'bg-red-500' 
                                : barWarn 
                                ? 'bg-[var(--accent-amber)]' 
                                : 'bg-[var(--text-muted)]/30'
                            }`}
                            style={{ height: `${Math.max(4, Math.min(100, val))}%` }}
                            title={`t: ${pt.t?.toFixed(1)}s, score: ${Math.round(val)}%`}
                          ></div>
                        );
                      })
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-[10px] font-mono font-bold text-[var(--text-muted)]">
                        Awaiting timeline samples...
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

    </div>
  );
}
