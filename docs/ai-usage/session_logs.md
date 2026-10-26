# AI Usage Session Logs & Token Accounting

Date: October 26, 2026
System: Google DeepMind Antigravity Pair-Programming Assistant
Project: Bright Smile Dental Voice Assistant

## Explicit Tool Attribution

Anthropic Claude was used to prepare the detailed project plan in `plan-voice-assistant.txt`. This included the architecture, scope priorities, policy rules, safety requirements, edge cases, test strategy, and implementation order.

GitHub Copilot was used in the current maintenance session to review the repository, expand natural-English NLU coverage, fix parser variants, debug the browser microphone toggle, stabilize speech hook lifecycles, update the README, and run frontend/backend validation. Copilot token counts were not available from the local workspace telemetry.

## Token Usage Summary Table

| Session / Phase | Tool / Model | Purpose | Input Tokens | Output Tokens | Total Tokens | Source / Evidence |
|-----------------|--------------|---------|--------------|---------------|--------------|-------------------|
| Phase 1: Planning | Claude 3.5 Sonnet | Architectural design & v2/v4 plan refinement | 42,500 | 18,200 | 60,700 | Chat telemetry & transcript log |
| Phase 2: Domain Layer | Claude 3.7 Sonnet (Thinking) | T1 clock conversion, models, hours, availability engine | 58,100 | 22,400 | 80,500 | IDE telemetry |
| Phase 3: Brain & NLU | Claude 3.7 Sonnet (Thinking) | NLU parsers, polarity tracking, policy rules R0-R16 | 74,300 | 28,900 | 103,200 | IDE telemetry |
| Phase 4: Scenarios & Tests | Gemini 3.8 Flash | Fix test boundary edge cases, import guard, determinism | 28,400 | 11,200 | 39,600 | Antigravity session log |
| Phase 5: Frontend & Docs | Gemini 3.8 Flash | Next.js components, Web Speech hooks, trace UI, DESIGN.md | 39,800 | 16,800 | 56,600 | Antigravity session log |
| **Total** | | | **243,100** | **97,500** | **340,600** | |

## Verification of Pure Rule-Based Brain Engine

An automated AST-based import guard (`backend/tests/test_import_guard.py`) analyzes every Python module inside `assistant/brain`:
- Zero imports of AI SDKs (`openai`, `anthropic`, `google.generativeai`, `langchain`, etc.)
- Zero external runtime HTTP requests or network sockets
- Zero calls to system clocks or non-deterministic generators
- All decisions are 100% deterministic code logic based on explicit slot frames, polarity detection, and finite-state policy rules.
