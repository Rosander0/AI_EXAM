import React, { useEffect } from 'react';
import { X, FileText, Download, Printer } from 'lucide-react';

export default function HtmlReportModal({
  sessionId,
  onClose
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!sessionId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      
      <div className="w-full max-w-6xl h-[90vh] bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-2xl shadow-2xl overflow-hidden flex flex-col animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-surface)] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[var(--bg-card)] text-amber-500 border border-[var(--border-subtle)] flex items-center justify-center">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[var(--text-primary)] font-mono">
                Official Invigilation Report
              </h3>
              <p className="text-[11px] text-[var(--text-muted)] font-mono">
                Session: {sessionId}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <a
              href={`/api/sessions/${sessionId}/report.html`}
              target="_blank"
              rel="noopener noreferrer"
              className="px-3.5 py-1.5 rounded-xl bg-[var(--bg-card)] hover:bg-[var(--bg-hover)] text-[var(--text-primary)] text-xs font-mono font-semibold transition-colors flex items-center gap-1.5 border border-[var(--border-subtle)]"
            >
              <Printer className="w-3.5 h-3.5" /> Open / Print
            </a>

            <a
              href={`/api/sessions/${sessionId}/report.html`}
              download={`report_${sessionId}.html`}
              className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white text-xs font-mono font-semibold transition-colors flex items-center gap-1.5 shadow-sm"
            >
              <Download className="w-3.5 h-3.5" /> Download HTML
            </a>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg bg-[var(--bg-surface)] hover:bg-[var(--bg-hover)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors ml-2"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Report Frame */}
        <div className="flex-1 bg-white">
          <iframe
            src={`/api/sessions/${sessionId}/report.html`}
            title="Invigilation Report"
            className="w-full h-full border-0"
          />
        </div>

      </div>

    </div>
  );
}
