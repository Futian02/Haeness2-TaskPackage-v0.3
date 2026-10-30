# R9-B local tracing harness

Isolated Phoenix/OpenInference developer smoke harness. It does not modify `backend/`, `orchestration/`, or `.venv-langgraph`; application tracing defaults to no-op (`TRACE_BACKEND=none`).

## Install (PowerShell, project root)

```powershell
py -3.11 -m venv observability/.venv
./observability/.venv/Scripts/python.exe -m pip install -r observability/requirements.lock.txt
./observability/.venv/Scripts/python.exe -m pip check
```

The lock includes the Phoenix server, Phoenix OTEL adapter, OpenInference LangChain instrumentor, and a compatible `langchain-core`. Langfuse is not included.

## Start isolated localhost Phoenix

```powershell
$env:PHOENIX_TELEMETRY_ENABLED = 'false'
$env:PHOENIX_ALLOW_EXTERNAL_RESOURCES = 'false'
$env:PHOENIX_SQL_DATABASE_URL = 'sqlite:///./docs/audits/R9B_RUNTIME_EVIDENCE/phoenix-local.sqlite'
./observability/.venv/Scripts/python.exe -m phoenix.server.main serve --host 127.0.0.1 --port 6006
```

In a second terminal, from the project root:

```powershell
$env:TRACE_BACKEND = 'phoenix'
$env:PHOENIX_COLLECTOR_ENDPOINT = 'http://127.0.0.1:6006/v1/traces'
./observability/.venv/Scripts/python.exe -m observability.run_real_tools --backend phoenix
```

The runner invokes the frozen teacher tool registry with fixture queries. Tool input/output payloads are not exported; OpenInference input/output fields are redacted and manual spans use a strict attribute allowlist. The Phoenix UI is at `http://127.0.0.1:6006`.

## Tests

```powershell
./observability/.venv/Scripts/python.exe -m unittest tests.test_r9b_observability -v
./observability/.venv/Scripts/python.exe -m pip check
```

The tested failure mode includes an exporter returning `FAILURE`; local tracing remains best-effort and must not change the underlying tool result.

