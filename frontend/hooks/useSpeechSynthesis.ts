/**
 * frontend/hooks/useSpeechSynthesis.ts
 * Browser Web Speech API speechSynthesis hook.
 * Manages audio output, pauses mic while speaking, and ensures fallback timeouts.
 */

import { useCallback, useEffect, useRef, useState } from "react";

interface UseSpeechSynthesisOptions {
  locale?: string;
  onSpeakingStart?: () => void;
  onSpeakingEnd?: () => void;
}

export function useSpeechSynthesis({
  locale = "en-US",
  onSpeakingStart,
  onSpeakingEnd,
}: UseSpeechSynthesisOptions = {}) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const safetyTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const onSpeakingStartRef = useRef(onSpeakingStart);
  const onSpeakingEndRef = useRef(onSpeakingEnd);

  useEffect(() => {
    onSpeakingStartRef.current = onSpeakingStart;
    onSpeakingEndRef.current = onSpeakingEnd;
  }, [onSpeakingStart, onSpeakingEnd]);

  const clearSafetyTimeout = useCallback(() => {
    if (safetyTimeoutRef.current) {
      clearTimeout(safetyTimeoutRef.current);
      safetyTimeoutRef.current = null;
    }
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) {
        return;
      }

      // Empty reply_text is not spoken (e.g. actions HOLD and WAIT)
      if (!text || !text.trim()) {
        return;
      }

      window.speechSynthesis.cancel();
      clearSafetyTimeout();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = locale;
      utterance.rate = 1.0;

      utterance.onstart = () => {
        setIsSpeaking(true);
        onSpeakingStartRef.current?.();

        // Safety timeout in case onend never fires (approx 200 words/min = 3.3 words/sec)
        const wordCount = text.split(/\s+/).length;
        const estimatedMs = Math.max(wordCount * 600, 3000);
        safetyTimeoutRef.current = setTimeout(() => {
          setIsSpeaking(false);
          onSpeakingEndRef.current?.();
        }, estimatedMs);
      };

      utterance.onend = () => {
        clearSafetyTimeout();
        setIsSpeaking(false);
        onSpeakingEndRef.current?.();
      };

      utterance.onerror = (e) => {
        console.warn("Speech synthesis error:", e);
        clearSafetyTimeout();
        setIsSpeaking(false);
        onSpeakingEndRef.current?.();
      };

      window.speechSynthesis.speak(utterance);
    },
    [locale, clearSafetyTimeout]
  );

  const cancel = useCallback(() => {
    clearSafetyTimeout();
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      onSpeakingEndRef.current?.();
    }
  }, [clearSafetyTimeout]);

  useEffect(() => {
    return () => {
      clearSafetyTimeout();
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, [clearSafetyTimeout]);

  return {
    isSpeaking,
    speak,
    cancel,
  };
}
