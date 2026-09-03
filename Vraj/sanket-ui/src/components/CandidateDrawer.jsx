import React from 'react';
import { 
  X, Activity, CheckCircle2, Flame, Clock, User, Video, Play, Layers
} from 'lucide-react';

const RULE_BADGES = {
  hand_phone_grip: { label: 'Phone Grip (MediaPipe)', color: 'bg-orange-500/10 text-orange-400 border-orange-500/25', points: '+80' },
  object_phone: { label: 'Prohibited Device', color: 'bg-red-500/10 text-red-400 border-red-500/25', points: '+100' },
  head_turn: { label: 'Head Deviation', color: 'bg-amber-500/10 text-amber-400 border-amber-500/25', points: '+10' },
  turning_back: { label: 'Turning Back', color: 'bg-rose-600/10 text-rose-400 border-rose-600/25', points: '+35' },
  neighbour_reach: { label: 'Neighbor Reach', color: 'bg-amber-600/10 text-amber-300 border-amber-600/25', points: '+25' },
  hidden_hands: { label: 'Hidden Hands', color: 'bg-yellow-600/10 text-yellow-300 border-yellow-600/25', points: '+15' },
  repeated_action: { label: 'Repeated Pattern', color: 'bg-stone-500/10 text-stone-300 border-stone-500/25', points: '+30' },
  hand_chit_pinch: { label: 'Chit Pinch', color: 'bg-orange-500/10 text-orange-400 border-orange-500/25', points: '+50' },
  object_chit: { label: 'Chit Item', color: 'bg-red-500/10 text-red-400 border-red-500/25', points: '+60' },
  object_unregistered: { label: 'Unregistered Item', color: 'bg-stone-500/10 text-stone-300 border-stone-500/25', points: '+20' }
};

