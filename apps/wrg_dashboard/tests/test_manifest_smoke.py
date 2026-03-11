from __future__ import annotations

import json
from pathlib import Path


def test_dashboard_manifest_bootstrap_contract() -> None:
    app_root = Path(__file__).resolve().parents[1]
    package_json = app_root / "package.json"
    manifest = json.loads(package_json.read_text(encoding="utf8"))

    scripts = manifest.get("scripts", {})
    assert isinstance(scripts, dict)
    assert "dev" in scripts and "vite" in str(scripts["dev"])
    assert "build" in scripts and "vite build" in str(scripts["build"])
    assert "test" in scripts and "vitest" in str(scripts["test"])

    main_entry = manifest.get("main")
    assert isinstance(main_entry, str) and main_entry.strip()
    main_path = app_root / main_entry
    assert main_path.exists()

    main_src = main_path.read_text(encoding="utf8")
    assert "BrowserWindow" in main_src
    assert "loadURL" in main_src or "loadFile" in main_src

    renderer_entry = app_root / "src" / "main.tsx"
    assert renderer_entry.exists()
    renderer_src = renderer_entry.read_text(encoding="utf8")
    assert "createRoot" in renderer_src
