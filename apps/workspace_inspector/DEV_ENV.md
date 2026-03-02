# Development Environment Notes

## Sandbox limitations
In some restricted/sandbox shells, Git/network behavior is limited:
- HTTPS auth cannot prompt, so `fetch`/`push` may fail.
Typical error: `failed to execute prompt script (exit code 66)` and `could not read Username for 'https://github.com'`.
- Global git config may be read-only.
Typical error: `could not lock config file .../.gitconfig: Permission denied`.
- SSH may be blocked or unavailable in sandbox sessions.

## What still works in sandbox
- Run QA scripts, for example: `pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\qa_cli.ps1`
- Create local commits and local tags
- Set repo-local git config (for example `git config --local ...`)

## Recommended local workflow (Windows PowerShell)
Preferred: Git Credential Manager
- `git config --local credential.helper manager-core`
- `git push --tags`
- `git push`

Alternative: SSH (if configured and working locally)
- Use an SSH remote and push normally.

Security warning:
- Do not paste PATs/tokens into chat.
- Avoid embedding tokens directly in remote URLs.

## Release checklist
- `pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\qa_cli.ps1`
- `pwsh -NoProfile -ExecutionPolicy Bypass -File .\tools\release.ps1 -Tag vX.Y.Z -Msg "..."`
- If remote operations fail in sandbox, run the push steps locally.
