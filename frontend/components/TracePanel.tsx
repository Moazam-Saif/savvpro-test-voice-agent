"use client";

import React, { useState } from "react";
import { TurnResponse } from "../lib/api";

interface TracePanelProps {
  response: TurnResponse | null;
}

export function TracePanel({ response }: TracePanelProps) {
  const [showRawJson, setShowRawJson] = useState(false);

  if (!response || !response.trace) {
    return (
      <div className="card trace-card">
        <h3>Decision Trace</h3>
        <p className="empty-state">
          No turn processed yet. Trace entries from the deterministic brain will appear here.
        </p>
      </div>
    );
  }

  const { trace, frame, counters } = response;

  return (
    <div className="card trace-card">
      <div className="trace-header">
        <h3>🧠 Brain Decision Trace (Turn #{response.turn_no})</h3>
        <button
          className="btn btn-outline-sm"
          onClick={() => setShowRawJson(!showRawJson)}
        >
          {showRawJson ? "Visual View" : "{ } Raw JSON"}
        </button>
      </div>

      {showRawJson ? (
        <pre className="json-dump">{JSON.stringify(response, null, 2)}</pre>
      ) : (
        <div className="trace-body">
          <div className="trace-section">
            <span className="trace-label">Action & Reason:</span>
            <div className="trace-badge-row">
              <span className="badge badge-action">{trace.action}</span>
              <span className="badge-desc">{trace.reason}</span>
            </div>
          </div>

          <div className="trace-grid-2">
            <div className="trace-section">
              <span className="trace-label">Rules Fired:</span>
              <div className="trace-tags">
                {trace.rules_fired && trace.rules_fired.length > 0 ? (
                  trace.rules_fired.map((r, i) => (
                    <span key={i} className="tag tag-rule">
                      {r}
                    </span>
                  ))
                ) : (
                  <span className="muted">None</span>
                )}
              </div>
            </div>

            <div className="trace-section">
              <span className="trace-label">State Transitions:</span>
              <div className="transition-row">
                <span>
                  Phase: <b>{trace.phase_before}</b> ➔ <b>{trace.phase_after}</b>
                </span>
                <span>
                  Pending: <b>{trace.pending_before}</b> ➔ <b>{trace.pending_after}</b>
                </span>
              </div>
            </div>
          </div>

          <div className="trace-section">
            <span className="trace-label">NLU Input & Normalization:</span>
            <div className="trace-code-box">
              <div>Raw: &quot;{trace.input?.text || ""}&quot;</div>
              <div>Normalized: &quot;{trace.normalized}&quot;</div>
            </div>
          </div>

          <div className="trace-grid-2">
            <div className="trace-section">
              <span className="trace-label">Intent Scores:</span>
              <div className="trace-keyvalues">
                {Object.keys(trace.intent_scores || {}).length > 0 ? (
                  Object.entries(trace.intent_scores).map(([k, v]) => (
                    <div key={k} className="kv-row">
                      <span>{k}:</span>
                      <span>{v.toFixed(1)}</span>
                    </div>
                  ))
                ) : (
                  <span className="muted">No intents above threshold</span>
                )}
              </div>
            </div>

            <div className="trace-section">
              <span className="trace-label">Extracted Entities & Polarity:</span>
              <div className="trace-tags">
                {trace.extracted && trace.extracted.length > 0 ? (
                  trace.extracted.map((e, idx) => (
                    <span
                      key={idx}
                      className={`tag ${
                        e.polarity === "POS" ? "tag-pos" : "tag-neg"
                      }`}
                    >
                      {e.slot}: {e.value} ({e.polarity})
                    </span>
                  ))
                ) : (
                  <span className="muted">None extracted</span>
                )}
              </div>
            </div>
          </div>

          {trace.proposal && (
            <div className="trace-section highlight-box">
              <span className="trace-label">🔒 Confirmed Proposal Snapshot:</span>
              <div className="proposal-grid">
                <div>Patient: <b>{trace.proposal.patient_name}</b></div>
                <div>Service: <b>{trace.proposal.service}</b> ({trace.proposal.duration_minutes}m)</div>
                <div>Start: <b>{new Date(trace.proposal.start).toLocaleString()}</b></div>
              </div>
            </div>
          )}

          {trace.offers && (
            <div className="trace-section highlight-box-alt">
              <span className="trace-label">OfferSet ({trace.offers.kind}):</span>
              <ul>
                {trace.offers.options?.map((opt, i) => (
                  <li key={i}>{opt.label}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="trace-section">
            <span className="trace-label">Frame State:</span>
            <div className="frame-pills">
              <span>Intent: <b>{frame.intent || "none"}</b></span>
              <span>Service: <b>{frame.service || "none"}</b></span>
              <span>Date: <b>{frame.date || "none"}</b></span>
              <span>Time: <b>{frame.time ? frame.time.slice(11, 16) : "none"}</b></span>
              <span>Patient: <b>{frame.name || "none"}</b></span>
              {frame.urgent && <span className="urgent-badge">URGENT</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
