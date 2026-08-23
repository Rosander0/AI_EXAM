import React from 'react';
import {
  ShieldCheck, Radio, Grid, Layers, Users, BarChart3,
  Cpu, Activity
} from 'lucide-react';

export default function Sidebar({
  activeTab,
  setActiveTab,
  session,
  deviceInfo
}) {
  const isRunning = session?.state === 'running';

  const navItems = [
    { id: 'live', label: 'Live Monitor', icon: Radio },
    { id: 'grid', label: 'Seating Matrix', icon: Grid },
    { id: 'events', label: 'Evidence Vault', icon: Layers, badge: session?.events_total },
    { id: 'staff', label: 'Staff & Facility', icon: Users },
    { id: 'analytics', label: 'Analytics & Reports', icon: BarChart3 },
  ];

  return (
    <aside className="w-64 bg-[var(--bg-sidebar)] border-r border-[var(--border-subtle)] flex flex-col shrink-0 h-screen select-none">

      {/* Brand Header */}
      <div className="h-16 px-5 flex items-center justify-between border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-orange-600 to-amber-600 flex items-center justify-center text-white font-bold shadow-sm">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <span className="font-semibold text-sm tracking-tight text-[var(--text-primary)]">
              SANKET<span className="text-orange-500 font-bold">.AI</span>
            </span>
            <p className="text-[10px] text-[var(--text-muted)] font-mono">
              Invigilation Intelligence
            </p>
          </div>
        </div>
      </div>

      {/* Main Navigation */}
      <div className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          Operations
        </div>

        {navItems.map(item => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${isActive
                  ? 'bg-orange-600/10 text-orange-500 font-semibold'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]'
                }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 ${isActive ? 'text-orange-500' : 'text-[var(--text-muted)]'}`} />
                <span>{item.label}</span>
              </div>

              {item.badge > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-[var(--bg-surface)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer Info & Hardware Status */}
      <div className="p-4 border-t border-[var(--border-subtle)] space-y-3 bg-black/10">

        {/* System Status Pill */}
        <div className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] text-xs">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-emerald-500 animate-pulse' : 'bg-stone-500'}`}></span>
            <span className="text-[11px] font-mono font-medium text-[var(--text-secondary)]">
              {isRunning ? 'ACTIVE MONITOR' : 'ENGINE STANDBY'}
            </span>
          </div>
        </div>

        {/* Hardware Chip */}
        <div className="flex items-center justify-between text-[11px] font-mono text-[var(--text-muted)] px-1">
          <span className="flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-amber-500" />
            <span>{deviceInfo || 'AUTO'}</span>
          </span>
          {session?.fps_processing && (
            <span className="text-emerald-500 font-medium">{session.fps_processing.toFixed(1)} FPS</span>
          )}
        </div>

      </div>

    </aside>
  );
}
