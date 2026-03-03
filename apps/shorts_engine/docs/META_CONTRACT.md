# Meta contract

## Required fields

- engine_version
- job_hash
- inputs_hash
- started_at
- ended_at
- duration_ms
- result_rc
- cached
- out_path
- error_type
- artifacts_ok

## Notes

- engine_version should be git short SHA or a semver tag.
- job_hash is SHA256 of normalized job JSON.
- inputs_hash is SHA256 of a stable fingerprint of referenced inputs; null if none.
- error_type is "validation" | "io" | "renderer" | "ffmpeg" | "tts" | "unknown" | "none".
