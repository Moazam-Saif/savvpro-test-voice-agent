"use client";

import React, { useEffect, useRef, useState } from "react";
import { MessageItem, CallStatus } from "../hooks/useCall";
import { TurnResponse } from "../lib/api";
import { SpeechRecognitionStatus } from "../hooks/useSpeechRecognition";

interface ChatContainerProps {
  messages: MessageItem[];
  isListening: boolean;
  isSpeaking: boolean;
  isRetrying: boolean;
  status: CallStatus;
  locale: string;
  onLocaleChange: (loc: string) => void;
  onStartCall: () => void;
  onEndCall: () => void;
  onToggleMic: () => void;
  speechStatus: SpeechRecognitionStatus;
  onSendTyped: (text: string) => void;
  latestResponse: TurnResponse | null;
  onOpenTrace: () => void;
  liveSpeechText: string;
}

export function ChatContainer({
  messages,
  isListening,
  isSpeaking,
  isRetrying,
  status,
  locale,
  onLocaleChange,
  onStartCall,
  onEndCall,
  onToggleMic,
  speechStatus,
  onSendTyped,
  latestResponse,
  onOpenTrace,
  liveSpeechText,
}: ChatContainerProps) {
  const [typedInput, setTypedInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const isCallActive = status !== "idle" && status !== "ended";

  // When speech recognition produces text live, reflect it directly into typedInput
  useEffect(() => {
    if (liveSpeechText) {
      setTypedInput(liveSpeechText);
    }
  }, [liveSpeechText]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveSpeechText]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedInput.trim()) return;
    onSendTyped(typedInput.trim());
    setTypedInput("");
  };

  const getStatusBadge = () => {
    if (isRetrying) {
      return <span className="status-badge status-retry">Retrying</span>;
    }
    if (isSpeaking) {
      return <span className="status-badge status-speaking">Speaking</span>;
    }
    if (isListening) {
      return (
        <span className="status-badge status-listening">
          <span className="pulse-dot"></span> Listening
        </span>
      );
    }
    if (status === "thinking") {
      return <span className="status-badge status-thinking">Processing</span>;
    }
    if (status === "ended") {
      return <span className="status-badge status-ended">Call Ended</span>;
    }
    return <span className="status-badge status-idle">Ready</span>;
  };

  return (
    <div className="main-chat-card">
      {/* Top Header of Chat */}
      <div className="chat-header">
        <div className="chat-brand">
          <div className="tooth-logo-badge">
            <svg viewBox="0 0 24 24" fill="currentColor" width="22" height="22">
              <path d="M17.2 2c-1.8 0-3.3 1.1-4.2 2.7-.9-1.6-2.4-2.7-4.2-2.7-2.9 0-5.3 2.5-5.3 5.5 0 2.4 1 5.3 2.1 8 1.3 3.3 2.8 6.5 4.3 6.5.9 0 1.5-.7 2.1-2 .4-.9.9-1.7 1-1.7s.6.8 1 1.7c.6 1.3 1.2 2 2.1 2 1.5 0 3-3.2 4.3-6.5 1.1-2.7 2.1-5.6 2.1-8 0-3-2.4-5.5-5.3-5.5z" />
            </svg>
          </div>
          <div>
            <h2>Bright Smile Dental</h2>
            <p className="chat-subtitle">Automated Voice & Appointment Desk</p>
          </div>
        </div>

        <div className="header-controls">
          <div className="locale-wrap">
            <select
              value={locale}
              onChange={(e) => onLocaleChange(e.target.value)}
              disabled={isCallActive}
              className="locale-select"
            >
              <option value="en-US">English (US)</option>
              <option value="en-GB">English (UK)</option>
              <option value="en-IN">English (India)</option>
            </select>
          </div>

          <div className="status-wrap">{getStatusBadge()}</div>

          {isCallActive && (
            <button className="btn-end" onClick={onEndCall}>
              End Conversation
            </button>
          )}
        </div>
      </div>

      {/* Main Q&A Conversation Area with Tooth Watermark */}
      <div className="chat-body">
        {/* Subtle SVG Tooth Watermark in background */}
        <div className="tooth-watermark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M17.2 2c-1.8 0-3.3 1.1-4.2 2.7-.9-1.6-2.4-2.7-4.2-2.7-2.9 0-5.3 2.5-5.3 5.5 0 2.4 1 5.3 2.1 8 1.3 3.3 2.8 6.5 4.3 6.5.9 0 1.5-.7 2.1-2 .4-.9.9-1.7 1-1.7s.6.8 1 1.7c.6 1.3 1.2 2 2.1 2 1.5 0 3-3.2 4.3-6.5 1.1-2.7 2.1-5.6 2.1-8 0-3-2.4-5.5-5.3-5.5z" />
          </svg>
        </div>

        <div className="messages-stream">
          {!isCallActive && messages.length === 0 ? (
            <div className="center-call-container">
              <div className="center-call-card">
                <h3>Welcome to Bright Smile Dental</h3>
                <p>
                  Click below to begin your conversation. You can speak or type to schedule,
                  cancel, or ask questions about our dental services.
                </p>
                <button className="btn-start-center" onClick={onStartCall}>
                  Start Conversation
                </button>
              </div>
            </div>
          ) : (
            messages.map((m, index) => {
              const isAssistant = m.sender === "assistant";
              const isLastAssistant =
                isAssistant &&
                index === messages.map((x) => x.sender).lastIndexOf("assistant");

              return (
                <div
                  key={m.id}
                  className={`message-row ${isAssistant ? "row-assistant" : "row-caller"}`}
                >
                  <div className={`msg-bubble ${isAssistant ? "bubble-assistant" : "bubble-caller"}`}>
                    <div className="bubble-meta">
                      <span className="sender-name">
                        {isAssistant ? "Assistant" : "You"}
                      </span>
                      <span className="msg-time">{m.timestamp}</span>
                    </div>
                    <div className="msg-text">{m.text}</div>

                    {/* Button to inspect Decision Trace Pop-Up */}
                    {isLastAssistant && latestResponse && latestResponse.trace && (
                      <div className="trace-action-bar">
                        <button
                          type="button"
                          className="btn-trace-pill"
                          onClick={onOpenTrace}
                        >
                          View Decision Trace (Turn #{latestResponse.turn_no})
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Mic Status Indicator bar when actively listening */}
      {isListening && (
        <div className="listening-indicator-bar">
          <div className="pulse-indicator"></div>
          <span>
            Recording voice... Speak everything you need, then click the microphone button again to send.
          </span>
        </div>
      )}

      {/* Bottom Input Area: Voice Icon + Typing Box + Send Button */}
      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <button
          type="button"
          className={`mic-button ${isListening ? "mic-active" : ""} mic-${speechStatus}`}
          onClick={onToggleMic}
          disabled={!isCallActive || speechStatus === "stopping"}
          title={isListening ? "Click to stop listening and send" : "Click to start speaking"}
          aria-label={isListening ? "Stop listening and send voice message" : "Start listening"}
          aria-pressed={isListening}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
          </svg>
          <span className="mic-button-label">{isListening ? "Listening" : "Speak"}</span>
        </button>

        <input
          type="text"
          className="text-input"
          placeholder={
            isCallActive
              ? isListening
                ? "Listening... text will appear here as you speak..."
                : "Type your response here or click the microphone to speak..."
              : "Click 'Start Conversation' above to begin..."
          }
          value={typedInput}
          onChange={(e) => setTypedInput(e.target.value)}
          disabled={!isCallActive}
        />

        <button
          type="submit"
          className="btn-send"
          disabled={!isCallActive || !typedInput.trim()}
          title="Send message"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
          <span>Send</span>
        </button>
      </form>
    </div>
  );
}
