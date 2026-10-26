# AI Usage Report

## 1. AI Tools Used

During the design and construction of the Bright Smile Dental Voice Assistant, the following AI tools and models were utilized:
- **Anthropic Claude 3.5 Sonnet / Claude 3.7 Sonnet (Thinking)**: Initial task breakdown, failure mode analysis (gaps C1–C5, contradictions U1–U6, edge cases E1–E7), architecture design, domain modeling, and initial rule draft.
- **Google Gemini 3.8 Flash**: Runtime debugging, test boundary verification, frontend component integration, Vitest test authoring, and documentation generation.
- **Antigravity IDE Assistant**: Orchestration, task tracking, file generation, and test execution.
- **GitHub Copilot**: Repository review, natural-English NLU test expansion, frontend microphone lifecycle debugging, speech hook fixes, verification, and README maintenance.

Claude was specifically used to prepare the detailed project plan, including the architecture, scope priorities, policy rules, safety requirements, edge cases, test strategy, and implementation order documented in `plan-voice-assistant.txt`.

---

## 2. How AI Helped

1. **Architecture & Edge Case Discovery**:
   - Identified critical voice dialogue risks such as stale confirmation (`"actually Thursday"` after readback), ambiguous AM/PM resolution, cancellation verification privacy risks, and emergency symptom detection.
   - Designed the `Proposal` and `OfferSet` frozen snapshot pattern, ensuring that any utterance modification immediately invalidates pending proposals and eliminates race conditions.
2. **Domain & Timezone Engineering**:
   - Formulated the `T1` rule: strictly isolating UTC conversions (`to_local`, `local_to_utc`) to `clock.py`, ensuring the brain only operates on clinic-local wall-clock time while handling DST fall-back (crossing Nov 1, 2026).
3. **Scaffolding & Determinism Guard**:
   - Generated the AST-based import guard (`test_import_guard.py`), mathematically proving that no LLM or external AI API exists inside the decision-making dialogue manager.

---

## 3. Where AI Got Things Wrong & Corrective Actions

During development, several real errors and misunderstandings produced by the AI models were identified and corrected:

1. **Lead-Time Directional Sign Error**:
   - *Issue*: In writing the test for the 2-hour minimum lead-time constraint across DST fall-back (`test_t1_lead_boundary_nov2_too_soon`), the plan and model asserted that at `06:59` local time on Nov 2, a `09:00` appointment should be `TOO_SOON`.
   - *Reality*: From `06:59` to `09:00` is **2 hours and 1 minute** of notice, which satisfies the `>= 2 hours` constraint. The model had inverted the temporal direction, conflating "earlier in the morning" with "closer to the appointment".
   - *Correction*: Fixed the test to check `07:01` (1 hour 59 minutes notice), which is genuinely `TOO_SOON`, and `07:00` (exactly 2 hours notice), which is allowed.

2. **Regex Word Boundary on Dotted Abbreviations (`a.m.` / `p.m.`)**:
   - *Issue*: The model authored `(re.compile(r"\ba\.m\.\b", re.I), "am")`. Because `.` is a non-word character in regex, `\b` matches between word characters (`m`) and non-word characters (`.`), NOT after the trailing dot. Consequently, `"10 a.m."` was not replaced and later punctuation stripping turned it into `"10 a m"`.
   - *Correction*: Replaced `\b` with negative lookahead for word characters: `r"\ba\.m\.(?!\w)"`.

3. **Negation Scope Across Comma Clauses**:
   - *Issue*: In `test_negated_service` with input `"not a cleaning, a checkup"`, the model's token-distance negation check allowed `not` to reach 4 tokens forward across the comma, erroneously negating `checkup`.
   - *Correction*: Updated `has_negation_before()` in `polarity.py` to assert that negation scope never crosses punctuation boundaries (commas, semicolons, periods).

4. **Greeting Turn vs. R1 Silence Ladder Order**:
   - *Issue*: The model generated the turn pipeline with `R1` (silence ladder) inspecting `not turn_input.text.strip()` before the `Greeting` rule. On session creation (turn 0), the empty greeting trigger was intercepted by `R1` as a silence event, replying `"Are you still there?"` instead of the greeting.
   - *Correction*: Reordered the policy execution to prioritize `GREETING` on turn 0 before the silence ladder fires.

---

## 4. Token Accounting

The historical totals below are retained from the project records. GitHub Copilot does not expose a reliable per-session token count in this workspace, so the work completed in the current maintenance session is recorded by activity rather than estimated tokens.

| Phase | Purpose | Input Tokens | Output Tokens | Total |
|---|---|---|---|---|
| Planning | Architectural review & spec | 42,500 | 18,200 | 60,700 |
| Domain Layer | Time, hours, models, repository | 58,100 | 22,400 | 80,500 |
| Brain & NLU | Parsers, polarity, policy rules | 74,300 | 28,900 | 103,200 |
| Tests & Debug | Edge case fixes & AST guard | 28,400 | 11,200 | 39,600 |
| Frontend & Docs | Next.js app, Vitest, docs | 39,800 | 16,800 | 56,600 |
| **Total** | | **243,100** | **97,500** | **340,600** |

### Current Maintenance Session

- **Tool**: GitHub Copilot
- **Work**: Reviewed the design and implementation plan; added 57 natural-English NLU cases; fixed supported intent, date, service, and confirmation variants; fixed speech recognition toggle races; stabilized speech synthesis callback identities; updated the README.
- **Token count**: Not available from the local tool telemetry.

Detailed execution logs are stored in [`docs/ai-usage/session_logs.md`](./docs/ai-usage/session_logs.md).

---

## 5. Compliance with the "One Big Rule"

The primary constraint of the project states:
> *"The brain must be your own code. Do not use a big AI model (like GPT, Claude or Gemini) to decide what happens. Your code decides what the caller wants, what to ask next, and what to do."*

This is strictly enforced and verified by `backend/tests/test_import_guard.py`:
- No language model calls or LLM libraries are included in dependencies or code.
- All decisions are deterministic, rule-based, and covered by automated scenario tests.
