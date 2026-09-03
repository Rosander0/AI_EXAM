import React, { useState, useMemo } from 'react';
import { 
  Grid, Search, Filter, ShieldAlert, Activity, CheckCircle2, 
  UserX, UserCheck, Flame, ChevronRight, Clock, AlertTriangle, ShieldCheck
} from 'lucide-react';

export default function SeatingMatrixView({
  seats,
  onSelectCandidate
}) {
  const [filterStatus, setFilterStatus] = useState('all'); // all, alert, warning, calm
  const [searchQuery, setSearchQuery] = useState('');

  const filteredSeats = useMemo(() => {
    return seats.filter(seat => {
      // Status filter
      if (filterStatus === 'alert' && !(seat.status === 'alert' || seat.score >= 100)) return false;
      if (filterStatus === 'warning' && !(seat.status === 'accumulating' || (seat.score >= 40 && seat.score < 100))) return false;
      if (filterStatus === 'calm' && !(seat.status === 'calm' || seat.score < 40)) return false;

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesId = seat.seat_id.toLowerCase().includes(q);
        const matchesReason = seat.last_reason?.toLowerCase().includes(q);
        if (!matchesId && !matchesReason) return false;
      }

      return true;
    });
  }, [seats, filterStatus, searchQuery]);

  return (
    <div className="flex-1 flex flex-col p-5 md:p-8 overflow-y-auto min-h-0 space-y-6">
      
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-[var(--text-primary)] flex items-center gap-2.5">
            <Grid className="w-5 h-5 text-[var(--accent-amber)]" />
            Exam Hall Seating Matrix & Spatial Grid
          </h2>
          <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">
            Continuous Posture Calibration • Time-Invariant Suspicion Decay Engine
          </p>
        </div>

        {/* Filters and Search */}
        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Search Box */}
          <div className="relative flex-1 md:w-56">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder="Search seat or action..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full neu-pressed rounded-xl pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition-colors font-mono"
            />
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1 neu-pressed p-1.5 rounded-xl">
            {[
              { id: 'all', label: 'All', count: seats.length },
              { id: 'alert', label: 'Alert (100+)', count: seats.filter(s => s.status === 'alert' || s.score >= 100).length, color: 'text-red-500' },
              { id: 'warning', label: 'Accumulating', count: seats.filter(s => s.status === 'accumulating' || (s.score >= 40 && s.score < 100)).length, color: 'text-[var(--accent-amber)]' },
              { id: 'calm', label: 'Calm', count: seats.filter(s => s.status === 'calm' || s.score < 40).length, color: 'text-[var(--accent-emerald)]' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setFilterStatus(tab.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  filterStatus === tab.id
                    ? 'neu-convex text-[var(--text-primary)]'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <span className={tab.color}>{tab.label}</span> ({tab.count})
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Grid of Seats */}
      {filteredSeats.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-12 text-center neu-pressed rounded-2xl">
          <UserX className="w-12 h-12 text-[var(--text-muted)] mb-3" />
          <h4 className="text-base font-bold text-[var(--text-primary)]">No Candidates Found</h4>
          <p className="text-xs text-[var(--text-muted)] max-w-sm mt-1 font-bold">
            No seated candidates matched your current filter criteria.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
          {filteredSeats.map(seat => {
            const isAlert = seat.status === 'alert' || seat.score >= 100;
            const isWarning = seat.status === 'accumulating' || (seat.score >= 40 && seat.score < 100);
            const scoreNum = Math.round(seat.score || 0);

            return (
              <div
                key={seat.seat_id}
                onClick={() => onSelectCandidate(seat)}
                className={`neu-convex hover:neu-flat rounded-2xl p-5 transition-all duration-200 cursor-pointer relative overflow-hidden group flex flex-col justify-between min-h-[200px]`}
              >
                {/* Status Bar */}
                <div className={`absolute top-0 left-0 right-0 h-1 ${
                  isAlert ? 'bg-red-500' : isWarning ? 'bg-amber-500' : 'bg-emerald-600'
                }`}></div>

                {/* Top: Seat ID & Coordinates */}
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-bold tracking-tight text-[var(--text-primary)] group-hover:text-[var(--accent-copper)] transition-colors">
                          {seat.seat_id}
                        </h3>
                        {seat.occupied && (
                          <span className="w-2 h-2 rounded-full bg-[var(--accent-amber)]" title="Desk Occupied"></span>
                        )}
                      </div>
                      <p className="text-[10px] text-[var(--text-muted)] font-mono">
                        Row {seat.grid_row + 1}, Col {seat.grid_col + 1}
                      </p>
                    </div>

                    <span className={`px-2.5 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-wider border ${
                      isAlert 
                        ? 'bg-red-500/10 text-red-400 border-red-500/25' 
                        : isWarning 
                        ? 'bg-amber-500/10 text-amber-500 border-amber-500/25' 
                        : 'bg-emerald-600/10 text-emerald-600 border-emerald-600/25'
                    }`}>
                      {isAlert ? 'Alert' : isWarning ? 'Accumulating' : 'Nominal'}
                    </span>
                  </div>

                  {/* Suspicion Score Meter */}
                  <div className="my-3">
                    <div className="flex items-baseline justify-between mb-1.5">
                      <span className="text-[10px] font-mono text-[var(--text-muted)] uppercase">Suspicion Score</span>
                      <span className={`text-2xl font-bold font-mono tracking-tight ${
                        isAlert ? 'text-red-500' : isWarning ? 'text-amber-500' : 'text-emerald-600'
                      }`}>
                        {scoreNum}%
                      </span>
                    </div>

                    {/* Score Bar with Warm Gradient */}
                    <div className="w-full h-2 rounded-full bg-[var(--bg-surface)] overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          isAlert 
                            ? 'bg-gradient-to-r from-amber-600 to-red-600' 
                            : isWarning 
                            ? 'bg-gradient-to-r from-amber-600 to-amber-500' 
                            : 'bg-gradient-to-r from-emerald-700 to-emerald-600'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(3, scoreNum))}%` }}
                      ></div>
                    </div>
                  </div>
                </div>

                {/* Bottom: Diagnostics & Last Observed Behaviour */}
                <div className="pt-2.5 border-t border-[var(--border-subtle)] space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] font-mono text-[var(--text-muted)]">
                    <span>Peak: <strong className="text-[var(--text-secondary)]">{Math.round(seat.peak_score || 0)}%</strong></span>
                    <span>Events: <strong className="text-[var(--text-secondary)]">{seat.event_count || 0}</strong></span>
                    <span>Sustained: <strong className={seat.sustained_seconds > 0 ? 'text-red-500' : 'text-[var(--text-secondary)]'}>{(seat.sustained_seconds || 0).toFixed(1)}s</strong></span>
                  </div>

                  {seat.last_reason && (
                    <p className="text-[10px] text-[var(--text-secondary)] italic truncate font-sans">
                      &ldquo;{seat.last_reason}&rdquo;
                    </p>
                  )}
                </div>

              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
