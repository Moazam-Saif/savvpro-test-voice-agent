"use client";

import React, { useEffect, useRef, useState } from "react";
import { MessageItem } from "../hooks/useCall";

interface TranscriptProps {
  messages: MessageItem[];
  interimText?: string;
  isCallActive: boolean;
  onSendTyped: (text: string) => void;
}

export function Transcript({
  messages,
  interimText,
  isCallActive,
  onSendTyped,
}: TranscriptProps) {
  const [typedInput, setTypedInput] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, interimText]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typedInput.trim() || !isCallActive) return;
    onSendTyped(typedInput.trim());
    setTypedInput("");
  };

  return (
    <div className="card transcript-card">
      <h3>Transcript</h3>
      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="empty-state">
            Start a call to speak with Bright Smile Dental assistant.
          </div>
        ) : (
          messages.map((m) => (
            <div
              key={m.id}
              className={`message-bubble ${
                m.sender === "caller" ? "caller" : "assistant"
              }`}
            >
              <div className="sender-tag">
                {m.sender === "caller" ? "👤 Caller" : "🦷 Assistant"}
                <span className="timestamp">{m.timestamp}</span>
              </div>
              <div className="message-content">{m.text}</div>
            </div>
          ))
        )}

        {interimText && (
          <div className="message-bubble caller interim">
            <div className="sender-tag">👤 Caller (listening...)</div>
            <div className="message-content">{interimText}</div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form className="typed-input-bar" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder={
            isCallActive
              ? "Type your response here (first-class fallback)..."
              : "Start a call to begin typing..."
          }
          value={typedInput}
          onChange={(e) => setTypedInput(e.target.value)}
          disabled={!isCallActive}
        />
        <button
          type="submit"
          className="btn btn-secondary"
          disabled={!isCallActive || !typedInput.trim()}
        >
          Send
        </button>
      </form>
    </div>
  );
}
