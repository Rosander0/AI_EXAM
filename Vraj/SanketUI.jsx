import React, { useState } from 'react';

// Lightweight inline SVG icons
const UploadIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
    <polyline points="17 8 12 3 7 8"></polyline>
    <line x1="12" y1="3" x2="12" y2="15"></line>
  </svg>
);

const CameraIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"></path>
    <circle cx="12" cy="13" r="3"></circle>
  </svg>
);

// Literal rubber-stamp graphic
const StampIcon = ({ type, className = '' }) => {
  const isFlagged = type === 'flagged';
  const color = isFlagged ? '#B0392F' : '#A9822E';
  const text = isFlagged ? 'FLAGGED' : 'VERIFIED';
  const rotation = isFlagged ? '-12deg' : '8deg';

  return (
    <div 
      className={`relative inline-flex items-center justify-center stamp-impact ${className}`} 
      style={{ 
        transform: `rotate(${rotation})`,
        color: color 
      }}
    >
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full" style={{ fill: 'none', stroke: color, strokeWidth: 3, strokeDasharray: '6 2 4 3 8 2' }}>
        <circle cx="50" cy="50" r="46" />
        <circle cx="50" cy="50" r="39" strokeWidth="1.5" strokeDasharray="3 4 5 2" />
      </svg>
      <span className="font-zilla font-bold text-[0.6rem] tracking-widest uppercase mt-0.5">{text}</span>
    </div>
  );
};

// Torn-ticket-stub perforated card
const TicketCard = ({ children, className = '', direction = 'left' }) => {
  const isLeft = direction === 'left';
  return (
    <div className={`relative bg-transparent border-2 border-[#C9CDBE] p-6 md:p-8 ${className}`}>
      <div className={`absolute top-0 bottom-0 w-3 flex flex-col justify-evenly py-2 ${isLeft ? '-left-1.5' : '-right-1.5'}`}>
        {Array.from({ length: 16 }).map((_, i) => (
          <div key={i} className={`w-3 h-3 rounded-full bg-[#EAEDE2] border border-[#C9CDBE] ${isLeft ? 'border-l-transparent' : 'border-r-transparent'}`}></div>
        ))}
      </div>
      {children}
    </div>
  );
};

