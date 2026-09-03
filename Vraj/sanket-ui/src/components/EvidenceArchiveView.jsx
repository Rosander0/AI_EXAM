import React, { useState, useMemo } from 'react';
import { 
  Layers, Search, Filter, Video, Play, AlertTriangle, 
  Calendar, Clock, Download, ChevronRight, Eye, Grid, List
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

export default function EvidenceArchiveView({
  events,
  onOpenClipModal
}) {
  const [severityFilter, setSeverityFilter] = useState('all'); // all, critical, warning
  const [ruleFilter, setRuleFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // grid, table

  const filteredEvents = useMemo(() => {
    return events.filter(evt => {
      if (severityFilter !== 'all' && evt.severity !== severityFilter) return false;
      if (ruleFilter !== 'all' && evt.rule !== ruleFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesSeat = evt.seat_id?.toLowerCase().includes(q);
        const matchesReason = evt.reason?.toLowerCase().includes(q);
        const matchesRule = evt.rule?.toLowerCase().includes(q);
        if (!matchesSeat && !matchesReason && !matchesRule) return false;
      }
      return true;
    });
  }, [events, severityFilter, ruleFilter, searchQuery]);

  const uniqueRules = Array.from(new Set(events.map(e => e.rule)));

  return (
    <div className="flex-1 flex flex-col p-5 md:p-8 overflow-y-auto min-h-0 space-y-6">
      
      {/* Header & Controls */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-[var(--text-primary)] flex items-center gap-2.5">
            <Layers className="w-5 h-5 text-[var(--accent-amber)]" />
            Evidence Archive & Video Clip Vault
          </h2>
          <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">
            Asynchronous 3-Second Pre/Post MP4 Infraction Recordings & Verification Frames
          </p>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto">
          {/* Search */}
          <div className="relative flex-1 sm:w-52">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder="Search candidate, rule..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full neu-pressed rounded-xl pl-9 pr-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none font-mono"
            />
          </div>

          {/* Rule Dropdown */}
          <select
            value={ruleFilter}
            onChange={(e) => setRuleFilter(e.target.value)}
            className="neu-pressed text-[var(--text-secondary)] rounded-xl px-4 py-2 text-xs focus:outline-none cursor-pointer"
          >
            <option value="all">All Rules ({events.length})</option>
            {uniqueRules.map(r => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>

          {/* Severity Buttons */}
          <div className="flex items-center gap-1 neu-pressed p-1.5 rounded-xl">
            {[
              { id: 'all', label: 'All' },
              { id: 'critical', label: 'Critical', color: 'text-red-500' },
              { id: 'warning', label: 'Warning', color: 'text-[var(--accent-amber)]' }
            ].map(sev => (
              <button
                key={sev.id}
                onClick={() => setSeverityFilter(sev.id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  severityFilter === sev.id
                    ? 'neu-convex text-[var(--text-primary)]'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                }`}
              >
                <span className={sev.color}>{sev.label}</span>
              </button>
            ))}
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 neu-pressed p-1.5 rounded-xl">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-lg ${viewMode === 'grid' ? 'neu-convex text-[var(--text-primary)]' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}
              title="Grid View"
            >
              <Grid className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`p-2 rounded-lg ${viewMode === 'table' ? 'neu-convex text-[var(--text-primary)]' : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'}`}
              title="Table View"
            >
              <List className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Content View */}
      {filteredEvents.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-12 text-center neu-pressed rounded-3xl">
          <Layers className="w-12 h-12 text-[var(--text-muted)] mb-3" />
          <h4 className="text-base font-bold text-[var(--text-primary)]">No Evidence Clips Found</h4>
          <p className="text-xs text-[var(--text-muted)] max-w-sm mt-1 font-bold">
            No behavioral events match the active filter or search query.
          </p>
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredEvents.map(evt => {
            const ruleBadge = RULE_BADGES[evt.rule] || {
              label: evt.rule,
              color: 'text-[var(--text-secondary)]',
              points: `+${evt.points || 10}`
            };
            const isCritical = evt.severity === 'critical';

            return (
              <div
                key={evt.event_id}
                onClick={() => onOpenClipModal(evt)}
                className="neu-convex hover:neu-flat rounded-2xl overflow-hidden transition-all duration-200 cursor-pointer group flex flex-col justify-between"
              >
                {/* Thumbnail Container */}
                <div className="relative aspect-video bg-[var(--bg-surface)] flex items-center justify-center overflow-hidden border-b border-[var(--border-subtle)]">
                  <img
                    src={`/api/thumbs/${evt.event_id}`}
                    alt="Evidence Frame"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />
                  <div className="absolute inset-0 bg-black/30 group-hover:bg-black/15 flex items-center justify-center transition-colors">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-orange-600 to-amber-500 text-white flex items-center justify-center group-hover:scale-110 transition-transform shadow-md">
                      <Play className="w-4 h-4 fill-current ml-0.5" />
                    </div>
                  </div>

                  <span className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded-md text-[9px] font-mono font-bold bg-[var(--bg-base)]/90 backdrop-blur-md text-[var(--text-primary)] border border-[var(--border-subtle)]">
                    {evt.seat_id}
                  </span>

                  <span className="absolute bottom-2.5 right-2.5 px-2 py-0.5 rounded-md text-[9px] font-mono bg-[var(--bg-base)]/90 backdrop-blur-md text-[var(--text-secondary)]">
                    t = {evt.t_start?.toFixed(1)}s
                  </span>
                </div>

                {/* Card Info */}
                <div className="p-4 flex-1 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-medium border ${ruleBadge.color}`}>
                        {ruleBadge.label}
                      </span>
                      <span className="text-[10px] font-mono text-red-500 font-bold">
                        {ruleBadge.points} pts
                      </span>
                    </div>

                    <p className="text-xs text-[var(--text-secondary)] font-medium line-clamp-2 leading-relaxed">
                      {evt.reason}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[var(--border-subtle)] flex items-center justify-between text-[10px] font-mono text-[var(--text-muted)]">
                    <span>Score: <strong className="text-red-500">{Math.round(evt.score_after || 0)}%</strong></span>
                    <span className="text-[var(--accent-copper)] font-semibold group-hover:underline flex items-center gap-1">
                      Play Clip &rarr;
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* Table View */
        <div className="neu-convex rounded-3xl overflow-hidden p-2">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="text-[var(--text-muted)] text-[10px] uppercase font-bold">
                <tr>
                  <th className="py-4 px-5">Event ID</th>
                  <th className="py-4 px-5">Seat</th>
                  <th className="py-4 px-5">Timestamp</th>
                  <th className="py-4 px-5">Rule Fired</th>
                  <th className="py-4 px-5">Severity</th>
                  <th className="py-4 px-5">Observed Behavior</th>
                  <th className="py-4 px-5">Score After</th>
                  <th className="py-4 px-5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="text-[var(--text-secondary)] font-bold">
                {filteredEvents.map(evt => {
                  const ruleBadge = RULE_BADGES[evt.rule] || {
                    label: evt.rule,
                    color: 'text-[var(--text-secondary)]',
                    points: `+${evt.points || 10}`
                  };
                  return (
                    <tr
                      key={evt.event_id}
                      onClick={() => onOpenClipModal(evt)}
                      className="hover:neu-flat cursor-pointer transition-all border-b-2 border-dashed border-[var(--border-subtle)] last:border-0"
                    >
                      <td className="py-4 px-5 text-[var(--accent-orange)]">{evt.event_id}</td>
                      <td className="py-4 px-5 text-[var(--text-primary)]">{evt.seat_id}</td>
                      <td className="py-4 px-5 text-[var(--text-muted)]">
                        {evt.t_start?.toFixed(1)}s - {evt.t_end?.toFixed(1)}s
                      </td>
                      <td className="py-4 px-5">
                        <span className={`text-[11px] font-bold ${ruleBadge.color.replace('bg-', '').replace('border-', '')}`}>
                          {ruleBadge.label}
                        </span>
                      </td>
                      <td className="py-4 px-5">
                        <span className={`px-2 py-1 rounded-md text-[10px] uppercase ${
                          evt.severity === 'critical' ? 'neu-pressed text-red-500' : 'neu-pressed text-[var(--accent-amber)]'
                        }`}>
                          {evt.severity}
                        </span>
                      </td>
                      <td className="py-4 px-5 font-sans text-xs text-[var(--text-secondary)] max-w-md truncate">
                        {evt.reason}
                      </td>
                      <td className="py-4 px-5 text-red-500">
                        {Math.round(evt.score_after || 0)}%
                      </td>
                      <td className="py-4 px-5 text-right">
                        <button className="px-4 py-2 rounded-xl neu-convex hover:neu-pressed text-[var(--accent-orange)] text-[10px] inline-flex items-center gap-1.5 transition-all">
                          <Play className="w-3.5 h-3.5 fill-current" /> Play
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
