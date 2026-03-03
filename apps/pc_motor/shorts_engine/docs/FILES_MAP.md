# Files Map

| Path | Role | Reads | Writes | Called by |
|---|---|---|---|---|
| `shorts_engine/layer2/cli/render_job.py` | Layer-2 CLI orchestrator; validation -> core render -> best-effort finalize/telemetry | job file, schema, `meta.json`, legacy output artifacts | `meta.json`, fallback `trace.txt`, `render_meta.json`, copied legacy artifacts | `python -m layer2.cli.render_job`; invoked by `shorts_engine/tools/verify.ps1` |
| `shorts_engine/layer2/core/render.py` | Core render pipeline; run-store prepare, cache-hit handling, Layer-1 subprocess | Layer-2 job dict, run_store contract, Layer-1 return code/output | `job.layer2.json`, `job.layer1.json`, `stdout.log`, `meta.json`, `trace.txt` (fail), run-local mp4 + requested output copy | called by `shorts_engine/layer2/cli/render_job.py` |
| `shorts_engine/layer2/core/run_store.py` | Run-store contract source (`RUN_STORE_VERSION`, `REQUIRED_ARTIFACTS`) + required-artifact checker | input job dict, run directory contents | run path definitions (via `RunPaths`), JSON writes via helper | called by `shorts_engine/layer2/core/render.py` and `shorts_engine/layer2/cli/render_job.py` |
| `shorts_engine/tools/verify.ps1` | Smoke verify gate + JSON contract emitter (`ok`, artifacts fields, version match) | compile targets, Layer-2 RESULT line, run dir artifacts, `meta.json`, `render_meta.json` | none (reports JSON/console only) | called by `shorts_engine/tools/release_check.ps1` and humans/CI |
| `shorts_engine/tools/release_check.ps1` | Release gate wrapper enforcing compile, verify, and artifact gate policy | verify JSON output, docs presence | none | humans/CI release command |
| `shorts_engine/tools/explain.ps1` | One-command docs scaffolder and reconnaissance generator | repo files (`layer2/core/run_store.py`, `layer2/cli/*.py`, etc.) | `docs/_generated/*`, `tasks/codex_explain_prompt.txt`, missing-doc skeletons | humans/CI tooling |

## Evidence
- `shorts_engine/layer2/cli/render_job.py:L113-L225`
- `shorts_engine/layer2/core/render.py:L50-L155`
- `shorts_engine/layer2/core/run_store.py:L11-L104`
- `shorts_engine/tools/verify.ps1:L71-L167`
- `shorts_engine/tools/verify.ps1:L317-L347`
- `shorts_engine/tools/release_check.ps1:L49-L114`
- `shorts_engine/tools/explain.ps1:L52-L253`