export default function SanketUI() {
  const [dragActive, setDragActive] = useState(false);
  const [uploadState, setUploadState] = useState('idle'); // idle, processing, done
  const [rtspUrl, setRtspUrl] = useState('');
  
  // Handlers for drag & drop
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setUploadState('processing');
      setTimeout(() => setUploadState('done'), 2000);
    }
  };

  const handleConnect = (e) => {
    e.preventDefault();
    if (rtspUrl) {
      setUploadState('processing');
      setTimeout(() => setUploadState('done'), 1500);
    }
  };

  const detections = [
    { id: '1', timestamp: '14:02:11', seat: 'SEAT-12', behaviour: 'Multiple faces detected', confidence: '0.92', severity: 'flagged' },
    { id: '2', timestamp: '14:05:43', seat: 'SEAT-04', behaviour: 'Looked away from screen', confidence: '0.64', severity: 'verified' },
    { id: '3', timestamp: '14:12:01', seat: 'SEAT-19', behaviour: 'Mobile phone detected', confidence: '0.98', severity: 'flagged' },
    { id: '4', timestamp: '14:15:33', seat: 'SEAT-12', behaviour: 'Audio spike (Speech)', confidence: '0.88', severity: 'flagged' },
    { id: '5', timestamp: '14:22:10', seat: 'SEAT-08', behaviour: 'Not present in frame', confidence: '0.95', severity: 'verified' },
  ];

  return (
    <div className="min-h-screen p-4 md:p-8 flex flex-col selection:bg-[#B0392F] selection:text-[#EAEDE2]" style={{ backgroundColor: '#EAEDE2', color: '#1C2B3A' }}>
      <style dangerouslySetInnerHTML={{ __html: `
        @import url('https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@400;600;700&family=Inter:wght@400;500;600&family=VT323&display=swap');
        
        .font-zilla { font-family: 'Zilla Slab', serif; }
        .font-inter { font-family: 'Inter', sans-serif; }
        .font-vt { font-family: 'VT323', monospace; }

        @keyframes stamp-impact {
          0% { transform: scale(1.8) rotate(0deg); opacity: 0; }
          40% { transform: scale(0.95) rotate(-15deg); opacity: 1; }
          100% { transform: scale(1) rotate(-12deg); opacity: 0.9; }
        }
        .stamp-impact {
          animation: stamp-impact 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
        }
        @media (prefers-reduced-motion: reduce) {
          .stamp-impact { animation: none; opacity: 0.9; }
        }
        
        /* Ruled ledger table styling */
        .ledger-row {
          border-bottom: 1px solid #C9CDBE;
          transition: background-color 0.2s;
        }
        .ledger-row:hover {
          background-color: rgba(201, 205, 190, 0.3);
        }
        
        /* Focus styles for inputs */
        input:focus, button:focus {
          outline: 2px solid #1C2B3A;
          outline-offset: 2px;
        }
      `}} />

      <div className="max-w-6xl mx-auto w-full">
        {/* Header - Letterhead Style */}
        <header className="border-b-4 border-double border-[#1C2B3A] pb-6 mb-8 flex flex-col sm:flex-row sm:justify-between sm:items-end gap-6">
          <div>
            <h1 className="font-zilla text-5xl md:text-6xl font-bold tracking-tight uppercase" style={{ color: '#1C2B3A' }}>Sanket</h1>
            <p className="font-zilla text-lg uppercase tracking-widest mt-1 opacity-80 border-t border-[#1C2B3A] pt-1 inline-block">Exam Integrity Monitor</p>
          </div>
          <div className="text-left sm:text-right flex flex-col items-start sm:items-end">
            <div className="font-vt text-xl border-2 border-[#A9822E] text-[#A9822E] p-2 px-4 transform sm:rotate-2 inline-block stamp-impact shadow-sm" style={{ animationDelay: '0.2s' }}>
              SESSION: LIVE
              <br/>
              DATE: {new Date().toISOString().split('T')[0]}
            </div>
          </div>
        </header>

        {/* Hero: Seating Chart Visual */}
        <section className="mb-12">
          <h2 className="font-zilla text-2xl font-bold uppercase mb-4 tracking-wider flex items-center gap-3">
            <span className="w-5 h-5 bg-[#1C2B3A] inline-block"></span>
            Seating Registry (Hall B)
          </h2>
          
          <div className="border border-[#1C2B3A] p-2 md:p-4 bg-transparent relative overflow-hidden">
            {/* Subtle ruled background lines */}
            <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: 'linear-gradient(#C9CDBE 1px, transparent 1px)', backgroundSize: '100% 2rem', opacity: 0.3 }}></div>
            
            <div className="grid grid-cols-5 md:grid-cols-10 gap-2 md:gap-3 relative z-10">
              {Array.from({ length: 30 }).map((_, i) => {
                const seatId = i + 1;
                const isFlagged = [12, 19].includes(seatId);
                const isVerified = [4, 8].includes(seatId);
                
                return (
                  <div key={seatId} className="relative aspect-square border border-[#C9CDBE] flex items-center justify-center bg-[#EAEDE2] p-1 transition-colors hover:border-[#1C2B3A]">
                    <span className="font-vt text-sm opacity-60 absolute top-1 left-1">{seatId.toString().padStart(2, '0')}</span>
                    {isFlagged && (
                      <StampIcon type="flagged" className="w-10 h-10 absolute z-10" />
                    )}
                    {isVerified && (
                      <StampIcon type="verified" className="w-8 h-8 absolute z-10 opacity-70" />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Ingest Section: Register Page Halves */}
        <section className="mb-16 flex flex-col md:flex-row gap-8 relative">
          {/* Live Camera Connect */}
          <TicketCard direction="left" className="flex-1 border-dashed">
            <div className="flex items-center gap-3 mb-8 border-b-2 border-[#1C2B3A] pb-2 inline-flex">
              <CameraIcon />
              <h3 className="font-zilla text-xl font-bold uppercase tracking-widest">Connect Live Feed</h3>
            </div>
            
            <form onSubmit={handleConnect} className="space-y-6">
              <div>
                <label className="block mb-2 font-inter text-sm font-semibold uppercase tracking-widest text-[#1C2B3A]">RTSP URL / Camera ID</label>
                <input 
                  type="text" 
                  value={rtspUrl}
                  onChange={(e) => setRtspUrl(e.target.value)}
                  placeholder="rtsp://camera.local:554/stream"
                  className="w-full bg-transparent font-vt text-xl border-b-2 border-[#1C2B3A] p-2 px-0 focus:outline-none focus:border-[#B0392F] transition-colors placeholder:opacity-30"
                />
              </div>
              <div className="flex flex-col sm:flex-row gap-6">
                <div className="flex-1">
                  <label className="block mb-2 font-inter text-sm font-semibold uppercase tracking-widest text-[#1C2B3A]">Room Label</label>
                  <input 
                    type="text" 
                    placeholder="e.g. Hall B"
                    className="w-full bg-transparent font-vt text-xl border-b-2 border-[#1C2B3A] p-2 px-0 focus:outline-none focus:border-[#B0392F] transition-colors placeholder:opacity-30"
                  />
                </div>
                <button 
                  type="submit"
                  className="self-start sm:self-end font-zilla font-bold text-lg uppercase tracking-widest border-2 border-[#1C2B3A] px-8 py-2 hover:bg-[#1C2B3A] hover:text-[#EAEDE2] active:bg-[#B0392F] active:border-[#B0392F] transition-colors"
                >
                  Engage
                </button>
              </div>
            </form>
          </TicketCard>

          {/* Upload Recording */}
          <TicketCard direction="right" className="flex-1 border-dashed">
            <div className="flex items-center gap-3 mb-8 border-b-2 border-[#1C2B3A] pb-2 inline-flex">
              <UploadIcon />
              <h3 className="font-zilla text-xl font-bold uppercase tracking-widest">Upload Recording</h3>
            </div>
            
            <div 
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`
                border-2 border-dashed transition-colors p-8 flex flex-col items-center justify-center text-center min-h-[200px]
                ${dragActive ? 'border-[#1C2B3A] bg-[rgba(28,43,58,0.03)]' : 'border-[#C9CDBE] hover:border-[#1C2B3A]'}
                ${uploadState === 'processing' ? 'animate-pulse' : ''}
              `}
            >
              {uploadState === 'idle' && (
                <>
                  <p className="font-zilla text-xl font-bold mb-2">Drag & Drop Footage</p>
                  <p className="font-vt text-lg opacity-70">MP4, MKV, AVI (Max 5GB)</p>
                  <div className="my-5 border-t border-[#C9CDBE] w-24 mx-auto"></div>
                  <button className="font-vt text-xl uppercase tracking-wider underline hover:text-[#B0392F] focus:text-[#B0392F] transition-colors">
                    Browse Files
                  </button>
                </>
              )}
              {uploadState === 'processing' && (
                <p className="font-vt text-2xl uppercase tracking-widest flex items-center gap-3">
                  <span className="w-3 h-3 bg-[#1C2B3A] rounded-full animate-ping"></span>
                  Processing Tape...
                </p>
              )}
              {uploadState === 'done' && (
                <div className="flex flex-col items-center gap-2">
                  <StampIcon type="verified" className="w-16 h-16" />
                  <p className="font-vt text-xl uppercase tracking-widest text-[#A9822E] mt-4">Tape Accepted</p>
                </div>
              )}
            </div>
          </TicketCard>
        </section>

        {/* Detection Log - Ledger Table */}
        <section className="mb-12">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-6 border-b-2 border-[#1C2B3A] pb-2 gap-2">
            <h2 className="font-zilla text-2xl font-bold uppercase tracking-wider flex items-center gap-3">
              <span className="w-5 h-5 border-2 border-[#1C2B3A] inline-block"></span>
              Detection Log
            </h2>
            <span className="font-vt text-lg tracking-widest">PAGE 1 OF 1</span>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[600px]">
              <thead>
                <tr className="font-inter text-xs font-semibold uppercase tracking-widest opacity-70 border-b border-[#1C2B3A]">
                  <th className="py-3 px-3">Timestamp</th>
                  <th className="py-3 px-3">Seat ID</th>
                  <th className="py-3 px-3">Behaviour</th>
                  <th className="py-3 px-3 text-right">Confidence</th>
                  <th className="py-3 px-3 text-center w-32">Severity</th>
                </tr>
              </thead>
              <tbody className="font-vt text-xl">
                {detections.map((d) => (
                  <tr key={d.id} className="ledger-row group">
                    <td className="py-5 px-3 opacity-80">{d.timestamp}</td>
                    <td className="py-5 px-3">{d.seat}</td>
                    <td className="py-5 px-3 font-inter text-base font-medium tracking-wide group-hover:text-[#B0392F] transition-colors">{d.behaviour}</td>
                    <td className="py-5 px-3 text-right opacity-80">{d.confidence}</td>
                    <td className="py-2 px-3 flex justify-center items-center min-h-[5rem]">
                      {d.severity === 'flagged' ? (
                        <StampIcon type="flagged" className="w-14 h-14" />
                      ) : (
                        <StampIcon type="verified" className="w-12 h-12 opacity-70" />
                      )}
                    </td>
                  </tr>
                ))}
                {/* Empty ledger rows for visual completion */}
                {Array.from({ length: 4 }).map((_, i) => (
                  <tr key={`empty-${i}`} className="ledger-row">
                    <td className="py-6 px-3 text-transparent">-</td>
                    <td className="py-6 px-3"></td>
                    <td className="py-6 px-3"></td>
                    <td className="py-6 px-3"></td>
                    <td className="py-6 px-3"></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Footer - Form Fine Print */}
        <footer className="mt-16 pt-6 border-t-2 border-[#1C2B3A] flex flex-col md:flex-row justify-between items-center font-vt text-base opacity-80 uppercase tracking-widest gap-4">
          <p>FORM NO. S-420 // SANKET MONITORING SYSTEMS</p>
          <div className="flex gap-2">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="w-2 h-2 border border-[#1C2B3A] rounded-sm transform rotate-45"></div>
            ))}
          </div>
          <p>FOR AUTHORIZED PERSONNEL ONLY</p>
        </footer>
      </div>
    </div>
  );
}
