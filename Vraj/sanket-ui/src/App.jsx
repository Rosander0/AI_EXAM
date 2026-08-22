import React, { useState, useEffect, useRef } from 'react';
import { 
  Camera, UploadCloud, AlertTriangle, ShieldCheck, 
  Activity, XCircle, CheckCircle, Video, UserX, BarChart2, Moon, Sun
} from 'lucide-react';

const API_BASE = '/api';

const IconCamera = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"></path><circle cx="12" cy="13" r="3"></circle></svg>;
const IconUpload = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>;
const IconAlert = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" x2="12" y1="9" y2="13"></line><line x1="12" x2="12.01" y1="17" y2="17"></line></svg>;
const IconStop = () => <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"></rect><path d="M9 9h6v6H9z"></path></svg>;

export default function App() {

  const [view, setView] = useState('setup'); // setup, monitoring, confirm-stop, results
  const [mode, setMode] = useState('live'); // live, upload
  const [theme, setTheme] = useState('dark');

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [theme]);
  
  // API State
  const [sessionId, setSessionId] = useState(null);
  const [rtspUrl, setRtspUrl] = useState('');
  const [isStarting, setIsStarting] = useState(false);

  // Monitoring State
  const [students, setStudents] = useState([]);
  const [elapsed, setElapsed] = useState(0);
  const [logs, setLogs] = useState([]);
  const [timeline, setTimeline] = useState({});
  
  const fileInputRef = useRef(null);
  const [confirmInput, setConfirmInput] = useState('');

  // Start Session API call
  const startSession = async (sourcePath) => {
    setIsStarting(true);
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: sourcePath, config_overrides: {} })
      });
      if (!res.ok) {
        const err = await res.json();
        alert(`Failed to start session: ${err.detail || res.statusText}`);
        return false;
      }
      const data = await res.json();
      setSessionId(data.session_id);
      setStudents([]);
      setLogs([]);
      setElapsed(0);
      setView('monitoring');
      return true;
    } catch (error) {
      console.error(error);
      alert('Network error connecting to backend. Is the FastAPI server running on port 8000?');
      return false;
    } finally {
      setIsStarting(false);
    }
  };

  const handleStartLive = (e) => {
    e.preventDefault();
    if (!rtspUrl) return;
    startSession(rtspUrl);
  };

  const processFileUpload = async (file) => {
    setIsStarting(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const upRes = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData
      });
      if (!upRes.ok) {
        let errDetail = 'Unknown Error';
        try {
          const errData = await upRes.json();
          errDetail = errData.detail || JSON.stringify(errData);
        } catch (e) {
          errDetail = upRes.statusText;
        }
        throw new Error(`Upload failed: ${upRes.status} - ${errDetail}`);
      }
      const upData = await upRes.json();
      
      // Start session with the returned source_path
      await startSession(upData.source_path);
    } catch (err) {
      console.error(err);
      alert(`Failed to upload video:\n${err.message}`);
      setIsStarting(false);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) processFileUpload(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) processFileUpload(file);
  };
  const preventDefaultDrag = (e) => e.preventDefault();

  // Polling Loop for Seats and Events
  useEffect(() => {
    let timer;
    if (view === 'monitoring' && sessionId) {
      timer = setInterval(async () => {
        setElapsed(prev => prev + 1);
        
        try {
          // Poll Seats
          const seatRes = await fetch(`${API_BASE}/sessions/${sessionId}/seats`);
          if (seatRes.ok) {
            const seatData = await seatRes.json();
            // Map backend schema to UI schema
            const mappedStudents = seatData.map(s => {
              const isCritical = s.status === 'alert' || s.status === 'critical' || s.peak_score >= 100 || s.score >= 100;
              const isWarning = s.status === 'accumulating' || s.status === 'warning' || s.score >= 40;
              return {
                id: s.seat_id,
                name: `Seat ${s.seat_id.split('-').pop() || s.seat_id}`,
                score: s.score || 0,
                peak_score: s.peak_score || 0,
                status: isCritical ? 'critical' : isWarning ? 'warning' : 'clear',
                occupied: s.occupied
              };
            });
            setStudents(mappedStudents);
          }

          // Poll Events
          const eventRes = await fetch(`${API_BASE}/sessions/${sessionId}/events`);
          if (eventRes.ok) {
            const eventData = await eventRes.json();
            const mappedLogs = eventData.map(e => ({
              id: e.event_id,
              studentName: `Candidate ${e.seat_id.split('-').pop() || e.seat_id}`,
              activity: e.reason,
              time: new Date(e.t_start * 1000).toLocaleTimeString(),
              date: new Date(e.t_start * 1000).toLocaleDateString(),
              severity: e.severity,
              clip_path: e.clip_path,
              thumb_path: e.thumb_path
            })).reverse(); // Newest first
            setLogs(mappedLogs);
          }
        } catch (err) {
          console.error("Polling error", err);
        }
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [view, sessionId]);

  // Fetch Timeline for Results
  useEffect(() => {
    if (view === 'results' && sessionId) {
      fetch(`${API_BASE}/sessions/${sessionId}/timeline`)
        .then(r => r.json())
        .then(data => setTimeline(data.seats || {}))
        .catch(console.error);
    }
  }, [view, sessionId]);


  const handleStopRequest = () => {
    setView('confirm-stop');
    setConfirmInput('');
  };

  const handleConfirmInput = (e) => {
    const val = e.target.value.toLowerCase();
    setConfirmInput(val);
    if (val === 'y') {
      setView('results');
    } else if (val === 'n') {
      setView('monitoring');
    }
  };

  // --------------------------------------------------------
  // SUB-COMPONENTS
  // --------------------------------------------------------

  const SetupView = () => (
    <div className="flex-1 flex flex-col items-center justify-center max-w-2xl mx-auto w-full p-8 animate-in fade-in zoom-in-95 duration-300">
      <div className="text-center mb-10">
        <h2 className="text-3xl font-bold text-slate-900 dark:text-zinc-100 mb-3 tracking-tight">Initialize Detection Engine</h2>
        <p className="text-slate-600 dark:text-zinc-400">Select your feed source to begin monitoring</p>
      </div>
      
      <div className="w-full bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl p-8 shadow-2xl relative">
        {isStarting && (
          <div className="absolute inset-0 bg-white dark:bg-zinc-900/80 backdrop-blur flex flex-col items-center justify-center z-10 rounded-xl">
            <Activity className="w-10 h-10 text-teal-500 animate-spin mb-4" />
            <p className="font-mono text-slate-700 dark:text-zinc-300 font-bold tracking-widest uppercase">Initializing System...</p>
          </div>
        )}
        
        <form onSubmit={handleStartLive} className="flex flex-col gap-8">
          {mode === 'live' ? (
            <div className="space-y-4">
              <label className="text-sm font-semibold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">RTSP Stream URL</label>
              <input 
                type="text" 
                placeholder="rtsp://admin:pass@camera.local/stream1" 
                required
                value={rtspUrl}
                onChange={e => setRtspUrl(e.target.value)}
                className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg p-4 text-slate-900 dark:text-zinc-100 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500 transition-all font-mono"
              />
            </div>
          ) : (
            <div className="space-y-4">
              <label className="text-sm font-semibold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Video File Upload</label>
              <input 
                type="file" 
                accept="video/*" 
                ref={fileInputRef} 
                className="hidden" 
                onChange={handleFileUpload} 
              />
              <div 
                onDragOver={preventDefaultDrag} 
                onDragEnter={preventDefaultDrag} 
                onDrop={handleDrop} 
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-300 dark:border-zinc-700 rounded-lg p-12 text-center hover:bg-slate-100 dark:bg-slate-100/50 dark:bg-zinc-800/50 hover:border-teal-500 transition-colors cursor-pointer group"
              >
                <IconUpload className="mx-auto h-8 w-8 text-slate-500 dark:text-zinc-500 group-hover:text-teal-400 mb-4 transition-colors" />
                <p className="text-slate-700 dark:text-zinc-300 font-medium">Drag & Drop recording file or click to browse</p>
                <p className="text-slate-500 dark:text-zinc-500 text-sm mt-1">MP4, MKV up to 4GB</p>
              </div>
            </div>
          )}

          {mode === 'live' && (
            <div className="pt-4 border-t border-slate-200 dark:border-zinc-800">
              <button type="submit" className="w-full bg-teal-500 hover:bg-teal-400 text-zinc-950 font-bold text-lg py-4 rounded-lg transition-colors shadow-[0_0_20px_rgba(20,184,166,0.3)]">
                ENGAGE SYSTEM
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );

  const MonitoringView = () => (
    <div className="flex-1 flex flex-col lg:flex-row gap-6 p-6 animate-in fade-in duration-300 h-full overflow-hidden">
      {/* Left: Feed Output */}
      <div className="flex-1 flex flex-col gap-4 min-h-0">
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl overflow-hidden flex-1 relative group">
          
          <div className="absolute inset-0 bg-slate-50 dark:bg-zinc-950 flex items-center justify-center overflow-hidden">
            <img 
              src={`${API_BASE}/stream/${sessionId}`} 
              alt="Live Detection Stream"
              className="w-full h-full object-contain opacity-90"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          </div>
          
          {/* OSD (On Screen Display) Overlays */}
          <div className="absolute top-4 left-4 flex gap-2">
            <span className="bg-rose-500 text-white text-xs font-bold px-2 py-1 rounded animate-pulse">REC</span>
            <span className="bg-slate-50 dark:bg-slate-50/80 dark:bg-zinc-950/80 backdrop-blur text-teal-400 font-mono text-xs px-2 py-1 rounded border border-slate-200 dark:border-zinc-800 border-l-teal-500 border-l-2">
              SANKET ENGINE v4.2
            </span>
          </div>
          
          <div className="absolute bottom-4 left-4 right-4 flex justify-between items-end">
            <div className="bg-slate-50 dark:bg-slate-50/80 dark:bg-zinc-950/80 backdrop-blur font-mono text-xs text-slate-600 dark:text-zinc-400 px-3 py-2 rounded border border-slate-200 dark:border-zinc-800">
              SESSION: {sessionId} | UPTIME: {elapsed}s
            </div>
            
            <button 
              onClick={handleStopRequest}
              className="bg-rose-500/10 hover:bg-rose-500 hover:text-white text-rose-500 border border-rose-500/50 px-4 py-2 rounded font-bold tracking-wider uppercase flex items-center gap-2 transition-all"
            >
              <IconStop /> Halt Detection
            </button>
          </div>
        </div>
      </div>

      {/* Right: Live Telemetry Sidebar */}
      <div className="w-full lg:w-[450px] flex flex-col gap-4 overflow-hidden h-full">
        
        {/* Top Half: Live Seating Grid */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl p-5 flex flex-col flex-1 overflow-y-auto">
          <div className="flex justify-between items-center mb-4 shrink-0">
            <h3 className="text-lg font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
              <Activity className="w-5 h-5 text-teal-500" /> YOLO Seating Grid
            </h3>
            <span className="text-xs font-mono text-slate-500 dark:text-zinc-500">{students.filter(s => s.status === 'caught' || s.status === 'critical').length} / {students.length} FLAGGED</span>
          </div>
          
          {students.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-slate-400 dark:text-zinc-600 italic text-sm">
              <Camera className="w-8 h-8 mb-2 opacity-50" />
              Scanning frame for candidates...
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3 auto-rows-max shrink-0">
              {students.map(student => (
                <div 
                  key={student.id} 
                  className={`
                    relative p-3 rounded-lg border flex flex-col items-center justify-center gap-1.5 transition-all duration-300
                    ${student.status === 'critical' ? 'bg-rose-950/40 border-rose-500/60 shadow-sm shadow-rose-500/20' : 
                      student.status === 'warning' ? 'bg-amber-950/40 border-amber-500/60' : 
                      'bg-slate-50 dark:bg-zinc-950/60 border-slate-200 dark:border-zinc-800'}
                  `}
                >
                  <div className="flex justify-between items-center w-full px-1">
                    <span className="text-[11px] font-bold text-slate-700 dark:text-zinc-300 tracking-wider truncate" title={student.name}>
                      {student.name}
                    </span>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-200 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400">
                      Peak: {Math.round(student.peak_score)}%
                    </span>
                  </div>
                  
                  <div className="text-2xl font-mono font-black tracking-tight" style={{
                    color: student.status === 'critical' ? '#f43f5e' : student.status === 'warning' ? '#f59e0b' : '#14b8a6'
                  }}>
                    {Math.round(student.score)}%
                  </div>

                  <span className={`text-[9px] font-bold uppercase tracking-wider ${
                    student.status === 'critical' ? 'text-rose-400' : 
                    student.status === 'warning' ? 'text-amber-400' : 'text-teal-400'
                  }`}>
                    {student.status === 'critical' ? 'Suspicious' : student.status === 'warning' ? 'Warning' : 'Calm'}
                  </span>
                  
                  {student.status === 'critical' && (
                    <div className="absolute inset-0 bg-rose-500/10 backdrop-blur-[1px] flex items-center justify-center border-2 border-rose-500 rounded-lg z-10">
                      <span className="bg-rose-500 text-white text-[10px] font-black uppercase px-2 py-1 rounded shadow-lg transform -rotate-12">
                        Disqualified
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Bottom Half: Detection Log */}
        <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl p-5 flex flex-col flex-1 overflow-hidden">
          <div className="flex items-center gap-2 mb-4 shrink-0">
            <AlertTriangle className="w-4 h-4 text-rose-500" />
            <h3 className="text-sm font-bold text-slate-700 dark:text-zinc-300 uppercase tracking-wider">Detection Log</h3>
          </div>
          
          <div className="flex-1 overflow-y-auto overflow-x-hidden space-y-3 pr-2">
            {logs.length === 0 ? (
              <div className="text-slate-400 dark:text-zinc-600 text-sm italic h-full flex items-center justify-center">
                Monitoring nominal... no severe infractions detected.
              </div>
            ) : (
              logs.map(log => (
                <div key={log.id} className={`bg-slate-50 dark:bg-zinc-950 border-l-2 p-3 rounded text-sm animate-in slide-in-from-right-4 duration-300 ${log.severity === 'critical' ? 'border-rose-500' : 'border-amber-500'}`}>
                  <div className="flex justify-between items-start mb-1">
                    <span className={`font-bold ${log.severity === 'critical' ? 'text-rose-400' : 'text-amber-400'}`}>{log.studentName}</span>
                    <span className="text-[10px] font-mono text-slate-500 dark:text-zinc-500">{log.time}</span>
                  </div>
                  <p className="text-slate-700 dark:text-zinc-300 font-medium">{log.activity}</p>
                  {log.clip_path ? (
                    <div className="mt-2 rounded overflow-hidden border border-slate-200 dark:border-zinc-800 bg-black">
                      <video
                        src={log.clip_path}
                        controls
                        preload="metadata"
                        className="w-full aspect-video object-contain"
                      />
                    </div>
                  ) : log.thumb_path ? (
                    <a href={log.thumb_path} target="_blank" rel="noopener noreferrer" className="mt-2 block rounded overflow-hidden border border-slate-200 dark:border-zinc-800 cursor-pointer hover:opacity-80 transition-opacity bg-zinc-900">
                      <img src={log.thumb_path} alt="Evidence" className="w-full aspect-video object-contain" />
                    </a>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );

  const ConfirmStopView = () => (
    <div className="absolute inset-0 bg-slate-50 dark:bg-slate-50/80 dark:bg-zinc-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl p-8 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200">
        <div className="flex items-center gap-4 text-rose-500 mb-6">
          <IconAlert />
          <h2 className="text-xl font-bold">Halt Detection Sequence?</h2>
        </div>
        <p className="text-slate-600 dark:text-zinc-400 mb-8 leading-relaxed">
          You are about to terminate the current monitoring session. All telemetry will be finalized.
        </p>
        <div className="space-y-3">
          <label className="text-sm font-mono text-slate-500 dark:text-zinc-500 uppercase">Print y/n to confirm</label>
          <input 
            type="text" 
            autoFocus
            maxLength={1}
            value={confirmInput}
            onChange={handleConfirmInput}
            className="w-full bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg p-4 text-slate-900 dark:text-zinc-100 focus:outline-none focus:border-rose-500 focus:ring-1 focus:ring-rose-500 text-center text-xl font-mono font-bold uppercase transition-all"
            placeholder="_"
          />
        </div>
      </div>
    </div>
  );

  const ResultsView = () => {
    const flaggedCount = students.filter(s => s.status === 'caught' || s.status === 'critical').length;
    
    return (
      <div className="flex-1 overflow-y-auto p-6 md:p-10 animate-in fade-in slide-in-from-bottom-8 duration-500">
        <div className="max-w-5xl mx-auto">
          
          <div className="flex items-end justify-between mb-10 border-b border-slate-200 dark:border-zinc-800 pb-6">
            <div>
              <h2 className="text-3xl font-black text-slate-900 dark:text-zinc-100 uppercase tracking-tight">Session Report</h2>
              <p className="text-slate-600 dark:text-zinc-400 mt-2 font-mono text-sm">DURATION: {elapsed}s // ID: {sessionId}</p>
            </div>
            <button 
              onClick={() => { setView('setup'); setElapsed(0); setSessionId(null); }}
              className="bg-slate-100 dark:bg-zinc-800 hover:bg-slate-200 dark:bg-zinc-700 text-slate-800 dark:text-zinc-200 px-4 py-2 rounded-lg font-medium transition-colors text-sm"
            >
              Start New Session
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
            <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl p-6">
              <p className="text-slate-500 dark:text-zinc-500 text-sm font-bold uppercase tracking-wider mb-2">Total Candidates</p>
              <p className="text-4xl font-light text-slate-900 dark:text-zinc-100">{students.length}</p>
            </div>
            <div className="bg-white dark:bg-zinc-900 border border-rose-500/30 rounded-xl p-6 relative overflow-hidden">
              <div className="absolute right-0 top-0 w-2 h-full bg-rose-500"></div>
              <p className="text-slate-500 dark:text-zinc-500 text-sm font-bold uppercase tracking-wider mb-2">Flagged</p>
              <p className="text-4xl font-light text-rose-500">{flaggedCount}</p>
            </div>
            <div className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl p-6">
              <p className="text-slate-500 dark:text-zinc-500 text-sm font-bold uppercase tracking-wider mb-2">System Status</p>
              <p className="text-2xl font-light text-teal-400 mt-2 flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-teal-400"></span> Concluded
              </p>
            </div>
          </div>

          <h3 className="text-xl font-bold text-slate-900 dark:text-zinc-100 mb-6 flex items-center gap-2">
            Telemetry Graphs
          </h3>

          <div className="space-y-4">
            {students.map(student => {
              const history = timeline[student.id] || [];
              const isFlagged = student.status === 'caught' || student.status === 'critical';
              
              return (
                <div key={student.id} className="bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl p-5 flex flex-col md:flex-row items-start md:items-center gap-6">
                  
                  <div className="w-48 shrink-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h4 className="font-bold text-slate-800 dark:text-zinc-200">{student.name}</h4>
                      {isFlagged && <span className="bg-rose-500/20 text-rose-400 text-[10px] font-bold px-2 py-0.5 rounded uppercase border border-rose-500/20">Caught</span>}
                    </div>
                    <p className="text-xs font-mono text-slate-500 dark:text-zinc-500">Peak Suspicion: {Math.round(student.peak_score || student.score)}%</p>
                  </div>

                  {/* Micro Chart */}
                  <div className="flex-1 w-full h-16 flex items-end gap-[2px] bg-slate-50 dark:bg-slate-50/50 dark:bg-zinc-950/50 rounded p-2 border border-slate-200 dark:border-slate-200/50 dark:border-zinc-800/50 overflow-hidden">
                    {history.length > 0 ? history.slice(-100).map((pt, i) => {
                      const score = pt.score;
                      const isDanger = score > 85;
                      const isWarning = score > 50 && !isDanger;
                      return (
                        <div 
                          key={i} 
                          className={`flex-1 min-w-[2px] rounded-t-sm ${isDanger ? 'bg-rose-500' : isWarning ? 'bg-amber-500' : 'bg-teal-500/40'}`}
                          style={{ height: `${Math.max(2, score)}%` }}
                        ></div>
                      );
                    }) : (
                      <div className="w-full h-full flex items-center justify-center text-xs text-slate-400 dark:text-zinc-600 font-mono">No timeline data available</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

        </div>
      </div>
    );
  };

  return (
    <div className="h-screen bg-slate-50 dark:bg-zinc-950 flex flex-col font-sans text-slate-900 dark:text-zinc-100 selection:bg-teal-500/30 overflow-hidden">
      {/* Dynamic Hotbar / Navbar */}
      <header className="h-16 border-b border-slate-200 dark:border-zinc-800 bg-white dark:bg-white/50 dark:bg-zinc-900/50 flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-teal-500 flex items-center justify-center text-zinc-950 font-black tracking-tighter">S</div>
          <h1 className="font-bold text-lg tracking-widest uppercase text-slate-900 dark:text-zinc-100">Sanket<span className="text-teal-500 font-black">.AI</span></h1>
        </div>
        
        {/* Only show source toggles during setup */}
        {view === 'setup' && (
          <div className="flex bg-slate-50 dark:bg-zinc-950 rounded-lg p-1 border border-slate-200 dark:border-zinc-800">
            <button 
              onClick={() => setMode('live')}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${mode === 'live' ? 'bg-slate-100 dark:bg-zinc-800 text-teal-400 shadow-sm' : 'text-slate-500 dark:text-zinc-500 hover:text-slate-700 dark:text-zinc-300'}`}
            >
              <IconCamera /> Live Camera
            </button>
            <button 
              onClick={() => setMode('upload')}
              className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${mode === 'upload' ? 'bg-slate-100 dark:bg-zinc-800 text-teal-400 shadow-sm' : 'text-slate-500 dark:text-zinc-500 hover:text-slate-700 dark:text-zinc-300'}`}
            >
              <IconUpload /> Upload Video
            </button>
          </div>
        )}

{view !== 'setup' && (
          <div className="flex items-center gap-2 text-xs font-mono text-slate-500 dark:text-zinc-500 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 px-3 py-1.5 rounded-full">
            <span className={`w-2 h-2 rounded-full ${view === 'monitoring' ? 'bg-teal-500 animate-pulse' : 'bg-slate-400 dark:bg-zinc-600'}`}></span>
            {view === 'monitoring' ? 'ACTIVE MONITORING' : 'STANDBY'}
          </div>
        )}
        
        <button 
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="p-2 rounded-full hover:bg-slate-200 dark:hover:bg-zinc-800 transition-colors ml-4 text-slate-700 dark:text-zinc-300"
        >
          {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
        </button>
      </header>

      {/* Main Content Area */}
      {view === 'setup' && <SetupView />}
      {view === 'monitoring' && <MonitoringView />}
      {view === 'results' && <ResultsView />}
      
      {/* Overlays */}
      {view === 'confirm-stop' && (
        <>
          <MonitoringView />
          <ConfirmStopView />
        </>
      )}

    </div>
  );
}
