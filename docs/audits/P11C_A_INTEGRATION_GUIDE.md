# P11-C Integration Guide for Owner A

**Component handoff status: READY_FOR_OWNER_REVIEW**

## ActivityTrace

Import `ActivityTrace` from `frontend/src/components/trace/ActivityTrace.tsx` and pass the run-scoped API/SSE event list already used by the chat:

```tsx
<ActivityTrace
  runId={message.run_id}
  events={events}
  finalText={undefined}
  title="本轮执行记录"
  theme={theme}
/>
```

`ActivityTrace` filters by `runId`, deduplicates persisted/replayed overlap by `run_id + sequence`, and renders an empty folded record when no events exist. Keep assistant answer text as the normal message content; do not pass hidden model reasoning. The stage UI only exposes public event summaries, actual tools, stored references/review facts, and durations.

## SpeechInputButton

Place the component beside the composer and wire its transcript callback to the same controlled draft state used by the text input:

```tsx
<SpeechInputButton
  onTranscript={(transcript) => setDraft(transcript)}
  onStatus={setSpeechStatus}
/>
```

Do not call `submit`, `send`, or the chat API from `onTranscript`. The component intentionally has no send callback. If the composer preserves existing text, implement an explicit append/replace UX in the owner integration layer, then retain the test that proves no submit occurs when recognition reports results.

## Previews and acceptance rerun

Start Vite with the project's existing `/api` proxy and FastAPI running locally:

```powershell
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5174 --strictPort
```

- Trace: `http://127.0.0.1:5174/src/components/trace/demo/?run_id=<existing-run-id>` — read-only GET replay; choose a local run that has `tool_called`, review, and terminal events.
- Voice: `http://127.0.0.1:5174/src/voice/demo/` — controlled draft only, no send action.
- Regression: `npm run typecheck --prefix frontend`; `npm test --prefix frontend -- --run`; `npm run build --prefix frontend`.

When integrating, leave backend event protocol, Graph and teacher tools unchanged. Test the final composer in Edge with a user's explicit microphone permission; browser speech services may transmit audio to the provider.
