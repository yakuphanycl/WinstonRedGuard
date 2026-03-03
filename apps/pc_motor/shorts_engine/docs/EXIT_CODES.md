# Exit codes

## Required

- 0: success
- 2: user error (schema/validation)
- 3: runtime/tool error (renderer/ffmpeg/tts)
- 4: internal bug (unexpected exception)

## Notes

- render_job and render_batch must preserve these semantics.
