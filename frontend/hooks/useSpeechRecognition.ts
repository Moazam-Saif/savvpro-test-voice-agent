/**
 * frontend/hooks/useSpeechRecognition.ts
 * Clean manual toggle speech recognition hook.
 *
 * User clicks the mic button -> starts listening and continuously transcribes.
 * User clicks the mic button again -> stops listening and finalizes the complete transcription.
 * No premature timeouts or automatic cutoffs.
 */

import { useCallback, useEffect, useRef, useState } from "react";

interface UseSpeechRecognitionOptions {
  locale?: string;
  onTranscriptUpdate?: (text: string) => void;
  onFinalSentence?: (text: string) => void;
}

export type SpeechRecognitionStatus = "idle" | "starting" | "listening" | "stopping";

export function useSpeechRecognition({
  locale = "en-US",
  onTranscriptUpdate,
  onFinalSentence,
}: UseSpeechRecognitionOptions = {}) {
  const [isListening, setIsListening] = useState(false);
  const [status, setStatus] = useState<SpeechRecognitionStatus>("idle");
  const [isSupported, setIsSupported] = useState(true);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const finalBufferRef = useRef<string>("");
  const interimBufferRef = useRef<string>("");
  const isManuallyStoppedRef = useRef<boolean>(true);
  const isListeningRef = useRef<boolean>(false);
  const wantsListeningRef = useRef<boolean>(false);
  const restartTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Stable callback refs
  const onTranscriptUpdateRef = useRef(onTranscriptUpdate);
  useEffect(() => {
    onTranscriptUpdateRef.current = onTranscriptUpdate;
  }, [onTranscriptUpdate]);

  const onFinalSentenceRef = useRef(onFinalSentence);
  useEffect(() => {
    onFinalSentenceRef.current = onFinalSentence;
  }, [onFinalSentence]);

  const updateTranscript = useCallback(() => {
    const combined = (finalBufferRef.current + " " + interimBufferRef.current).trim();
    onTranscriptUpdateRef.current?.(combined);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setIsSupported(false);
      setErrorNotice(
        "Speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge."
      );
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = locale;

    recognition.onstart = () => {
      if (!wantsListeningRef.current) {
        try {
          recognition.stop();
        } catch {}
        return;
      }
      isListeningRef.current = true;
      setStatus("listening");
      setIsListening(true);
      setErrorNotice(null);
    };

    recognition.onresult = (event: any) => {
      if (!wantsListeningRef.current) return;

      let newlyFinal = "";
      let newlyInterim = "";

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const item = event.results[i];
        if (item.isFinal) {
          newlyFinal += " " + item[0].transcript;
        } else {
          newlyInterim += item[0].transcript;
        }
      }

      if (newlyFinal.trim()) {
        finalBufferRef.current = (finalBufferRef.current + " " + newlyFinal).trim();
      }
      interimBufferRef.current = newlyInterim.trim();

      updateTranscript();
    };

    recognition.onerror = (event: any) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setErrorNotice("Microphone permission was denied.");
        wantsListeningRef.current = false;
        isListeningRef.current = false;
        setStatus("idle");
        setIsListening(false);
      } else if (event.error !== "no-speech") {
        console.warn("Speech recognition notice:", event.error);
      }
    };

    recognition.onend = () => {
      if (wantsListeningRef.current && !isManuallyStoppedRef.current) {
        setStatus("starting");
        isListeningRef.current = true;
        setIsListening(true);
        if (restartTimerRef.current === null) {
          restartTimerRef.current = setTimeout(() => {
            restartTimerRef.current = null;
            if (!wantsListeningRef.current) return;
            try {
              recognition.start();
            } catch {
              // The browser may still be closing the previous session.
            }
          }, 0);
        }
        return;
      }
      isListeningRef.current = false;
      setStatus("idle");
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      isManuallyStoppedRef.current = true;
      wantsListeningRef.current = false;
      if (restartTimerRef.current !== null) {
        clearTimeout(restartTimerRef.current);
        restartTimerRef.current = null;
      }
      isListeningRef.current = false;
      setStatus("idle");
      try {
        recognition.stop();
      } catch {}
    };
  }, [locale, updateTranscript]);

  const startListening = useCallback(() => {
    if (!recognitionRef.current) return;
    wantsListeningRef.current = true;
    isListeningRef.current = true;
    setIsListening(true);
    setStatus("listening");
    try {
      isManuallyStoppedRef.current = false;
      finalBufferRef.current = "";
      interimBufferRef.current = "";
      updateTranscript();
      recognitionRef.current.lang = locale;
      recognitionRef.current.start();
    } catch (error: any) {
      if (error?.name === "InvalidStateError") {
        return;
      }
      wantsListeningRef.current = false;
      isListeningRef.current = false;
      setStatus("idle");
      setIsListening(false);
      setErrorNotice("The microphone could not be started. Please try again.");
    }
  }, [locale, updateTranscript]);

  const stopListening = useCallback((triggerSubmit: boolean = true) => {
    const shouldStop = isListeningRef.current || wantsListeningRef.current;
    isManuallyStoppedRef.current = true;
    wantsListeningRef.current = false;
    if (restartTimerRef.current !== null) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }
    isListeningRef.current = false;
    setStatus(shouldStop ? "stopping" : "idle");
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }
    setIsListening(false);

    const fullSentence = (finalBufferRef.current + " " + interimBufferRef.current).trim();
    finalBufferRef.current = "";
    interimBufferRef.current = "";

    onTranscriptUpdateRef.current?.("");

    if (triggerSubmit && fullSentence.length > 0) {
      onFinalSentenceRef.current?.(fullSentence);
    }
    if (!recognitionRef.current || !shouldStop) {
      setStatus("idle");
    }
    return fullSentence;
  }, []);

  const toggleListening = useCallback(() => {
    if (wantsListeningRef.current) {
      stopListening(true);
    } else {
      startListening();
    }
  }, [startListening, stopListening]);

  return {
    isListening,
    isSupported,
    errorNotice,
    status,
    startListening,
    stopListening,
    toggleListening,
  };
}
