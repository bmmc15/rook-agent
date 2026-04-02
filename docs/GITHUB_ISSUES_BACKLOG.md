# Rook Agent — GitHub issues backlog

This document maps **labels**, **epics**, and **detailed issue drafts** you can paste into GitHub Issues. It reflects the current architecture: async Python core (`Agent`, `MessageRouter`, `EventBus`, `StateMachine`), Rich terminal UI (`RookApp`), Gemini Live audio (`GeminiLiveProvider`), OpenClaw WebSocket (`OpenClawClient`), SQLite storage, and REPL commands.

---

## How to use this file

1. In the GitHub repo: **Settings → General → Issues** — enable issues if needed.
2. **Settings → Labels** — create the labels listed below (colors are suggestions).
3. Create **Milestones** if you want (e.g. `v0.2-core`, `v0.3-mac-ui`).
4. Open issues from the sections below; copy the **Title** and **Body** blocks.

---

## Label taxonomy (tags)

Use a consistent prefix so filters stay readable.

| Label | Color (hex) | Meaning |
|-------|----------------|---------|
| `type:bug` | `#d73a4a` | Incorrect behavior or regression |
| `type:feature` | `#0e8a16` | New capability |
| `type:chore` | `#fef2c0` | Tooling, deps, housekeeping |
| `type:docs` | `#0075ca` | Documentation only |
| `type:test` | `#bfdadc` | Tests, fixtures, CI |
| `area:core` | `#5319e7` | Agent, events, state machine, config |
| `area:audio` | `#1d76db` | Capture, playback, Gemini Live, waveform |
| `area:openclaw` | `#fbca04` | WebSocket client, streaming, device auth |
| `area:cli` | `#c5def5` | Rich UI, renderer, widgets, input |
| `area:storage` | `#bfd4f2` | SQLite, repositories, schema |
| `area:tasks` | `#f9d0c4` | Task manager, executor, coding delegation |
| `area:mac-app` | `#d4c5f9` | macOS menu bar app, native shell, animations |
| `priority:P0` | `#b60205` | Blocker |
| `priority:P1` | `#d93f0b` | High |
| `priority:P2` | `#fbca04` | Medium |
| `priority:P3` | `#cccccc` | Low |
| `good-first-issue` | `#7057ff` | Suitable for newcomers |
| `needs-design` | `#e99695` | UX/visual/animation spec TBD |
| `breaking-change` | `#000000` | API or behavior incompatible with prior release |

**Optional GitHub Projects fields:** `Epic`, `Estimate`, `Platform` (macOS / Linux / CI).

---

## Epics (umbrella themes)

| Epic ID | Title | Scope |
|---------|--------|--------|
| E1 | Core reliability & observability | Config, logging, state correctness, error surfaces |
| E2 | Voice pipeline completion | STT/TTS, barge-in, timeouts, provider parity |
| E3 | OpenClaw production readiness | Connection lifecycle, retries, streaming UX |
| E4 | Task & session UX | Task manager wired to UI, progress, panic/stop |
| E5 | Test & CI hardening | Unit/integration, mocks, coverage gates |
| E6 | **macOS menu bar client** | Native UI, animations, text input, parity with CLI |

---

## Issue drafts — Core & infrastructure

### Issue C1 — Centralize public API surface for multiple UIs

**Title:** `feat(core): define stable facade for CLI and future macOS client`

**Labels:** `type:feature`, `area:core`, `priority:P2`

**Body:**
- **Goal:** Expose a small async API (e.g. `start_session`, `send_text`, `start_listening`, `stop_listening`, `subscribe_events`) so terminal and macOS apps share one integration path instead of duplicating `RookApp` internals.
- **Tasks:** Document lifecycle; ensure `Agent`, `EventBus`, and `StateMachine` are usable without Rich; avoid importing `rook.cli` from future native shell.
- **Acceptance:** Second “headless” harness can drive the same flows as `main.py` without instantiating `Renderer`.

---

### Issue C2 — Config validation and secrets hygiene

**Title:** `chore(config): validate env on startup and redact secrets in logs`

**Labels:** `type:chore`, `area:core`, `priority:P2`

