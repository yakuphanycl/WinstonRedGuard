# WRG Control Center v0.1

## What this app is

- Read-only desktop control center for WinstonRedGuard.
- Local-first observer for:
  - `artifacts/company_health.json`
  - `artifacts/policy_check.json`
  - `artifacts/governance_check.json`
  - `apps/app_registry/data/registry.json`
- Deterministic UI over normalized adapter data + derived insights.

## What this app is not

- Not a mutating admin panel.
- Not an orchestration backend.
- Not a write-capable operator console.
- Not a command runner.

## Validation commands

```bash
cd apps/wrg_dashboard
npm install
npm run test
npm run build:renderer
npm run validate
```

Desktop flows:

```bash
npm run dev:desktop
npm run desktop
npm run diagnose:desktop
npm run package:desktop
npm run dist:desktop
```

- `dev:desktop`: renderer dev server + Electron shell.
- `desktop`: runs Electron shell against built `dist/` output.
- `diagnose:desktop`: diagnosis-only output for packaging lane context and cache location.
- `package:desktop`: unpacked desktop packaging lane (`electron-builder --dir`).
- `dist:desktop`: distributable lane (`electron-builder --win nsis`).

## Desktop packaging usage (Windows)

From `apps/wrg_dashboard`:

1. Desktop dev run (hot reload renderer + Electron shell):
   - `npm run dev:desktop`
2. Build unpacked desktop app:
   - `npm run pack:desktop`
3. Build Windows installer (`.exe` via NSIS):
   - `npm run dist:desktop`
4. Quick artifact check:
   - `dir out`

Expected artifact locations:

- Unpacked app: `out/win-unpacked/`
- NSIS installer: `out/WRG Control Center-Setup-<version>.exe`

How to test unpacked app:

- Run `out\\win-unpacked\\WRG Control Center.exe`
- Verify shell loads and data panels render as expected.

How to install generated `.exe`:

- Run the generated installer from `out\\`.
- Follow installer prompts (installation directory can be changed).
- Launch from desktop/start-menu shortcut "WRG Control Center".

## Desktop icon resource

- Electron Builder now uses `build/icon.ico` for Windows builds.
- Current `build/icon.ico` is a temporary placeholder to avoid default Electron icon usage.
- Replace `build/icon.ico` with the product's final branded `.ico` asset when available.

## Known environment gotcha (packaging)

- Packaging artifacts can be locked by external tools (editors, file watchers, antivirus scanners, indexers).
- If packaging fails with file-lock symptoms, close those tools and retry `npm run pack:desktop` or `npm run dist:desktop`.

Important:

- `build:renderer` success means renderer build is healthy.
- `package:desktop` / `dist:desktop` success is a separate desktop packaging concern.
- Renderer success does not imply distributable success.

## Status matrix

| Area | Status | Note |
|---|---|---|
| Shell layout (Overview/Workers/Governance/Artifacts/Signals/Settings) | Ready | Implemented and active |
| Bilingual UI (EN/TR) | Ready | Header + settings toggle, persisted in localStorage |
| Adapter/insight separation | Ready | Preserved; UI remains render-only |
| Source-state model (`valid/partial/missing/invalid`) | Ready | Unchanged semantics |
| Read-only scope | Ready | No mutation actions |
| Test status | Ready | Renderer tests pass locally |
| Renderer build status | Ready | `npm run build:renderer` passes locally |
| Desktop distributable status | Environment-sensitive | Packaging may fail on some Windows setups due to symlink/sign tooling privileges |

## Desktop action layer (read-only)

Settings page exposes a narrow allowlisted desktop action set:

- open repository root
- open artifacts folder
- open reports folder
- open registry file
- open registry folder

Rules:

- Electron-only capability (disabled in browser mode)
- explicit allowlist only
- no arbitrary path input
- no command execution
- no write side effects

## Known limitations

- `electron-builder` packaging can fail in restricted Windows environments where symlink/sign tooling prerequisites are not available.
- Typical failure signal in this environment: winCodeSign extraction cannot create symbolic links (`privilege not held`).
- This limitation is environment/tooling related, not treated as application logic success.

## Windows packaging diagnosis (truth-first)

If `npm run package:desktop` or `npm run dist:desktop` fails with symbolic link / privilege errors:

1. Confirm renderer lane first:
   - `npm run build:renderer`
2. Run diagnosis lane:
   - `npm run diagnose:desktop`
3. Verify Windows environment conditions:
   - Developer Mode enabled (symlink privilege behavior)
   - shell elevation policy in your environment
   - enterprise group policy restrictions
   - antivirus/security tooling interference
4. Check electron-builder tool cache path reported by `diagnose:desktop` (winCodeSign extraction location).

This failure class is typically OS/tooling privilege related unless evidence shows app-code breakage.
