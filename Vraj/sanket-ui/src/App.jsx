import React, { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import LiveMonitorView from './components/LiveMonitorView';
import SeatingMatrixView from './components/SeatingMatrixView';
import EvidenceArchiveView from './components/EvidenceArchiveView';
import StaffSupervisionView from './components/StaffSupervisionView';
import AnalyticsReportView from './components/AnalyticsReportView';
import CandidateDrawer from './components/CandidateDrawer';
import ClipPlayerModal from './components/ClipPlayerModal';
import HtmlReportModal from './components/HtmlReportModal';
import SessionModal from './components/SessionModal';
import { playAudioChime } from './utils/audio';

const API_BASE = '/api';

export default function App() {
  // Navigation & UI State
  const [activeTab, setActiveTab] = useState('live'); // live, grid, events, staff, analytics
  const [theme, setTheme] = useState('dark'); // dark, light
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [deviceInfo, setDeviceInfo] = useState('AUTO');

  // Core Data State
  const [sessionsList, setSessionsList] = useState([]);
  const [session, setSession] = useState(null);
  const [seats, setSeats] = useState([]);
  const [events, setEvents] = useState([]);
  const [staffList, setStaffList] = useState([]);
  const [staffEvents, setStaffEvents] = useState([]);
  const [timelineData, setTimelineData] = useState({ timestamps: [], seats: {} });

  // Modals & Drawers
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [activeClipEvent, setActiveClipEvent] = useState(null);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [isNewSessionModalOpen, setIsNewSessionModalOpen] = useState(false);
  const [isHalting, setIsHalting] = useState(false);

  const lastEventCountRef = useRef(0);
  const pollTimerRef = useRef(null);

  // Sync theme class on document element
  useEffect(() => {
    document.documentElement.classList.remove('theme-dark', 'theme-light');
    document.documentElement.classList.add(`theme-${theme}`);
  }, [theme]);

  // Initial Load
  useEffect(() => {
    fetchHealth();
    loadSessions(true);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        const data = await res.json();
        setDeviceInfo(data.device?.toUpperCase() || 'AUTO');
      }
    } catch (e) {
      console.warn('Health check error:', e);
    }
  };

  const loadSessions = async (autoSelectLatest = false) => {
    try {
      const res = await fetch(`${API_BASE}/sessions`);
      if (res.ok) {
        const list = await res.json();
        setSessionsList(list);

        if (autoSelectLatest && list.length > 0) {
          const running = list.find(s => s.state === 'running' || s.state === 'initializing');
          const target = running || list[0];
          setSession(target);
        }
      }
    } catch (e) {
      console.warn('Load sessions error:', e);
    }
  };

  // Fetch telemetry
  const fetchSessionTelemetry = useCallback(async (sessionId) => {
    if (!sessionId) return;
    try {
      // 1. Session Status
      const sessRes = await fetch(`${API_BASE}/sessions/${sessionId}`);
      if (sessRes.ok) {
        const sessData = await sessRes.json();
        setSession(sessData);
      }

      // 2. Seats
      const seatsRes = await fetch(`${API_BASE}/sessions/${sessionId}/seats`);
      if (seatsRes.ok) {
        const seatsData = await seatsRes.json();
        setSeats(seatsData);

        if (selectedCandidate) {
          const updatedCand = seatsData.find(s => s.seat_id === selectedCandidate.seat_id);
          if (updatedCand) setSelectedCandidate(updatedCand);
        }
      }

      // 3. Events
      const eventsRes = await fetch(`${API_BASE}/sessions/${sessionId}/events`);
      if (eventsRes.ok) {
        const eventsData = await eventsRes.json();
        const sortedEvents = [...eventsData].reverse();
        setEvents(sortedEvents);

        if (sortedEvents.length > lastEventCountRef.current && lastEventCountRef.current !== 0) {
          const latest = sortedEvents[0];
          if (soundEnabled) {
            playAudioChime(latest?.severity === 'critical' ? 'critical' : 'warning');
          }
        }
        lastEventCountRef.current = sortedEvents.length;
      }

      // 4. Staff
      const staffRes = await fetch(`${API_BASE}/sessions/${sessionId}/staff`);
      if (staffRes.ok) {
        const staffData = await staffRes.json();
        setStaffList(staffData);
      }

      // 5. Staff Events
      const staffEvRes = await fetch(`${API_BASE}/sessions/${sessionId}/staff/events`);
      if (staffEvRes.ok) {
        const staffEvData = await staffEvRes.json();
        setStaffEvents(staffEvData);
      }

      // 6. Timeline
      const timelineRes = await fetch(`${API_BASE}/sessions/${sessionId}/timeline`);
      if (timelineRes.ok) {
        const timelineResData = await timelineRes.json();
        setTimelineData(timelineResData);
      }

    } catch (err) {
      console.warn('Telemetry fetch error:', err);
    }
  }, [selectedCandidate, soundEnabled]);

  // Polling loop
  useEffect(() => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);

    if (session?.session_id) {
      fetchSessionTelemetry(session.session_id);

      if (session.state === 'running' || session.state === 'initializing') {
        pollTimerRef.current = setInterval(() => {
          fetchSessionTelemetry(session.session_id);
        }, 1000);
      }
    }

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [session?.session_id, session?.state, fetchSessionTelemetry]);

  // Handle Session Selection
  const handleSelectSession = (sessionId) => {
    const found = sessionsList.find(s => s.session_id === sessionId);
    if (found) {
      setSession(found);
      lastEventCountRef.current = 0;
      fetchSessionTelemetry(sessionId);
    }
  };

  // Start New Session
  const handleStartSession = async (sourcePath) => {
    try {
      const res = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: sourcePath, config_overrides: {} })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to start session.');
      }

      const newSess = await res.json();
      setSession(newSess);
      setSeats([]);
      setEvents([]);
      lastEventCountRef.current = 0;
      setActiveTab('live');
      await loadSessions();
      if (soundEnabled) playAudioChime('success');
      return true;
    } catch (err) {
      console.error(err);
      throw err;
    }
  };

  // Upload Video File and Start Session
  const handleUploadAndStart = async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const upRes = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData
      });

      if (!upRes.ok) {
        const err = await upRes.json();
        throw new Error(err.detail || 'Video upload failed.');
      }

      const upData = await upRes.json();
      return await handleStartSession(upData.source_path);
    } catch (err) {
      console.error(err);
      throw err;
    }
  };

  // Halt Session
  const handleStopSession = async () => {
    if (!session?.session_id) return;
    if (!window.confirm("Halt examination invigilation and finalize telemetry records?")) return;

    setIsHalting(true);
    try {
      const res = await fetch(`${API_BASE}/sessions/${session.session_id}/stop`, {
        method: 'POST'
      });
      if (res.ok) {
        setSession(prev => prev ? { ...prev, state: 'done' } : null);
        if (soundEnabled) playAudioChime('halt');
        setTimeout(() => {
          fetchSessionTelemetry(session.session_id);
          loadSessions();
        }, 300);
      }
    } catch (err) {
      console.warn("Halt error:", err);
    } finally {
      setIsHalting(false);
    }
  };

  const candidateSpecificEvents = selectedCandidate
    ? events.filter(e => e.seat_id === selectedCandidate.seat_id)
    : [];

  return (
    <div className="h-screen w-screen flex bg-[var(--bg-app)] text-[var(--text-primary)] font-sans overflow-hidden p-6 gap-6">

      {/* Neumorphic Left Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        session={session}
        deviceInfo={deviceInfo}
      />

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden gap-6">

        {/* Header Bar */}
        <Navbar
          session={session}
          sessionsList={sessionsList}
          onSelectSession={handleSelectSession}
          soundEnabled={soundEnabled}
          setSoundEnabled={setSoundEnabled}
          theme={theme}
          setTheme={setTheme}
          onOpenNewSessionModal={() => setIsNewSessionModalOpen(true)}
          onRefresh={() => {
            if (session?.session_id) fetchSessionTelemetry(session.session_id);
            loadSessions();
          }}
        />

        {/* Dynamic Viewports */}
        <main className="flex-1 flex flex-col min-h-0 overflow-hidden relative">
          {activeTab === 'live' && (
            <LiveMonitorView
              session={session}
              seats={seats}
              events={events}
              onSelectCandidate={(cand) => setSelectedCandidate(cand)}
              onOpenClipModal={(evt) => setActiveClipEvent(evt)}
              onStopSession={handleStopSession}
              isHalting={isHalting}
            />
          )}

          {activeTab === 'grid' && (
            <SeatingMatrixView
              seats={seats}
              onSelectCandidate={(cand) => setSelectedCandidate(cand)}
            />
          )}

          {activeTab === 'events' && (
            <EvidenceArchiveView
              events={events}
              onOpenClipModal={(evt) => setActiveClipEvent(evt)}
            />
          )}

          {activeTab === 'staff' && (
            <StaffSupervisionView
              session={session}
              staffList={staffList}
              staffEvents={staffEvents}
            />
          )}

          {activeTab === 'analytics' && (
            <AnalyticsReportView
              session={session}
              seats={seats}
              events={events}
              timelineData={timelineData}
              onOpenReportModal={() => setIsReportModalOpen(true)}
            />
          )}
        </main>

      </div>

      {/* Slide-Over Candidate Drawer */}
      {selectedCandidate && (
        <CandidateDrawer
          candidate={selectedCandidate}
          candidateEvents={candidateSpecificEvents}
          onClose={() => setSelectedCandidate(null)}
          onOpenClipModal={(evt) => setActiveClipEvent(evt)}
        />
      )}

      {/* Video Evidence Clip Modal */}
      {activeClipEvent && (
        <ClipPlayerModal
          event={activeClipEvent}
          onClose={() => setActiveClipEvent(null)}
        />
      )}

      {/* HTML Report Modal */}
      {isReportModalOpen && session && (
        <HtmlReportModal
          sessionId={session.session_id}
          onClose={() => setIsReportModalOpen(false)}
        />
      )}

      {/* Feed Source Modal */}
      {isNewSessionModalOpen && (
        <SessionModal
          onClose={() => setIsNewSessionModalOpen(false)}
          onStartSession={handleStartSession}
          onUploadAndStart={handleUploadAndStart}
        />
      )}

    </div>
  );
}