**Body:**
- Validate combinations (e.g. OpenClaw URL without key warns clearly).
- Ensure API keys never appear in structured logs or UI transcripts.
- **Acceptance:** Manual test with `LOG_LEVEL=DEBUG` shows redacted values.

---

### Issue C3 — State machine coverage for edge transitions

**Title:** `test(core): expand state machine tests for SPEAKING → LISTENING and ERROR recovery`

**Labels:** `type:test`, `area:core`, `priority:P2`

**Body:**
- Map real `RookApp` transitions against `TRANSITIONS` in `StateMachine`.
- Add tests for forced transitions and invalid paths.
- **Acceptance:** All documented app states reachable from integration scenarios.

---

## Issue drafts — Audio & voice

### Issue A1 — Document and test Gemini Live session modes

**Title:** `docs(audio): document STT vs TTS vs audio_mode Gemini sessions`

**Labels:** `type:docs`, `area:audio`, `priority:P3`

**Body:**
- Explain `session_label`, modalities, and when each provider instance runs.
- Link to `prompts/gemini_session.md` behavior.
- **Acceptance:** New contributor can trace one voice turn end-to-end.

---

### Issue A2 — Barge-in and interrupt semantics

**Title:** `feat(audio): implement barge-in (user interrupts assistant TTS)`

**Labels:** `type:feature`, `area:audio`, `priority:P1`, `needs-design`

**Body:**
- Use `BARGE_IN_THRESHOLD` and streaming playback path.
- Define UX: terminal first; note implications for macOS orb/waveform.
- **Acceptance:** Speaking → user talks → playback stops and new turn starts.

---

### Issue A3 — Voice timeout and silence handling

**Title:** `feat(audio): align VOICE_TIMEOUT_SECONDS with LISTENING state`

**Labels:** `type:feature`, `area:audio`, `priority:P2`

**Body:**
- Auto-stop recording; transition to IDLE or PROCESSING consistently.
- Emit events for UI (and future menu bar) to animate “timeout” vs “send”.
- **Acceptance:** Unit tests with mock clock or short timeout.

---

## Issue drafts — OpenClaw

### Issue O1 — Reconnection backoff and user-visible status

**Title:** `feat(openclaw): exponential backoff and status events for WS reconnect`

**Labels:** `type:feature`, `area:openclaw`, `priority:P2`

**Body:**
- On disconnect: publish `EventType` suitable for status strip (CLI + macOS).
- Avoid tight reconnect loops; cap attempts; surface last error string safely (no tokens).
- **Acceptance:** Simulated drop recovers without duplicating requests.

---

### Issue O2 — Chunk merge and streaming transcript tests

**Title:** `test(openclaw): extend chunk merge tests for partial and out-of-order frames`

**Labels:** `type:test`, `area:openclaw`, `priority:P2`

**Body:**
- Build on `tests/unit/test_openclaw_chunk_merge.py`.
- Cover large payloads and cancellation mid-stream.

---

## Issue drafts — CLI (current terminal UI)

### Issue U1 — REPL command parity with README

**Title:** `fix(cli): register /agent and /audio commands (or update help text)`

**Labels:** `type:bug`, `area:cli`, `priority:P2`

**Body:**
- `CommandHandler` help lists `/agent` and `/audio` but dispatcher may omit them — align implementation and docs.
- **Acceptance:** `/help` matches behavior; unknown commands unchanged.

---

### Issue U2 — Task list wired to storage

**Title:** `feat(cli): implement /tasks using task manager and SQLite`

**Labels:** `type:feature`, `area:cli`, `area:tasks`, `priority:P2`

**Body:**
- Replace placeholder “No tasks yet” with real queries when task persistence exists.
- **Acceptance:** Creating a task shows in `/tasks`.

---

## Issue drafts — Storage & tasks

### Issue T1 — Session and message persistence audit

**Title:** `chore(storage): audit schema usage for sessions, messages, tasks`

**Labels:** `type:chore`, `area:storage`, `priority:P3`

**Body:**
- Ensure repositories are used from agent paths; document DB file location and backup.
- **Acceptance:** README “Database Issues” section matches code paths.

---

## Issue drafts — Testing & CI

