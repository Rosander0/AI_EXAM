import React from 'react';
import { 
  Users, UserCheck, Clock, ShieldCheck, Activity, MapPin
} from 'lucide-react';

export default function StaffSupervisionView({
  session,
  staffList,
  staffEvents
}) {
  return (
    <div className="flex-1 flex flex-col p-6 overflow-y-auto min-h-0 space-y-6">
      
      {/* Header */}
      <div className="shrink-0">
        <h2 className="text-xl font-bold text-[var(--text-primary)] flex items-center gap-2.5">
          <Users className="w-5 h-5 text-amber-500" />
          Staff Supervision & Facility Zone Intelligence
        </h2>
        <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">
          Invigilator Patrol Coverage • Median Dwell Time • Lobby & Queue Density Telemetry
        </p>
      </div>

      {/* Staff Overview Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="neu-pressed p-6 rounded-3xl">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">Active Invigilators</span>
            <div className="w-10 h-10 rounded-xl bg-[var(--accent-orange)]/10 text-[var(--accent-orange)] flex items-center justify-center">
              <UserCheck className="w-5 h-5" />
            </div>
          </div>
          <p className="text-4xl font-bold text-[var(--text-primary)] font-mono">{staffList.length}</p>
          <p className="text-[11px] text-[var(--text-muted)] font-bold mt-2 font-mono">
            Classified as roaming invigilator personnel
          </p>
        </div>

        <div className="neu-pressed p-6 rounded-3xl">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">Patrol Inspections</span>
            <div className="w-10 h-10 rounded-xl bg-[var(--accent-emerald)]/10 text-[var(--accent-emerald)] flex items-center justify-center">
              <Activity className="w-5 h-5" />
            </div>
          </div>
          <p className="text-4xl font-bold text-[var(--accent-emerald)] font-mono">
            {staffList.reduce((acc, s) => acc + (s.total_visits || 0), 0)}
          </p>
          <p className="text-[11px] text-[var(--text-muted)] font-bold mt-2 font-mono">
            Total candidate desk cluster visits logged
          </p>
        </div>

        <div className="neu-pressed p-6 rounded-3xl">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-mono font-bold uppercase text-[var(--text-muted)]">Facility Zone</span>
            <div className="w-10 h-10 rounded-xl bg-[var(--accent-amber)]/10 text-[var(--accent-amber)] flex items-center justify-center">
              <MapPin className="w-5 h-5" />
            </div>
          </div>
          <p className="text-2xl font-bold text-[var(--text-primary)] font-mono">Exam Hall & Lobby</p>
          <p className="text-[11px] text-[var(--text-muted)] font-bold mt-2 font-mono">
            Multi-zone tracking without anchor artifacts
          </p>
        </div>
      </div>

      {/* Main Staff Profiles & Events Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Left: Invigilator Profiles */}
        <div className="neu-flat p-6 rounded-3xl flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[var(--accent-amber)]" />
              Invigilator Patrol Profiles
            </h3>
            <span className="text-[10px] font-mono font-bold text-[var(--text-primary)] neu-pressed px-3 py-1 rounded-lg">
              {staffList.length} Active
            </span>
          </div>

          <div className="space-y-4 flex-1 overflow-y-auto pr-1">
            {staffList.length === 0 ? (
              <div className="h-48 flex flex-col items-center justify-center text-center text-[var(--text-muted)] text-xs font-mono font-bold neu-pressed rounded-2xl">
                <Users className="w-8 h-8 mb-3 text-[var(--text-muted)]" />
                No roaming invigilator movement detected yet.
              </div>
            ) : (
              staffList.map(staff => (
                <div
                  key={staff.staff_id}
                  className="p-5 rounded-2xl neu-convex hover:neu-flat transition-all space-y-4"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl neu-pressed flex items-center justify-center text-[var(--accent-orange)] font-bold font-mono text-lg">
                        {staff.staff_id.split('-').pop() || '01'}
                      </div>
                      <div>
                        <h4 className="text-base font-bold text-[var(--text-primary)]">{staff.staff_id}</h4>
                        <p className="text-[10px] font-mono font-bold text-[var(--text-muted)]">Track ID: #{staff.track_id}</p>
                      </div>
                    </div>

                    <span className="px-3 py-1 rounded-lg text-[10px] font-mono font-bold neu-pressed text-[var(--accent-emerald)] uppercase">
                      {staff.status || 'Active Patrol'}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-3 pt-4 border-t-2 border-dashed border-[var(--border-subtle)] text-center font-mono text-xs">
                    <div className="neu-pressed p-2.5 rounded-xl">
                      <span className="text-[9px] font-bold text-[var(--text-muted)] block uppercase mb-1">Median Dwell</span>
                      <strong className="text-[var(--text-primary)]">{(staff.median_dwell_s || 0).toFixed(1)}s</strong>
                    </div>
                    <div className="neu-pressed p-2.5 rounded-xl">
                      <span className="text-[9px] font-bold text-[var(--text-muted)] block uppercase mb-1">Total Visits</span>
                      <strong className="text-[var(--text-primary)]">{staff.total_visits || 0}</strong>
                    </div>
                    <div className="neu-pressed p-2.5 rounded-xl">
                      <span className="text-[9px] font-bold text-[var(--text-muted)] block uppercase mb-1">Total Patrol</span>
                      <strong className="text-[var(--text-secondary)]">{(staff.total_dwell_s || 0).toFixed(0)}s</strong>
                    </div>
                  </div>

                  {staff.last_reason && (
                    <p className="text-[11px] font-bold text-[var(--text-secondary)] italic">
                      &ldquo;{staff.last_reason}&rdquo;
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right: Supervision Logs */}
        <div className="neu-flat p-6 rounded-3xl flex flex-col">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <Activity className="w-4 h-4 text-[var(--accent-emerald)]" />
              Staff Supervision Logs
            </h3>
            <span className="text-[10px] font-mono font-bold text-[var(--text-primary)] neu-pressed px-3 py-1 rounded-lg">
              {staffEvents.length} Logs
            </span>
          </div>

          <div className="space-y-4 flex-1 overflow-y-auto pr-1">
            {staffEvents.length === 0 ? (
              <div className="h-48 flex flex-col items-center justify-center text-center text-[var(--text-muted)] text-xs font-mono font-bold neu-pressed rounded-2xl">
                <Clock className="w-8 h-8 mb-3 text-[var(--text-muted)]" />
                Staff supervision events will appear here as invigilators patrol.
              </div>
            ) : (
              staffEvents.map(evt => (
                <div
                  key={evt.event_id}
                  className="p-4 rounded-2xl neu-convex hover:neu-flat transition-all space-y-2"
                >
                  <div className="flex items-center justify-between text-xs font-mono font-bold">
                    <span className="text-[var(--accent-orange)]">{evt.staff_id}</span>
                    <span className="text-[var(--text-muted)]">
                      t = {evt.t_start?.toFixed(1)}s
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] font-bold">
                    {evt.reason}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

      </div>

    </div>
  );
}
