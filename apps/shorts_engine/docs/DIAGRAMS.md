# Diagrams

## Component Diagram
```mermaid
flowchart LR
  RC[shorts_engine/tools/release_check.ps1] --> V[shorts_engine/tools/verify.ps1]
  V --> L2CLI[shorts_engine/layer2/cli/render_job.py]

  L2CLI --> CORE[shorts_engine/layer2/core/render.py]
  L2CLI --> STORE[shorts_engine/layer2/core/run_store.py]
  CORE --> STORE
  CORE --> L1[shorts_engine/layer1/cli/render_job.py]

  CORE --> RUNS[(shorts_engine/runs/<run_id>/)]
  CORE --> OUT[(shorts_engine/output/*.mp4)]
  L2CLI --> RUNS
  V --> RUNS
```

## Sequence Diagram
```mermaid
sequenceDiagram
  autonumber
  participant U as User/CI
  participant RC as release_check.ps1
  participant V as verify.ps1
  participant L2 as layer2/cli/render_job.py
  participant C as layer2/core/render.py
  participant RS as layer2/core/run_store.py
  participant L1 as layer1/cli/render_job.py
  participant R as runs/<run_id>

  U->>RC: run release_check -Job ...
  RC->>V: run verify -Json
  V->>L2: python -m layer2.cli.render_job --job ...
  L2->>L2: parse/load/validate
  L2->>C: render_from_job(job)
  C->>RS: prepare_run + REQUIRED_ARTIFACTS contract
  alt cache hit (rp.out exists)
    C->>R: write meta.json (cached=True, run_store_version)
  else normal render
    C->>R: write job.layer2.json/job.layer1.json
    C->>L1: subprocess render
    L1-->>C: rc + output
    C->>R: write meta.json (+ trace.txt on fail)
  end
  C-->>L2: {rc, run_id, run_dir, out_path, cached}
  L2->>R: best-effort finalize render_meta/render_trace/layer1_job
  L2->>R: write artifacts_ok_fs/artifacts_missing + timing
  L2-->>V: RESULT ok/fail ...
  V->>R: filesystem check REQUIRED_ARTIFACTS
  V-->>RC: JSON (ok, artifacts_ok_fs, run_store_version_match)
  RC->>RC: hard gate artifacts_ok
  RC-->>U: pass/fail
```

## Evidence
- `shorts_engine/tools/release_check.ps1:L49-L114`
- `shorts_engine/tools/verify.ps1:L240-L347`
- `shorts_engine/layer2/cli/render_job.py:L131-L225`
- `shorts_engine/layer2/core/render.py:L64-L155`
- `shorts_engine/layer2/core/run_store.py:L11-L104`
- `shorts_engine/layer1/cli/render_job.py:L140-L178`