### Issue I1 — CI workflow (lint + pytest)

**Title:** `chore(ci): GitHub Actions for ruff/black check and pytest`

**Labels:** `type:chore`, `type:test`, `priority:P2`

**Body:**
- Python 3.11 matrix; cache deps; fail on lint/test failure.
- **Acceptance:** Green on PR; documented in CONTRIBUTING if added later.

---

### Issue I2 — Integration test harness (mock Gemini)

**Title:** `test(integration): harness with mock voice provider for E2E state flow`

**Labels:** `type:test`, `area:audio`, `priority:P3`

**Body:**
- Use existing `rook/audio/providers/mock.py` where possible.
- **Acceptance:** One async test runs IDLE → LISTENING → PROCESSING without real API.

---

## Epic E6 — macOS menu bar application (detailed)

**Suggested repo layout:** `macos/RookMenuBar/` (or `apps/rook-menubar/`) — Swift package or Xcode project kept separate from Python package but versioned together.

**Shared principles:**
- **Parity:** Same capabilities as CLI: text input, push-to-talk (or hold-to-talk), voice output, OpenClaw chat/tasks, `/command` equivalents, connection status, panic/stop.
- **Separation:** Prefer a **thin native shell** (SwiftUI) + **existing Python backend** via XPC/subprocess/gRPC/localhost socket, *or* progressively port orchestration to Swift only where needed (audio is often easier native on macOS).
- **Animations:** Distinct visual language for **IDLE**, **LISTENING** (mic active, waveform or particle field), **PROCESSING** (subtle pulse), **SPEAKING** (assistant waveform or orb). Respect Reduce Motion accessibility.

---

### Issue M0 — Decision record: architecture for macOS + Python

**Title:** `docs(mac-app): ADR — embedding Python vs IPC vs full Swift port`

**Labels:** `type:docs`, `area:mac-app`, `priority:P1`, `needs-design`

**Body:**
- Compare: (1) Bundle Python with PyInstaller + run subprocess, (2) Swift calling `PythonKit` / embedded interpreter, (3) Backend HTTP/WebSocket service started by LaunchAgent, (4) Full Swift rewrite of orchestration.
- Criteria: cold start, signing/notarization, debugging, team skills, latency for audio.
- **Acceptance:** ADR committed under `docs/adr/` with chosen direction and risks.

---

### Issue M1 — Create `macos/` directory and Xcode project skeleton

**Title:** `feat(mac-app): scaffold menu bar extra with SwiftUI template`

**Labels:** `type:feature`, `area:mac-app`, `priority:P1`

**Body:**
- Menu bar icon (NSStatusItem); no dock icon if possible; dark/light aware.
- Empty popover or NSPanel placeholder.
- **Acceptance:** Builds on Xcode 15+; runs on macOS 14+; README snippet for build steps.

---

### Issue M2 — Main UI: transcript + text field + send

**Title:** `feat(mac-app): text input and message list bound to backend`

**Labels:** `type:feature`, `area:mac-app`, `priority:P1`

**Body:**
- Multiline or single-line input; send on Enter; Shift+Enter for newline if multiline.
- Scrollable transcript; distinguish user vs assistant vs system (OpenClaw request IDs).
- **Acceptance:** Typing a message reaches same routing as CLI text path (`Agent.process_message` or facade from C1).

---

### Issue M3 — Listening animation (mic capture)

**Title:** `feat(mac-app): LISTENING state — animated visualization driven by RMS/levels`

**Labels:** `type:feature`, `area:mac-app`, `area:audio`, `priority:P1`, `needs-design`

**Body:**
- Subscribe to audio level events from backend or use `AVAudioEngine` tap if capture moves native-side.
- Visual: waveform bars, breathing ring, or particle flow — **modern, minimal**, 60fps where possible.
- **Acceptance:** Animation starts/stops in sync with LISTENING; low CPU when idle.

---

### Issue M4 — Speaking animation (TTS playback)

**Title:** `feat(mac-app): SPEAKING state — animation synced to playback`

**Labels:** `type:feature`, `area:mac-app`, `area:audio`, `priority:P1`, `needs-design`

