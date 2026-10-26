"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ChatContainer } from "../components/ChatContainer";
import { DemoBookings } from "../components/DemoBookings";
import { TraceModal } from "../components/TraceModal";
import { useCall } from "../hooks/useCall";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { useSpeechSynthesis } from "../hooks/useSpeechSynthesis";

export default function VoiceAssistantPage() {
  const [locale, setLocale] = useState("en-US");
  const [isTraceModalOpen, setIsTraceModalOpen] = useState(false);
  const [liveSpeechText, setLiveSpeechText] = useState("");

  const {
    status,
    messages,
    latestResponse,
    errorMessage,
    isRetrying,
    startCall,
    submitTurn,
    retryLastFailedTurn,
    endCall,
  } = useCall();

  const isCallActive = status !== "idle" && status !== "ended";

  // Speech synthesis (TTS)
  const { isSpeaking, speak, cancel: cancelSpeech } = useSpeechSynthesis({
    locale,
    onSpeakingStart: () => {
      // Mic off while assistant speaks
      stopListening(false);
    },
    onSpeakingEnd: () => {
      // Assistant finished speaking; user can click mic whenever they are ready
    },
  });

  // Handle final sentence when user stops recording
  const handleFinalSpeech = useCallback(
    async (text: string) => {
      if (!text || !text.trim() || !isCallActive || isSpeaking) return;
      setLiveSpeechText("");
      const res = await submitTurn("utterance", text);
      if (res && res.reply_text) {
        speak(res.reply_text);
      }
    },
    [isCallActive, isSpeaking, submitTurn, speak]
  );

  // Manual speech recognition hook
  const {
    isListening,
    status: speechStatus,
    errorNotice,
    startListening,
    stopListening,
    toggleListening,
  } = useSpeechRecognition({
    locale,
    onTranscriptUpdate: (text) => {
      setLiveSpeechText(text);
    },
    onFinalSentence: (text) => {
      handleFinalSpeech(text);
    },
  });

  // Start conversation
  const handleStartCall = async () => {
    const res = await startCall();
    if (res && res.reply_text) {
      speak(res.reply_text);
    }
  };

  // End conversation
  const handleEndCall = () => {
    cancelSpeech();
    stopListening(false);
    endCall();
    setLiveSpeechText("");
  };

  // Toggle mic button
  const handleToggleMic = () => {
    if (!isCallActive) return;
    cancelSpeech();
    toggleListening();
  };

  // Typed input handler
  const handleSendTyped = async (text: string) => {
    if (!isCallActive) return;
    cancelSpeech();
    stopListening(false);
    setLiveSpeechText("");
    const res = await submitTurn("utterance", text);
    if (res && res.reply_text) {
      speak(res.reply_text);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelSpeech();
      stopListening(false);
    };
  }, [cancelSpeech, stopListening]);

  return (
    <div className="app-wrapper">
      <header className="app-header">
        <div className="brand-container">
          <div className="brand-logo-circle">
            <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
              <path d="M17.2 2c-1.8 0-3.3 1.1-4.2 2.7-.9-1.6-2.4-2.7-4.2-2.7-2.9 0-5.3 2.5-5.3 5.5 0 2.4 1 5.3 2.1 8 1.3 3.3 2.8 6.5 4.3 6.5.9 0 1.5-.7 2.1-2 .4-.9.9-1.7 1-1.7s.6.8 1 1.7c.6 1.3 1.2 2 2.1 2 1.5 0 3-3.2 4.3-6.5 1.1-2.7 2.1-5.6 2.1-8 0-3-2.4-5.5-5.3-5.5z" />
            </svg>
          </div>
          <div>
            <h1 className="brand-title">Bright Smile Dental</h1>
            <p className="brand-subtitle">
              Automated Voice Assistant &bull; Rule-Based Dialogue Engine
            </p>
          </div>
        </div>
      </header>

      {errorMessage && (
        <div className="error-banner">
          <span>{errorMessage}</span>
          <button className="btn-retry" onClick={retryLastFailedTurn}>
            Retry
          </button>
        </div>
      )}

      {errorNotice && (
        <div className="error-banner">
          <span>{errorNotice}</span>
        </div>
      )}

      {/* Main Unified Chat Container */}
      <ChatContainer
        messages={messages}
        isListening={isListening}
        isSpeaking={isSpeaking}
        isRetrying={isRetrying}
        status={status}
        locale={locale}
        onLocaleChange={setLocale}
        onStartCall={handleStartCall}
        onEndCall={handleEndCall}
        onToggleMic={handleToggleMic}
        speechStatus={speechStatus}
        onSendTyped={handleSendTyped}
        latestResponse={latestResponse}
        onOpenTrace={() => setIsTraceModalOpen(true)}
        liveSpeechText={liveSpeechText}
      />

      {/* Pop-Up Modal for Decision Trace */}
      <TraceModal
        isOpen={isTraceModalOpen}
        onClose={() => setIsTraceModalOpen(false)}
        response={latestResponse}
      />

      {/* Scroll down section for Demo Information */}
      <section className="scroll-section">
        <DemoBookings />
      </section>
    </div>
  );
}
