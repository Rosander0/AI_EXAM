import React, { useState, useRef } from 'react';
import { 
  X, Radio, UploadCloud, Video, Play, Activity, 
  Sparkles, CheckCircle2, AlertTriangle, Film
} from 'lucide-react';

const PRESET_DATASETS = [
  {
    title: 'Mobile Phone in Examination Hall',
    desc: 'Candidate holding & browsing handheld phone. Evaluates 21-hand landmark grip biomechanics.',
    path: 'DRISHTI AI DEXIT GLobal Datasets/01.Candidate was found using a mobile phone in the examination hall..mkv',
    tag: 'Handheld Phone Grip (+80 pts)',
    color: 'border-orange-500/30 text-orange-500 bg-orange-500/10'
  },
  {
    title: 'Candidate Talking & Head Deviation',
    desc: 'Candidate turning head off calibrated baseline to communicate with adjacent desk.',
    path: 'DRISHTI AI DEXIT GLobal Datasets/04.CCTV Candidate Talking.mkv',
    tag: 'Gaze & Head Deviation (+35 pts)',
    color: 'border-amber-500/30 text-amber-500 bg-amber-500/10'
  },
  {
    title: 'Reception & Baggage Queue Flow',
    desc: 'Open lobby & verification desk monitoring. Tracks crowd count without false desk anchors.',
    path: 'DRISHTI AI DEXIT GLobal Datasets/05.Crowd observed near the reception and verification desk..mp4',
    tag: 'Facility Zone Tracking',
    color: 'border-stone-500/30 text-[var(--text-secondary)] bg-stone-500/10'
  }
];

