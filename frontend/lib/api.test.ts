import { describe, it, expect, vi, beforeEach } from "vitest";
import { createSession, sendTurn } from "./api";

describe("Frontend API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("createSession makes POST /api/sessions and returns response", async () => {
    const mockResponse = { session_id: "test-123", turn_no: 0, reply_text: "Welcome" };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await createSession();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/sessions"),
      expect.objectContaining({ method: "POST" })
    );
    expect(result.session_id).toBe("test-123");
  });

  it("sendTurn sends exact turn_no and payload", async () => {
    const mockResponse = { session_id: "test-123", turn_no: 1, reply_text: "Which service?" };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await sendTurn("test-123", 1, "utterance", "book an appointment", 0.95);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/sessions/test-123/turns"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          turn_no: 1,
          type: "utterance",
          text: "book an appointment",
          confidence: 0.95,
        }),
      })
    );
    expect(result.turn_no).toBe(1);
  });

  it("sendTurn throws error with status 404 on expired session", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
    });

    await expect(sendTurn("expired-id", 1, "utterance", "hello")).rejects.toThrow();
  });

  it("sendTurn throws error with status 409 on conflict", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      statusText: "Conflict",
    });

    await expect(sendTurn("test-id", 5, "utterance", "hello")).rejects.toThrow();
  });
});