**Body:**
- Different palette/motion than LISTENING to avoid confusion.
- Optional: frequency bands if backend exposes them; else envelope follower.
- **Acceptance:** User can tell “assistant talking” vs “mic open” without reading text.

---

### Issue M5 — Push-to-talk / global shortcut

**Title:** `feat(mac-app): global hotkey for PTT and optional menu bar click modes`

**Labels:** `type:feature`, `area:mac-app`, `priority:P2`

**Body:**
- Map to same semantics as `VOICE_ACTIVATION_KEY` where applicable.
- macOS permissions: Microphone usage description in `Info.plist`.
- **Acceptance:** Holding shortcut matches LISTENING lifecycle; releasing ends capture.

---

### Issue M6 — Backend bridge: spawn and health-check Python core

**Title:** `feat(mac-app): launch and supervise rook backend (IPC contract)`

**Labels:** `type:feature`, `area:mac-app`, `area:core`, `priority:P1`

**Body:**
- Define protocol (JSON lines over stdin/stdout, Unix socket, or gRPC).
- Messages: `config_snapshot`, `state_changed`, `transcript_delta`, `audio_level`, `error`.
- Restart policy on crash; surface last error in UI.
- **Acceptance:** Menu app works when installed from a dev path; documented env loading (`.env`).

---

### Issue M7 — OpenClaw and “coding task” flows in UI

**Title:** `feat(mac-app): commands for tasks, panic, and connection status`

**Labels:** `type:feature`, `area:mac-app`, `area:openclaw`, `priority:P2`

**Body:**
- Buttons or slash commands for `/code`, `/panic`, `/status` equivalents.
- Show WS state: connecting / connected / error with retry.
- **Acceptance:** Parity with CLI for documented OpenClaw flows.

---

### Issue M8 — Settings: bundle ID, permissions, About

**Title:** `feat(mac-app): settings window — API keys path, audio device, theme`

**Labels:** `type:feature`, `area:mac-app`, `priority:P2`

**Body:**
- Secure storage for secrets (Keychain); avoid plaintext in UserDefaults for keys.
- Link to repo / version.
- **Acceptance:** First-run experience explains mic permission.

---

### Issue M9 — Packaging: signed build + notarization checklist

**Title:** `chore(mac-app): release pipeline notes for signing and notarization`

**Labels:** `type:chore`, `area:mac-app`, `priority:P3`

**Body:**
- Apple Developer Program requirements; hardened runtime; entitlements for mic/network.
- Optional: ship embedded Python or document external `pip install rook-agent`.
- **Acceptance:** Checklist in `docs/macos-release.md` (or section in this file moved later).

---

### Issue M10 — Accessibility

**Title:** `feat(mac-app): VoiceOver labels and Reduce Motion support`

**Labels:** `type:feature`, `area:mac-app`, `priority:P2`

**Body:**
- VoiceOver: status, last message, button names.
- Reduce Motion: replace continuous loops with static or infrequent updates.
- **Acceptance:** Audit with Accessibility Inspector.

---

## Milestone suggestion

| Milestone | Issues |
|-----------|--------|
| **v0.2 — Core polish** | C1, C2, C3, U1, O1 |
| **v0.3 — Voice UX** | A2, A3, I2 |
| **v0.4 — macOS MVP** | M0, M1, M2, M6, M3, M4 |
| **v0.5 — macOS parity** | M5, M7, M8, M10, M9 |

---

## Quick copy-paste: first five macOS issues (minimal set)

1. **M0** — ADR (architecture) — `type:docs`, `area:mac-app`, `priority:P1`
2. **M1** — Xcode skeleton — `type:feature`, `area:mac-app`, `priority:P1`
3. **M6** — IPC to Python — `type:feature`, `area:mac-app`, `area:core`, `priority:P1`
4. **M2** — Text in/out — `type:feature`, `area:mac-app`, `priority:P1`
5. **M3** + **M4** — Listen/speak animations — `type:feature`, `area:mac-app`, `priority:P1`

---

*Generated for the rook-agent codebase: Python async core, Rich CLI, Gemini Live, OpenClaw, SQLite. Update issue bodies when implementation choices (especially M0) are locked.*