export default function SessionModal({
  onClose,
  onStartSession,
  onUploadAndStart
}) {
  const [activeMode, setActiveMode] = useState('presets'); // presets, upload, rtsp
  const [rtspUrl, setRtspUrl] = useState('');
  const [isStarting, setIsStarting] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const fileInputRef = useRef(null);

  const handleStartPreset = async (path) => {
    setIsStarting(true);
    setUploadError(null);
    try {
      const ok = await onStartSession(path);
      if (ok) onClose();
    } catch (err) {
      setUploadError(err.message || 'Failed to start session.');
    } finally {
      setIsStarting(false);
    }
  };

  const handleStartRtsp = async (e) => {
    e.preventDefault();
    if (!rtspUrl) return;
    setIsStarting(true);
    setUploadError(null);
    try {
      const ok = await onStartSession(rtspUrl);
      if (ok) onClose();
    } catch (err) {
      setUploadError(err.message || 'Failed to connect RTSP stream.');
    } finally {
      setIsStarting(false);
    }
  };

  const handleFileSelected = async (file) => {
    if (!file) return;
    setIsStarting(true);
    setUploadError(null);
    try {
      const ok = await onUploadAndStart(file);
      if (ok) onClose();
    } catch (err) {
      setUploadError(err.message || 'Failed to upload video.');
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      
      <div className="w-full max-w-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-2xl shadow-2xl overflow-hidden flex flex-col relative animate-in zoom-in-95 duration-200">
        
        {/* Loading Overlay */}
        {isStarting && (
          <div className="absolute inset-0 z-20 bg-[var(--bg-card)]/90 backdrop-blur-md flex flex-col items-center justify-center text-center p-6">
            <Activity className="w-10 h-10 text-amber-500 animate-spin mb-4" />
            <h4 className="text-base font-bold text-[var(--text-primary)] font-mono">Initializing SANKET Engine...</h4>
            <p className="text-xs text-[var(--text-muted)] font-mono mt-1">
              Calibrating per-seat baselines &amp; starting neural inference
            </p>
          </div>
        )}

        {/* Header */}
        <div className="p-5 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-surface)]">
          <div>
            <h3 className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              Initialize Examination Surveillance
            </h3>
            <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">
              Select an exam room feed source or load a benchmark recording
            </p>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Navigation */}
        <div className="flex border-b border-[var(--border-subtle)] p-2 bg-[var(--bg-surface)] gap-2">
          {[
            { id: 'presets', label: 'Benchmark Datasets', icon: Film },
            { id: 'upload', label: 'Upload Video File', icon: UploadCloud },
            { id: 'rtsp', label: 'Live RTSP Stream', icon: Radio },
          ].map(tab => {
            const Icon = tab.icon;
            const isActive = activeMode === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveMode(tab.id)}
                className={`flex-1 py-2 px-3 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all ${
                  isActive 
                    ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm border border-[var(--border-subtle)]' 
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Error Alert */}
        {uploadError && (
          <div className="mx-6 mt-4 p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-500 text-xs flex items-center gap-2 font-mono">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{uploadError}</span>
          </div>
        )}

        {/* Tab Contents */}
        <div className="p-6 flex-1 overflow-y-auto">
          
          {/* 1. Presets */}
          {activeMode === 'presets' && (
            <div className="space-y-3.5">
              <p className="text-xs text-[var(--text-muted)] font-mono mb-2">
                Click any benchmark video scenario to launch invigilation:
              </p>
              {PRESET_DATASETS.map((preset, i) => (
                <div
                  key={i}
                  onClick={() => handleStartPreset(preset.path)}
                  className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] hover:border-[var(--border-medium)] hover:bg-[var(--bg-hover)] transition-all cursor-pointer group flex items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2.5">
                      <h4 className="text-sm font-bold text-[var(--text-primary)] group-hover:text-orange-500 transition-colors">
                        {preset.title}
                      </h4>
                      <span className={`px-2 py-0.5 rounded text-[9px] font-mono border ${preset.color}`}>
                        {preset.tag}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed font-sans">
                      {preset.desc}
                    </p>
                  </div>

                  <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-orange-600 to-amber-600 text-white flex items-center justify-center shrink-0 shadow-sm group-hover:scale-105 transition-transform">
                    <Play className="w-4 h-4 fill-current ml-0.5" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 2. File Upload */}
          {activeMode === 'upload' && (
            <div className="space-y-4">
              <input
                type="file"
                accept="video/*"
                ref={fileInputRef}
                className="hidden"
                onChange={(e) => handleFileSelected(e.target.files?.[0])}
              />
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragOver(false);
                  handleFileSelected(e.dataTransfer.files?.[0]);
                }}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-2xl p-12 text-center transition-all cursor-pointer flex flex-col items-center justify-center gap-3.5 ${
                  isDragOver 
                    ? 'border-orange-500 bg-orange-500/5' 
                    : 'border-[var(--border-subtle)] hover:border-[var(--border-medium)] bg-[var(--bg-surface)]'
                }`}
              >
                <div className="w-12 h-12 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] flex items-center justify-center text-amber-500">
                  <UploadCloud className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm font-bold text-[var(--text-primary)]">Drag &amp; drop exam CCTV recording</p>
                  <p className="text-xs text-[var(--text-muted)] mt-1 font-mono">Supports MP4, MKV, AVI files</p>
                </div>
                <button
                  type="button"
                  className="mt-2 px-4 py-2 rounded-xl bg-[var(--bg-card)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] text-xs font-semibold font-mono border border-[var(--border-subtle)] transition-colors"
                >
                  Browse Local File
                </button>
              </div>
            </div>
          )}

          {/* 3. RTSP Camera Stream */}
          {activeMode === 'rtsp' && (
            <form onSubmit={handleStartRtsp} className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-mono uppercase text-[var(--text-muted)] block">
                  RTSP / HTTP Stream URL
                </label>
                <input
                  type="text"
                  placeholder="rtsp://admin:password@192.168.1.100:554/live/ch0"
                  value={rtspUrl}
                  onChange={(e) => setRtspUrl(e.target.value)}
                  required
                  className="w-full bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-xl p-3.5 text-xs text-[var(--text-primary)] font-mono focus:outline-none focus:border-orange-500"
                />
                <p className="text-[10px] text-[var(--text-muted)] font-mono">
                  Direct connection to IP exam room camera over RTSP protocol.
                </p>
              </div>

              <button
                type="submit"
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white font-bold text-xs uppercase tracking-wider transition-all shadow-md"
              >
                Connect Stream &amp; Start Analysis
              </button>
            </form>
          )}

        </div>

      </div>

    </div>
  );
}
