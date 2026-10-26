import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TraceModal } from "./TraceModal";
import { TurnResponse } from "../lib/api";

describe("TraceModal component", () => {
  it("renders nothing when isOpen is false", () => {
    const { container } = render(
      <TraceModal isOpen={false} onClose={() => {}} response={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders decision trace pop-up, rules fired, and extractions when isOpen is true", () => {
    const mockResponse: TurnResponse = {
      session_id: "s-1",
      turn_no: 3,
      reply_text: "So that's a cleaning for Sarah...",
      ended: false,
      end_reason: null,
      phase: "CONFIRMING",
      pending: "CONFIRM_YN",
      frame: {
        intent: "BOOK",
        service: "cleaning",
        date: "2026-10-30",
        time: "2026-10-30T14:00:00",
        time_window: null,
        pref_mode: null,
        ambiguous_ampm: false,
        urgent: false,
        name: "Sarah Thompson",
        for_other: false,
        proposal: {
          service: "cleaning",
          patient_name: "Sarah Thompson",
          start: "2026-10-30T14:00:00",
          end: "2026-10-30T14:30:00",
          duration_minutes: 30,
          for_other: false,
        },
        offers: null,
      },
      counters: {
        silence: 0,
        nomatch: 0,
        reject: 0,
        slot_attempts: {},
        verify_failures: 0,
        oos_streak: 0,
        human_offers: 0,
        noprogress: 0,
      },
      last_booking: null,
      trace: {
        turn: 3,
        input: { type: "utterance", text: "cleaning on friday at 2 for sarah" },
        normalized: "cleaning on friday at 2 for sarah",
        intent_scores: { BOOK: 2.0 },
        extracted: [
          {
            slot: "service",
            value: "cleaning",
            span: "cleaning",
            extractor: "services",
            polarity: "POS",
            clause: 0,
          },
        ],
        phase_before: "COLLECTING",
        phase_after: "CONFIRMING",
        pending_before: "TIME",
        pending_after: "CONFIRM_YN",
        rules_fired: ["R8.fill:service", "R10.free", "R12.confirm"],
        counters: {
          silence: 0,
          nomatch: 0,
          reject: 0,
          slot_attempts: {},
          verify_failures: 0,
          oos_streak: 0,
          human_offers: 0,
          noprogress: 0,
        },
        offers: null,
        proposal: {
          service: "cleaning",
          patient_name: "Sarah Thompson",
          start: "2026-10-30T14:00:00",
          end: "2026-10-30T14:30:00",
          duration_minutes: 30,
          for_other: false,
        },
        effect: null,
        action: "ASK_CONFIRM",
        reason: "all required slots filled and slot is free",
      },
    };

    render(
      <TraceModal isOpen={true} onClose={() => {}} response={mockResponse} />
    );
    expect(screen.getByText("Brain Decision Trace")).toBeInTheDocument();
    expect(screen.getByText("ASK_CONFIRM")).toBeInTheDocument();
    expect(screen.getByText("R8.fill:service")).toBeInTheDocument();
    expect(screen.getByText("R12.confirm")).toBeInTheDocument();
    expect(screen.getByText(/service: cleaning \[POS\]/i)).toBeInTheDocument();
  });
});
