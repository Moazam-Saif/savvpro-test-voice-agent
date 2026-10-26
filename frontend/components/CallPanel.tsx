"use client";

import React from "react";
import { CallStatus } from "../hooks/useCall";

interface CallPanelProps {
  status: CallStatus;
  isListening: boolean;
  isSpeaking: boolean;
  isRetrying: boolean;
  locale: string;
  onLocaleChange: (loc: string) => void;
  onStartCall: () => void;
  onEndCall: () => void;
  onToggleMic: () => void;
}

export function CallPanel({
  status,
  isListening,
  isSpeaking,
  isRetrying,
  locale,
  onLocaleChange,
  onStartCall,
  onEndCall,
  onToggleMic,
}: CallPanelProps) {
  const isCallActive = status !== "idle" && status !== "ended";

  const getStatusBadge = () => {
    if (isRetrying) {
      return <span className="status-badge retry">Retrying...</span>;
    }
    if (isSpeaking) {
      return <span className="status-badge speaking">Speaking (Assistant)</span>;
    }
    if (isListening) {
      return <span className="status-badge listening">Listening (Mic On)</span>;
    }
    if (status === "thinking") {
      return <span className="status-badge thinking">Thinking...</span>;
    }
    if (status === "ended") {
      return <span className="status-badge ended">Call Ended</span>;
    }
    return <span className="status-badge idle">Ready to Call</span>;
  };

  return (
    <div className="card call-panel">
      <div className="call-header">
        <div>
          <h2>Call Bright Smile Dental</h2>
          <p className="subtitle">Deterministic rule-based appointment assistant</p>
        </div>
        <div className="locale-selector">
          <label htmlFor="locale">Accent / Locale:</label>
          <select
            id="locale"
            value={locale}
            onChange={(e) => onLocaleChange(e.target.value)}
            disabled={isCallActive}
          >
            <option value="en-US">English (US - en-US)</option>
            <option value="en-GB">English (UK - en-GB)</option>
            <option value="en-IN">English (India - en-IN)</option>
          </select>
        </div>
      </div>

      <div className="call-controls">
        {!isCallActive ? (
          <button className="btn btn-primary" onClick={onStartCall}>
            📞 Start Call
          </button>
        ) : (
          <div className="active-controls">
            <button
              className={`btn btn-mic ${isListening ? "active" : ""}`}
              onClick={onToggleMic}
              title={isListening ? "Mute mic" : "Unmute mic"}
            >
              {isListening ? "🎙️ Mic Active" : "🔇 Mic Muted"}
            </button>
            <button className="btn btn-danger" onClick={onEndCall}>
              ⏹️ End Call
            </button>
          </div>
        )}
        <div className="status-container">{getStatusBadge()}</div>
      </div>
    </div>
  );
}
