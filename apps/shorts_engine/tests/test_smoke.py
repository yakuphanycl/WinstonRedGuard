def test_import_layer2():
    import layer2  # noqa: F401


def test_render_batch_help_runs():
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "-m", "layer2.cli.render_batch", "--help"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0
    out = (r.stdout or "") + (r.stderr or "")
    assert "usage" in out.lower()
