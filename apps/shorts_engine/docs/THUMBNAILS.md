# Thumbnails (Pack 13)

## Purpose
Deterministic, simple, copyright-safe thumbnail generation for Layer-2 runs.

Output is stored under run artifacts and recorded in `meta.json` so publish flow can reuse it.

## CLI
`python -m shorts_engine.layer2.cli.make_thumb`

Required:
- `--run-id <id>` or `--mp4 <path>`

Optional:
- `--repo-root <path>`
- `--mode gradient_text|frame` (default: `gradient_text`)
- `--size 1280x720|1080x1920` (default: `1280x720`)
- `--text "<string>"`
- `--out <path>`
- `--sec <float>` (frame extraction timestamp, default: `1.0`)
- `--force`
- `--dry-run`

## Modes
- `gradient_text`:
  - Uses Pillow (if available).
  - Generates a gradient background and overlays sanitized text.
- `frame`:
  - Uses ffmpeg to extract a frame from mp4 at `--sec`.
  - Scales/pads to target size.

## Dependencies
- `ffmpeg` is required for `frame` mode.
- Pillow is optional and only required for `gradient_text`.
- No web downloads and no external image/font assets are required.

## Artifacts Contract
`runs/<run_id>/meta.json` artifacts object includes:
- `thumb_path: string|null`
- `thumb_bytes: int|null`
- `thumb_ok: bool`

These keys should remain present in meta contract shape across success/failure paths.

## Determinism Notes
- Stable default output path for run mode: `runs/<run_id>/thumb.png`.
- Re-running without `--force` will keep existing thumbnail and return success with cached-style behavior.
- Byte-for-byte equality can vary across machines when Pillow font rendering differs, but file presence/path/metadata stay stable.

## Recommended Workflow
1. `render_batch` or `render_job` to produce run artifacts.
2. `make_thumb --run-id <run_id> --mode frame` (or `gradient_text`).
3. `publish add --run-id <run_id>` to reuse mp4/thumb paths from meta.
