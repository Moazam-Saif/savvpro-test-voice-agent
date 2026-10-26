/**
 * frontend/hooks/useCall.ts
 * Manages conversation lifecycle, turn sequencing, retries, and state coordination.
 */

import { useCallback, useRef, useState } from "react";
import { createSession, sendTurn, TurnResponse } from "../lib/api";

export interface MessageItem {
  id: string;
  sender: "caller" | "assistant";
  text: string;
  timestamp: string;
}

export type CallStatus = "idle" | "listening" | "thinking" | "speaking" | "ended";

export function useCall() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnNo, setTurnNo] = useState<number>(0);
  const [status, setStatus] = useState<CallStatus>("idle");
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [latestResponse, setLatestResponse] = useState<TurnResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState<boolean>(false);

  // In-flight submission lock to prevent concurrent double-submits
  const inFlightLockRef = useRef<boolean>(false);
  const lastFailedTurnRef = useRef<{
    turnNo: number;
    type: "utterance" | "silence" | "hangup";
    text?: string;
    confidence?: number;
  } | null>(null);

  const startCall = useCallback(async () => {
    try {
      setErrorMessage(null);
      setStatus("thinking");
      inFlightLockRef.current = true;

      const res = await createSession();
      setSessionId(res.session_id);
      setTurnNo(0);
      setLatestResponse(res);

      if (res.reply_text) {
        setMessages([
          {
            id: `turn-0`,
            sender: "assistant",
            text: res.reply_text,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
      } else {
        setMessages([]);
      }

      setStatus("listening");
      inFlightLockRef.current = false;
      return res;
    } catch (err: any) {
      inFlightLockRef.current = false;
      setStatus("idle");
      setErrorMessage("Could not connect to assistant. Is backend running?");
      return null;
    }
  }, []);

  const executeTurnWithRetry = useCallback(
    async (
      sid: string,
      targetTurnNo: number,
      type: "utterance" | "silence" | "hangup",
      text?: string,
      confidence?: number,
      maxRetries = 3
    ): Promise<TurnResponse> => {
      let attempt = 0;
      let delay = 500;

      while (attempt <= maxRetries) {
        try {
          const res = await sendTurn(sid, targetTurnNo, type, text, confidence);
          lastFailedTurnRef.current = null;
          return res;
        } catch (err: any) {
          if (err.status === 404) {
            // Session expired or server restart
            throw err;
          }
          if (err.status === 409) {
            // Conflict / state out of sync
            throw err;
          }
          attempt++;
          if (attempt > maxRetries) {
            lastFailedTurnRef.current = { turnNo: targetTurnNo, type, text, confidence };
            throw err;
          }
          setIsRetrying(true);
          await new Promise((resolve) => setTimeout(resolve, delay));
          delay *= 1.5;
        } finally {
          setIsRetrying(false);
        }
      }
      throw new Error("Retries exhausted");
    },
    []
  );

  const submitTurn = useCallback(
    async (
      type: "utterance" | "silence" | "hangup",
      text?: string,
      confidence?: number
    ): Promise<TurnResponse | null> => {
      if (!sessionId) return null;
      if (inFlightLockRef.current) {
        console.warn("Blocked duplicate in-flight turn submission");
        return null;
      }

      inFlightLockRef.current = true;
      setStatus("thinking");
      setErrorMessage(null);

      const nextTurnNo = turnNo + 1;

      // Add caller utterance to transcript if present
      if (type === "utterance" && text && text.trim()) {
        setMessages((prev) => [
          ...prev,
          {
            id: `caller-${nextTurnNo}`,
            sender: "caller",
            text,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
      }

      try {
        const res = await executeTurnWithRetry(
          sessionId,
          nextTurnNo,
          type,
          text,
          confidence
        );

        setTurnNo(nextTurnNo);
        setLatestResponse(res);

        // Add assistant reply to transcript if non-empty
        if (res.reply_text && res.reply_text.trim()) {
          setMessages((prev) => [
            ...prev,
            {
              id: `assistant-${nextTurnNo}`,
              sender: "assistant",
              text: res.reply_text,
              timestamp: new Date().toLocaleTimeString(),
            },
          ]);
        }

        if (res.ended) {
          setStatus("ended");
        } else {
          setStatus("listening");
        }

        inFlightLockRef.current = false;
        return res;
      } catch (err: any) {
        inFlightLockRef.current = false;
        if (err.status === 404) {
          setErrorMessage("The call timed out. Starting a new call...");
          setTimeout(() => {
            startCall();
          }, 2000);
          return null;
        }

        if (err.status === 409) {
          setErrorMessage("Session conflict or session ended.");
          setStatus("ended");
          return null;
        }

        setErrorMessage("The assistant is unavailable. You can click retry.");
        setStatus("idle");
        return null;
      }
    },
    [sessionId, turnNo, executeTurnWithRetry, startCall]
  );

  const retryLastFailedTurn = useCallback(async () => {
    if (!lastFailedTurnRef.current || !sessionId) return;
    const { type, text, confidence } = lastFailedTurnRef.current;
    await submitTurn(type, text, confidence);
  }, [sessionId, submitTurn]);

  const endCall = useCallback(async () => {
    if (!sessionId) {
      setStatus("idle");
      return;
    }
    await submitTurn("hangup");
    setStatus("ended");
  }, [sessionId, submitTurn]);

  const resetCall = useCallback(() => {
    setSessionId(null);
    setTurnNo(0);
    setStatus("idle");
    setMessages([]);
    setLatestResponse(null);
    setErrorMessage(null);
    inFlightLockRef.current = false;
  }, []);

  return {
    sessionId,
    turnNo,
    status,
    setStatus,
    messages,
    latestResponse,
    errorMessage,
    isRetrying,
    startCall,
    submitTurn,
    retryLastFailedTurn,
    endCall,
    resetCall,
  };
}
