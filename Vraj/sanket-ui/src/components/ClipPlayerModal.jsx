import React, { useEffect } from 'react';
import { 
  X, Video, Download, Play, Clock, AlertTriangle, ShieldCheck
} from 'lucide-react';

const RULE_BADGES = {
  hand_phone_grip: { label: 'Phone Grip (MediaPipe)', color: 'bg-orange-500/10 text-orange-500 border-orange-500/25', points: '+80' },
  object_phone: { label: 'Prohibited Device', color: 'bg-red-500/10 text-red-500 border-red-500/25', points: '+100' },
  head_turn: { label: 'Head Deviation', color: 'bg-amber-500/10 text-amber-500 border-amber-500/25', points: '+10' },
  turning_back: { label: 'Turning Back', color: 'bg-rose-500/10 text-rose-500 border-rose-500/25', points: '+35' },
  neighbour_reach: { label: 'Neighbor Reach', color: 'bg-amber-500/10 text-amber-500 border-amber-500/25', points: '+25' },
  hidden_hands: { label: 'Hidden Hands', color: 'bg-stone-500/10 text-stone-300 border-stone-500/25', points: '+15' },
  repeated_action: { label: 'Repeated Pattern', color: 'bg-stone-500/10 text-stone-300 border-stone-500/25', points: '+30' },
  hand_chit_pinch: { label: 'Chit Pinch', color: 'bg-orange-500/10 text-orange-500 border-orange-500/25', points: '+50' },
  object_chit: { label: 'Chit Item', color: 'bg-red-500/10 text-red-500 border-red-500/25', points: '+60' },
  object_unregistered: { label: 'Unregistered Item', color: 'bg-stone-500/10 text-stone-300 border-stone-500/25', points: '+20' }
};

export default function ClipPlayerModal({
  event,
  onClose
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!event) return null;

  const ruleBadge = RULE_BADGES[event.rule] || {
    label: event.rule,
    color: 'bg-[var(--bg-surface)] text-[var(--text-secondary)] border-[var(--border-subtle)]',
    points: `+${event.points || 10}`
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      
      <div className="w-full max-w-3xl neu-flat rounded-3xl overflow-hidden animate-in zoom-in-95 duration-200 flex flex-col m-4 shadow-[0_30px_60px_rgba(0,0,0,0.4)] border border-white/5">
        
        {/* Modal Header */}
        <div className="p-6 flex items-center justify-between shrink-0 z-10">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl neu-pressed text-[var(--accent-orange)] flex items-center justify-center">
              <Video className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">
                  Evidence Clip • {event.event_id}
                </h3>
                <span className={`px-2.5 py-1 rounded-md text-[10px] font-bold border ${ruleBadge.color}`}>
                  {ruleBadge.label}
                </span>
              </div>
              <p className="text-xs font-mono font-bold text-[var(--text-muted)] mt-1">
                Seat: {event.seat_id} • Timestamp: {event.t_start?.toFixed(1)}s - {event.t_end?.toFixed(1)}s
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

        {/* Video Container */}
        <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden neu-pressed mx-6 rounded-2xl">
          <video
            src={`/api/clips/${event.event_id}`}
            controls
            autoPlay
            loop
            className="w-full h-full object-contain rounded-2xl"
          >
            Your browser does not support HTML5 video playback.
          </video>
        </div>

        {/* Modal Footer */}
        <div className="p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="space-y-2 max-w-xl">
            <p className="text-sm text-[var(--text-secondary)] font-bold leading-relaxed font-sans">
              <strong className="text-[var(--text-primary)]">Observed Action:</strong> {event.reason}
            </p>
            <div className="flex items-center gap-5 text-[11px] font-mono text-[var(--text-muted)] font-bold">
              <span>Points Added: <strong className="text-red-500">{ruleBadge.points} pts</strong></span>
              <span>Score After: <strong className="text-red-500">{Math.round(event.score_after || 0)}%</strong></span>
              <span>Frames: {event.frame_start} - {event.frame_end}</span>
            </div>
          </div>

          <a
            href={`/api/clips/${event.event_id}`}
            download={`${event.event_id}.mp4`}
            className="px-5 py-3 rounded-xl bg-gradient-to-r from-[var(--accent-orange)] to-[var(--accent-amber)] hover:opacity-90 text-white text-xs font-bold font-mono flex items-center gap-2 shrink-0 transition-all shadow-lg shadow-orange-500/20"
          >
            <Download className="w-4 h-4" />
            Download MP4
          </a>
        </div>

      </div>

    </div>
  );
}
