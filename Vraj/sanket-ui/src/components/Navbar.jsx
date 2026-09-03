import React from 'react';
import {
  Volume2, VolumeX, PlusCircle, RefreshCw, Moon, Sun
} from 'lucide-react';

export default function Navbar({
  session,
  sessionsList,
  onSelectSession,
  soundEnabled,
  setSoundEnabled,
  theme,
  setTheme,
  onOpenNewSessionModal,
  onRefresh
}) {
  return (
    <header className="h-16 px-6 neu-flat flex items-center justify-between z-20 shrink-0">

      {/* Session Selector */}
      <div className="flex items-center gap-3">
        {sessionsList?.length > 0 && (
          <select
            value={session?.session_id || ''}
            onChange={(e) => onSelectSession(e.target.value)}
            className="neu-pressed text-[var(--text-primary)] rounded-lg px-4 py-2 text-xs font-mono focus:outline-none cursor-pointer max-w-[220px] truncate"
          >
            {sessionsList.map(s => (
              <option key={s.session_id} value={s.session_id}>
                {s.session_id.replace('sess_', '')} ({s.state})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">

        {/* Refresh */}
        <button
          onClick={onRefresh}
          title="Refresh Data"
          className="p-2.5 rounded-xl neu-convex text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all"
        >
          <RefreshCw className="w-4 h-4" />
        </button>

        {/* Audio Alert Toggle */}
        <button
          onClick={() => setSoundEnabled(!soundEnabled)}
          title={soundEnabled ? "Audio Alerts: Active" : "Audio Alerts: Muted"}
          className={`p-2.5 rounded-xl transition-all ${soundEnabled
              ? 'neu-pressed text-[var(--accent-amber)]'
              : 'neu-convex text-[var(--text-muted)] hover:text-[var(--text-primary)]'
            }`}
        >
          {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
        </button>

        {/* Theme Switcher */}
        <button
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          title="Toggle Theme"
          className="p-2.5 rounded-xl neu-convex text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* New Feed Button */}
        <button
          onClick={onOpenNewSessionModal}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl neu-convex text-[var(--accent-orange)] hover:text-orange-400 font-bold text-xs transition-all"
        >
          <PlusCircle className="w-4 h-4" />
          <span>New Feed</span>
        </button>

      </div>
    </header>
  );
}
