def test_import_pc_motor():
    import pc_motor  # noqa: F401


def test_python_help_runs():
    # Minimal deterministic command: "python --help" should be rc=0
    # We intentionally do NOT assume pc_motor has a CLI entrypoint yet.
    import subprocess, sys

    r = subprocess.run([sys.executable, "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    out = (r.stdout or "") + (r.stderr or "")
    assert "usage" in out.lower()