export default function CandidateDrawer({
  candidate,
  candidateEvents,
  onClose,
  onOpenClipModal
}) {
  if (!candidate) return null;

  const isAlert = candidate.status === 'alert' || candidate.score >= 100;
  const isWarning = candidate.status === 'accumulating' || (candidate.score >= 40 && candidate.score < 100);
  const scoreVal = Math.round(candidate.score || 0);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      
      {/* Click outside */}
      <div className="flex-1" onClick={onClose}></div>

      {/* Drawer */}
      <div className="w-full max-w-lg neu-flat m-6 h-[calc(100vh-3rem)] flex flex-col overflow-hidden animate-in slide-in-from-right duration-200">
        
        {/* Header */}
        <div className="p-6 flex items-center justify-between shrink-0 mb-2">
          <div className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center font-mono font-bold text-xl neu-pressed ${
              isAlert 
                ? 'text-red-500' 
                : 'text-[var(--text-primary)]'
            }`}>
              {candidate.seat_id}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">Candidate {candidate.seat_id}</h3>
                {candidate.calibrated && (
                  <span className="px-2 py-0.5 rounded-md text-[9px] font-mono font-bold neu-pressed text-[var(--accent-emerald)]">
                    CALIBRATED
                  </span>
                )}
              </div>
              <p className="text-[11px] font-mono text-[var(--text-muted)] font-bold mt-0.5">
                Row {candidate.grid_row + 1}, Col {candidate.grid_col + 1}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-3 rounded-xl neu-convex text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all active:neu-pressed"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-6">
          
          {/* Suspicion Score Card */}
          <div className="neu-flat p-6 rounded-3xl">
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">Current Suspicion Score</span>
              <span className={`px-3 py-1 rounded-lg text-[10px] font-mono font-bold uppercase neu-pressed ${
                isAlert ? 'text-red-500' : isWarning ? 'text-[var(--accent-amber)]' : 'text-[var(--accent-emerald)]'
              }`}>
                {isAlert ? 'Alert' : isWarning ? 'Accumulating' : 'Nominal'}
              </span>
            </div>

            <div className="flex items-baseline gap-2 mb-3">
              <span className={`text-5xl font-bold font-mono tracking-tight ${
                isAlert ? 'text-red-500' : isWarning ? 'text-[var(--accent-amber)]' : 'text-[var(--accent-emerald)]'
              }`}>
                {scoreVal}%
              </span>
              <span className="text-xs font-mono text-[var(--text-muted)] font-bold">/ 100% threshold</span>
            </div>

            {/* Score Bar with Warm Gradient */}
            <div className="w-full h-3 rounded-full neu-pressed overflow-hidden mb-5">
              <div
                className={`h-full rounded-full transition-all duration-300 ${
                  isAlert 
                    ? 'bg-gradient-to-r from-[var(--accent-amber)] to-red-500' 
                    : isWarning 
                    ? 'bg-gradient-to-r from-[var(--accent-amber)] to-[var(--accent-orange)]' 
                    : 'bg-[var(--accent-emerald)]'
                }`}
                style={{ width: `${Math.min(100, Math.max(4, scoreVal))}%` }}
              ></div>
            </div>

            <div className="grid grid-cols-3 gap-4 text-center text-xs font-mono pt-4">
              <div className="neu-pressed p-3 rounded-2xl">
                <span className="text-[10px] font-bold text-[var(--text-muted)] block uppercase mb-1">Peak</span>
                <strong className={candidate.peak_score >= 100 ? 'text-red-500 text-sm' : 'text-[var(--text-primary)] text-sm'}>
                  {Math.round(candidate.peak_score || 0)}%
                </strong>
              </div>
              <div className="neu-pressed p-3 rounded-2xl">
                <span className="text-[10px] font-bold text-[var(--text-muted)] block uppercase mb-1">Sustained</span>
                <strong className={candidate.sustained_seconds > 0 ? 'text-red-500 text-sm' : 'text-[var(--text-primary)] text-sm'}>
                  {(candidate.sustained_seconds || 0).toFixed(1)}s
                </strong>
              </div>
              <div className="neu-pressed p-3 rounded-2xl">
                <span className="text-[10px] font-bold text-[var(--text-muted)] block uppercase mb-1">Events</span>
                <strong className="text-[var(--text-primary)] text-sm">{candidate.event_count || 0}</strong>
              </div>
            </div>
          </div>

          {/* Baseline Info */}
          <div className="neu-flat rounded-3xl p-6 space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <Activity className="w-4 h-4 text-[var(--accent-amber)]" />
              Biomechanical Self-Calibration
            </h4>

            <div className="space-y-3 text-xs font-mono font-bold text-[var(--text-secondary)]">
              <div className="flex justify-between py-1.5 border-b-2 border-dashed border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">Calibration Window:</span>
                <span className="text-[var(--accent-emerald)]">{candidate.calibrated ? 'COMPLETED (3.0s window)' : 'PENDING'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b-2 border-dashed border-[var(--border-subtle)]">
                <span className="text-[var(--text-muted)]">Posture Baseline:</span>
                <span className="text-[var(--text-primary)]">Rolling Median &amp; MAD</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-[var(--text-muted)]">Score Decay:</span>
                <span className="text-[var(--text-primary)]">D = 1.5 pts/s</span>
              </div>
            </div>
          </div>

          {/* Recorded Events */}
          <div className="space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2 pl-2">
              <Layers className="w-4 h-4 text-[var(--accent-orange)]" />
              Recorded Observations ({candidateEvents.length})
            </h4>

            {candidateEvents.length === 0 ? (
              <div className="p-8 text-center text-xs font-mono font-bold text-[var(--text-muted)] neu-pressed rounded-3xl">
                No behavioral infractions registered for this candidate.
              </div>
            ) : (
              candidateEvents.map(evt => {
                const ruleBadge = RULE_BADGES[evt.rule] || {
                  label: evt.rule,
                  color: 'text-[var(--text-secondary)]',
                  points: `+${evt.points || 10}`
                };
                return (
                  <div
                    key={evt.event_id}
                    onClick={() => onOpenClipModal(evt)}
                    className="p-5 rounded-3xl neu-convex hover:neu-flat cursor-pointer transition-all space-y-3 group"
                  >
                    <div className="flex items-center justify-between">
                      <span className={`text-[11px] font-bold ${ruleBadge.color.replace('bg-', '').replace('border-', '')}`}>
                        {ruleBadge.label}
                      </span>
                      <span className="text-[10px] font-mono font-bold text-[var(--text-muted)]">
                        t = {evt.t_start?.toFixed(1)}s
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] font-bold leading-relaxed">
                      {evt.reason}
                    </p>
                    <div className="flex items-center justify-between pt-3 border-t-2 border-dashed border-[var(--border-subtle)] text-[10px] font-mono font-bold text-[var(--text-muted)]">
                      <span>Score: <strong className="text-red-500">{Math.round(evt.score_after || 0)}%</strong></span>
                      <span className="text-[var(--accent-orange)] group-hover:underline flex items-center gap-1.5 active:opacity-70">
                        <Play className="w-3.5 h-3.5" /> Play Evidence Clip
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>

        </div>

      </div>

    </div>
  );
}
