"use client";

import React, { useState } from "react";
import { TurnResponse } from "../lib/api";

interface TraceModalProps {
  isOpen: boolean;
  onClose: () => void;
  response: TurnResponse | null;
}

export function TraceModal({ isOpen, onClose, response }: TraceModalProps) {
  const [showRawJson, setShowRawJson] = useState(false);

  if (!isOpen || !response || !response.trace) {
    return null;
  }

  const { trace, frame } = response;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22" className="text-blue">
              <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
            </svg>
            <div>
              <h3>Brain Decision Trace</h3>
              <p className="modal-subtitle">
                Turn #{response.turn_no} &bull; Deterministic rule-based execution
              </p>
            </div>
          </div>
          <div className="modal-actions">
            <button
              className="btn btn-outline-sm"
              onClick={() => setShowRawJson(!showRawJson)}
            >
              {showRawJson ? "Visual View" : "{ } Raw JSON"}
            </button>
            <button className="btn-close" onClick={onClose} aria-label="Close">
              &times;
            </button>
          </div>
        </div>

        <div className="modal-body">
          {showRawJson ? (
            <pre className="json-dump">{JSON.stringify(response, null, 2)}</pre>
          ) : (
            <div className="trace-details">
              <div className="trace-row-hero">
                <div className="hero-stat">
                  <span className="stat-label">Action Decided</span>
                  <span className="badge badge-action">{trace.action}</span>
                </div>
                <div className="hero-stat">
                  <span className="stat-label">Primary Reason</span>
                  <span className="stat-text">{trace.reason}</span>
                </div>
              </div>

              <div className="trace-grid">
                <div className="trace-card-mini">
                  <h4>Rules Fired in Policy</h4>
                  <div className="tag-cloud">
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

                <div className="trace-card-mini">
                  <h4>State Transition</h4>
                  <div className="transition-list">
                    <div>
                      Phase: <b className="text-blue">{trace.phase_before}</b> &rarr;{" "}
                      <b className="text-blue">{trace.phase_after}</b>
                    </div>
                    <div>
                      Pending: <b className="text-blue">{trace.pending_before}</b>{" "}
                      &rarr; <b className="text-blue">{trace.pending_after}</b>
                    </div>
                  </div>
                </div>
              </div>

              <div className="trace-card-mini">
                <h4>NLU Input & Normalization</h4>
                <div className="code-box">
                  <div><strong>Raw text:</strong> &quot;{trace.input?.text || ""}&quot;</div>
                  <div><strong>Normalized:</strong> &quot;{trace.normalized}&quot;</div>
                </div>
              </div>

              <div className="trace-grid">
                <div className="trace-card-mini">
                  <h4>Intent Scoring</h4>
                  <div className="kv-table">
                    {Object.keys(trace.intent_scores || {}).length > 0 ? (
                      Object.entries(trace.intent_scores).map(([k, v]) => (
                        <div key={k} className="kv-item">
                          <span>{k}</span>
                          <b>{v.toFixed(1)}</b>
                        </div>
                      ))
                    ) : (
                      <span className="muted">No intents above 1.0 threshold</span>
                    )}
                  </div>
                </div>

                <div className="trace-card-mini">
                  <h4>Extracted Entities & Polarity</h4>
                  <div className="tag-cloud">
                    {trace.extracted && trace.extracted.length > 0 ? (
                      trace.extracted.map((e, idx) => (
                        <span
                          key={idx}
                          className={`tag ${
                            e.polarity === "POS" ? "tag-pos" : "tag-neg"
                          }`}
                        >
                          {e.slot}: {e.value} [{e.polarity}]
                        </span>
                      ))
                    ) : (
                      <span className="muted">No slots extracted</span>
                    )}
                  </div>
                </div>
              </div>

              {trace.proposal && (
                <div className="proposal-box">
                  <div className="proposal-title">Frozen Proposal Snapshot (Readback)</div>
                  <div className="proposal-content">
                    <div>Patient: <b>{trace.proposal.patient_name}</b></div>
                    <div>Service: <b>{trace.proposal.service}</b> ({trace.proposal.duration_minutes} min)</div>
                    <div>Start Time: <b>{new Date(trace.proposal.start).toLocaleString()}</b></div>
                  </div>
                </div>
              )}

              {trace.offers && (
                <div className="offers-box">
                  <div className="offers-title">Candidate OfferSet ({trace.offers.kind})</div>
                  <ul>
                    {trace.offers.options?.map((opt, i) => (
                      <li key={i}>{opt.label}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="trace-card-mini">
                <h4>Current Dialogue Frame</h4>
                <div className="frame-chips">
                  <span>Intent: <b>{frame.intent || "None"}</b></span>
                  <span>Service: <b>{frame.service || "None"}</b></span>
                  <span>Date: <b>{frame.date || "None"}</b></span>
                  <span>Time: <b>{frame.time ? frame.time.slice(11, 16) : "None"}</b></span>
                  <span>Patient: <b>{frame.name || "None"}</b></span>
                  {frame.urgent && <span className="urgent-chip">URGENT</span>}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
