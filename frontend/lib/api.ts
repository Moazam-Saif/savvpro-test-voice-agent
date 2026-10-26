/**
 * frontend/lib/api.ts - Typed API client for Bright Smile Dental voice assistant.
 * All state shown in the UI comes from server responses.
 */

export interface TraceResponse {
  turn: number;
  input: {
    type: string;
    text?: string;
    confidence?: number;
  };
  normalized: string;
  intent_scores: Record<string, number>;
  extracted: Array<{
    slot: string;
    value: string;
    span: string;
    extractor: string;
    polarity: "POS" | "NEG";
    clause: number;
  }>;
  phase_before: string;
  phase_after: string;
  pending_before: string;
  pending_after: string;
  rules_fired: string[];
  counters: {
    silence: number;
    nomatch: number;
    reject: number;
    slot_attempts: Record<string, number>;
    verify_failures: number;
    oos_streak: number;
    human_offers: number;
    noprogress: number;
  };
  offers: {
    offer_id: number;
    kind: string;
    options: Array<{
      label: string;
      start: string | null;
    }>;
  } | null;
  proposal: {
    service: string;
    patient_name: string;
    start: string;
    end: string;
    duration_minutes: number;
    for_other: boolean;
  } | null;
  effect: string | null;
  action: string;
  reason: string;
}

export interface TurnResponse {
  session_id: string;
  turn_no: number;
  reply_text: string;
  ended: boolean;
  end_reason: string | null;
  phase: string;
  pending: string;
  frame: {
    intent: string | null;
    service: string | null;
    date: string | null;
    time: string | null;
    time_window: string | null;
    pref_mode: string | null;
    ambiguous_ampm: boolean;
    urgent: boolean;
    name: string | null;
    for_other: boolean;
    proposal: TraceResponse["proposal"];
    offers: TraceResponse["offers"];
  };
  counters: TraceResponse["counters"];
  last_booking: {
    id: string;
    summary: string;
    code: string;
  } | null;
  trace: TraceResponse;
}

export interface DemoBooking {
  id: string;
  patient_name: string;
  service: string;
  start: string;
  code: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function createSession(): Promise<TurnResponse> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to create session: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function sendTurn(
  sessionId: string,
  turnNo: number,
  type: "utterance" | "silence" | "hangup",
  text?: string,
  confidence?: number
): Promise<TurnResponse> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/turns`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      turn_no: turnNo,
      type,
      text: text ?? "",
      confidence: confidence ?? null,
    }),
  });

  if (res.status === 404) {
    const err = new Error("Session expired or not found");
    (err as any).status = 404;
    throw err;
  }
  if (res.status === 409) {
    const err = new Error("Conflict - session ended or turn_no out of sync");
    (err as any).status = 409;
    throw err;
  }
  if (!res.ok) {
    throw new Error(`HTTP Error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export async function fetchDemoBookings(): Promise<DemoBooking[]> {
  try {
    const res = await fetch(`${API_BASE}/api/demo/bookings`);
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}
