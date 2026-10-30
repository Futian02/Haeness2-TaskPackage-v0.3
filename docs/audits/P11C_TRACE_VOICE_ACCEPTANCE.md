# P11-C Trace / Voice Acceptance

**Status: READY_FOR_OWNER_REVIEW**  
**Scope:** `frontend/src/components/trace/**`, `frontend/src/trace-events/**`, `frontend/src/voice/**`, trace integration regression test, and this audit. No backend, Graph, teacher tool, `App.tsx`, `AssistantMessages.tsx`, or `styles.css` changes in this task.

## Delivered

- `ActivityTrace` retains assistant-ui `MessagePrimitive.GroupedParts`, Reasoning UI, and Tool UI. Persisted events are grouped by recorded `phase`/`iteration` into separately collapsible stages; top-level summary exposes current status, tool count, explicit review count, and elapsed time.
- A stage uses its stored phase/agent/iteration and sequence range. It displays public event summaries, observed tool names, citations, review records, and reported duration or an explicitly approximate timestamp span. Tool rows remain separately expandable.
- `projectActivity` deduplicates `run_id + sequence`, sorts replay events, pairs concurrent same-name calls by `step_id`, sanitizes tool args/results, and keeps unique citation counts. Empty history is an explicit empty state, not a fabricated activity event.
- Model response summaries are labeled as public wording; no private/hidden reasoning is generated. No fictitious file edits or command execution are shown.
- `SpeechInputButton` uses `SpeechRecognition` or `webkitSpeechRecognition`, `zh-CN`, supports start/stop/interim results, unsupported-browser, permission-denied, and microphone-unavailable states, and cleans up on unmount. It only calls `onTranscript`; it has no send/submit path. User-initiated audio/service disclosure is visible.
- Standalone previews are available at `/src/components/trace/demo/?run_id=<existing-run-id>` and `/src/voice/demo/`; neither preview creates a run or sends a transcript.

## Verification evidence

| Command / action | Result |
|---|---|
| `npm run typecheck --prefix frontend` | PASS (`tsc -b --pretty false`) |
| `npm test --prefix frontend -- --run` | PASS: 16 test files, 109 tests |
| `npm run build --prefix frontend` | PASS, Vite production build completed. Existing Rollup warning: the main minified JS chunk exceeds 500 kB. |
| `Invoke-WebRequest "http://127.0.0.1:5174/api/runs/0282582e-d990-42e9-bfa7-918204396520/events?after_sequence=0" -UseBasicParsing` | HTTP 200; 21 events returned via Vite proxy from FastAPI replay. Read-only request against an existing local SQLite Run; no Run was created. |
| Edge trace preview: `http://127.0.0.1:5174/src/components/trace/demo/?run_id=0282582e-d990-42e9-bfa7-918204396520` | Actual persisted replay hydrated as 21 events. Collapsed header: `调查完成 · 查询 2 次 · 审查 1 次 · 589 ms`. Expanding the investigation stage showed `damage_mechanism_query` and `standard_clause_search`; the assistant-ui tool group could be expanded. |
| Microsoft Edge DOM interaction (local Node 24 CDP using built-in `WebSocket`) | Clicked the actual outer trace disclosure, investigation phase, and tool group; verified `aria-expanded=true`, the two persisted tool names, 12 observed stages, and captured expanded screenshot. |
| Edge voice preview with an injected deterministic `SpeechRecognition` test double | Clicked start, injected `湿硫化氢环境温度`, verified the draft contained that text, there was no send button, and the permission-denied UI appeared after a simulated browser error. This validates browser rendering and UI wiring; it is not a live microphone/acoustic-recognition test. |

Evidence screenshots:

- `docs/audits/P11C_activity-edge-collapsed.png` — real FastAPI/SQLite event replay, folded.
- `docs/audits/P11C_activity-edge-expanded.png` — same run with real stage and tool-group expansion.
- `docs/audits/P11C_voice-demo-edge.png` — Edge voice preview, idle state.
- `docs/audits/P11C_voice-demo-edge-transcribed.png` — Edge preview with injected transcript in the draft.

The real event sample is run `0282582e-d990-42e9-bfa7-918204396520`; inspected event sequence is `1..21`, ending at `run_completed`. The actual summary was derived from those persisted event timestamps and `tool_result.duration_ms`; it was not seeded into the preview.

## Test coverage

- Projection: replay ordering, `run_id + sequence` dedupe, legacy fields, phase/iteration, public-only summaries, secret/raw-text filtering, citations, malformed input, tool success/failure, and parallel same-name tool result pairing by `step_id`.
- Grouping: real phases/iterations, unique citations, duration source, review events, terminal labels, and a 240-event stress fixture preserving order and count.
- UI: initially collapsed; explicit top-level and stage expansion; empty state without fabricated steps; run isolation; tool fallback; citations, review, summary and theme rendering.
- Voice: Chrome/Edge API and prefixed API, zh-CN configuration, transcript callback, no-submit behavior, unsupported API, permission denial, missing microphone, synchronous denial, unmount cleanup, and audio-provider disclosure.

## Failed attempts and recovery

- Initial focused tests caught an incorrect permission mapping for synchronous `NotAllowedError`, duplicate reported tool duration in stage aggregation, and outdated assertions/empty-state handling. These were corrected; all focused and full frontend tests now pass.
- `npx vitest ...` was first invoked from the repository root instead of the frontend package and failed with an npm cache `EEXIST`; no project dependency was changed. Correct invocation `npm test --prefix frontend -- --run` passes.
- Port 5173 was occupied/stale (HTTP 502), so the isolated Vite preview used port 5174. The backend on 8000 and original application were not restarted or modified.
- Build completes but reports the existing >500 kB bundle advisory. No chunk-size limit was changed in this scoped task.

## Boundary check

No teacher-tool protocol, backend, Graph, official data, Excel, PDF, or deployment action was changed. `App.tsx` and `AssistantMessages.tsx` remain the responsibility of integration owner A. The preview fetches persisted events with GET only. Browser speech was tested using a deterministic browser API test double; live audio requires explicit user microphone permission and was not claimed as tested.

## Sources consulted

- [assistant-ui: Chain of Thought UI](https://www.assistant-ui.com/docs/guides/chain-of-thought)
- [assistant-ui: Part Grouping](https://www.assistant-ui.com/docs/guides/part-grouping)
- [MDN: SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)
