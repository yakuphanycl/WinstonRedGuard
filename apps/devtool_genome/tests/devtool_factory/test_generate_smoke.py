from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


def _factory_env(factory_root: Path, extra_pythonpath: list[str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if extra_pythonpath:
        pythonpath_parts.extend(extra_pythonpath)
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def _create_fake_app_registry_src(root: Path) -> tuple[Path, Path]:
    src_root = root / "fake_app_registry_src"
    pkg_dir = src_root / "app_registry"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf8")

    registry_path = root / "fake_registry.json"
    (pkg_dir / "core.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "import json",
                "from pathlib import Path",
                "",
                f"REGISTRY_PATH = Path(r'''{registry_path}''')",
                "",
                "def _load() -> dict:",
                "    if not REGISTRY_PATH.exists():",
                "        return {'apps': []}",
                "    return json.loads(REGISTRY_PATH.read_text(encoding='utf8'))",
                "",
                "def _save(data: dict) -> None:",
                "    REGISTRY_PATH.write_text(json.dumps(data, indent=2), encoding='utf8')",
                "",
                "def add_record(",
                "    name: str,",
                "    version: str,",
                "    role: str,",
                "    entrypoint: str,",
                "    status: str = 'active',",
                "    score: int | None = None,",
                "    verified: bool = False,",
                "    source_template: str | None = None,",
                "    created_by: str | None = None,",
                "    app_path: str | None = None,",
                ") -> dict:",
                "    data = _load()",
                "    apps = list(data.get('apps', []))",
                "    if any(app.get('name') == name for app in apps):",
                "        raise ValueError(f'app already exists: {name}')",
                "    app = {",
                "        'name': name,",
                "        'version': version,",
                "        'role': role,",
                "        'entrypoint': entrypoint,",
                "        'status': status,",
                "        'score': score,",
                "        'verified': bool(verified),",
                "        'source_template': source_template,",
                "        'created_by': created_by,",
                "        'app_path': app_path,",
                "    }",
                "    apps.append(app)",
                "    data['apps'] = apps",
                "    _save(data)",
                "    return app",
            ]
        )
        + "\n",
        encoding="utf8",
    )
    return src_root, registry_path


def _create_fake_app_evaluator_src(root: Path, score: int, ok: bool) -> Path:
    src_root = root / "fake_app_evaluator_src"
    pkg_dir = src_root / "app_evaluator"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf8")
    (pkg_dir / "core.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "def run_evaluation(app_path: str, json_out: str | None = None) -> dict:",
                "    return {",
                f"        'score': {score},",
                f"        'ok': {str(ok)},",
                "        'app_path': app_path,",
                "    }",
            ]
        )
        + "\n",
        encoding="utf8",
    )
    return src_root


def test_factory_generate_smoke() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        generate = subprocess.run(
            [sys.executable, "-m", "cli.factory_cli", "generate", "example_tool"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr

        generated_dir = tmp_path / "example_tool"
        expected_files = [
            "README.md",
            "cli.py",
            "core.py",
            "__init__.py",
            "pyproject.toml",
            "tests/test_smoke.py",
        ]
        for filename in expected_files:
            assert (generated_dir / filename).exists(), filename

        readme_text = (generated_dir / "README.md").read_text(encoding="utf8")
        assert any(
            line.strip() == "python -m example_tool.cli <input>"
            for line in readme_text.splitlines()
        )

        pyproject_text = (generated_dir / "pyproject.toml").read_text(encoding="utf8")
        assert 'name = "example_tool"' in pyproject_text
        assert (generated_dir / "__init__.py").exists()
        generated_test_text = (
            generated_dir / "tests" / "test_smoke.py"
        ).read_text(encoding="utf8")
        assert 'importlib.import_module("example_tool.cli")' in generated_test_text

        cli_text = (generated_dir / "cli.py").read_text(encoding="utf8")
        assert "def main():" in cli_text
        assert "if __name__ == \"__main__\":" in cli_text
        assert "main()" in cli_text
        assert "from .core import run" in cli_text
        assert "run(args.input)" in cli_text

        run_cli = subprocess.run(
            [sys.executable, "-m", "example_tool.cli", "hello"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run_cli.returncode == 0, run_cli.stderr

        import_check = subprocess.run(
            [sys.executable, "-c", "import example_tool; import example_tool.cli"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert import_check.returncode == 0, import_check.stderr
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_existing_target_fails() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        (tmp_path / "example_tool").mkdir()

        generate = subprocess.run(
            [sys.executable, "-m", "cli.factory_cli", "generate", "example_tool"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode != 0
        assert "target already exists" in (generate.stderr + generate.stdout)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_invalid_name_fails() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        for invalid_name in ["my tool", "123tool", "tool-name!"]:
            generate = subprocess.run(
                [sys.executable, "-m", "cli.factory_cli", "generate", invalid_name],
                cwd=tmp_path,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            assert generate.returncode != 0
            assert "invalid tool name" in (generate.stderr + generate.stdout).lower()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_keyword_name_fails() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        generate = subprocess.run(
            [sys.executable, "-m", "cli.factory_cli", "generate", "class"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode != 0
        output = (generate.stderr + generate.stdout).lower()
        assert "invalid tool name" in output
        assert "valid python package/module name" in output
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_description() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    description = "Example tool for counting lines"
    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "example_tool",
                "--description",
                description,
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr

        generated_dir = tmp_path / "example_tool"
        readme_text = (generated_dir / "README.md").read_text(encoding="utf8")
        assert description in readme_text

        pyproject_text = (generated_dir / "pyproject.toml").read_text(encoding="utf8")
        assert f'description = "{description}"' in pyproject_text
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_unknown_template_fails() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "example_tool",
                "--template",
                "unknown_template",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode != 0
        assert "unknown template" in (generate.stderr + generate.stdout).lower()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_single_file_cli_template() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "example_tool",
                "--template",
                "single_file_cli",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr

        generated_dir = tmp_path / "example_tool"
        assert (generated_dir / "README.md").exists()
        assert (generated_dir / "pyproject.toml").exists()
        assert (generated_dir / "__init__.py").exists()
        assert (generated_dir / "cli.py").exists()

        run_cli = subprocess.run(
            [sys.executable, "-m", "example_tool.cli", "hello"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert run_cli.returncode == 0, run_cli.stderr
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_wrg_app_template() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "example_app",
                "--template",
                "wrg_app",
                "--description",
                "Example WRG app",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr

        generated_dir = tmp_path / "example_app"
        expected_files = [
            "pyproject.toml",
            "README.md",
            "src/example_app/__init__.py",
            "src/example_app/cli.py",
            "src/example_app/core.py",
            "tests/test_smoke.py",
            "data/.gitkeep",
        ]
        for filename in expected_files:
            assert (generated_dir / filename).exists(), filename

        readme_text = (generated_dir / "README.md").read_text(encoding="utf8")
        assert "python -m example_app.cli" in readme_text

        cli_text = (generated_dir / "src" / "example_app" / "cli.py").read_text(
            encoding="utf8"
        )
        assert "def main() -> int:" in cli_text

        pyproject_text = (generated_dir / "pyproject.toml").read_text(encoding="utf8")
        assert 'name = "example_app"' in pyproject_text
        assert 'description = "Example WRG app"' in pyproject_text

        import_env = env.copy()
        import_env["PYTHONPATH"] = os.pathsep.join(
            [str(generated_dir / "src"), import_env["PYTHONPATH"]]
        )
        import_check = subprocess.run(
            [sys.executable, "-c", "import example_app.cli"],
            cwd=tmp_path,
            env=import_env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert import_check.returncode == 0, import_check.stderr
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_wrg_app_existing_target_fails() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        (tmp_path / "example_app").mkdir()

        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "example_app",
                "--template",
                "wrg_app",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode != 0
        assert "target already exists" in (generate.stderr + generate.stdout)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_without_output_root_keeps_cwd_behavior() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        generate = subprocess.run(
            [sys.executable, "-m", "cli.factory_cli", "generate", "example_tool"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr
        assert (tmp_path / "example_tool").is_dir()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_output_root_generates_under_given_dir() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        output_root = tmp_path / "apps"
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "example_tool",
                "--output-root",
                str(output_root),
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr
        assert (output_root / "example_tool").is_dir()
        assert not (tmp_path / "example_tool").exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_smoke_check_passes_for_wrg_app() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "example_app",
                "--template",
                "wrg_app",
                "--smoke-check",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr
        combined = generate.stdout + generate.stderr
        assert "smoke check passed: example_app" in combined
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_smoke_check_fails_for_missing_wrg_structure() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    env = os.environ.copy()
    pythonpath_parts = [str(factory_root)]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "example_tool",
                "--template",
                "cli_tool",
                "--smoke-check",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode != 0
        combined = (generate.stdout + generate.stderr).lower()
        assert "smoke check failed" in combined
        assert "missing file" in combined
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_register_success_flow() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        fake_src, fake_registry_path = _create_fake_app_registry_src(tmp_path)
        env = _factory_env(factory_root, extra_pythonpath=[str(fake_src)])
        env["APP_REGISTRY_SRC"] = str(fake_src)

        output_root = tmp_path / "apps"
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "ops_guard",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
                "--smoke-check",
                "--register",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr
        combined = generate.stdout + generate.stderr
        assert "smoke check passed: ops_guard" in combined
        assert "registry add passed: ops_guard status=candidate" in combined

        data = json.loads(fake_registry_path.read_text(encoding="utf8"))
        app = next(app for app in data.get("apps", []) if app.get("name") == "ops_guard")
        assert app["status"] == "candidate"
        assert app["score"] is None
        assert app["verified"] is True
        assert app["source_template"] == "wrg_app"
        assert app["created_by"] == "devtool_factory"
        assert app["entrypoint"] == "ops_guard.cli:main"
        assert app["app_path"].endswith("ops_guard")
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_register_duplicate_skips_without_crash() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        fake_src, fake_registry_path = _create_fake_app_registry_src(tmp_path)
        env = _factory_env(factory_root, extra_pythonpath=[str(fake_src)])
        env["APP_REGISTRY_SRC"] = str(fake_src)

        output_root = tmp_path / "apps"
        first = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "ops_guard",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
                "--register",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert first.returncode == 0, first.stderr
        shutil.rmtree(output_root / "ops_guard", ignore_errors=True)

        second = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "ops_guard",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
                "--register",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert second.returncode == 0, second.stderr
        combined = second.stdout + second.stderr
        assert "registry skip: app already exists: ops_guard" in combined

        data = json.loads(fake_registry_path.read_text(encoding="utf8"))
        assert len([app for app in data.get("apps", []) if app.get("name") == "ops_guard"]) == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_register_does_not_write_when_smoke_fails() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        fake_src, fake_registry_path = _create_fake_app_registry_src(tmp_path)
        env = _factory_env(factory_root, extra_pythonpath=[str(fake_src)])
        env["APP_REGISTRY_SRC"] = str(fake_src)

        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "bad_tool",
                "--template",
                "cli_tool",
                "--register",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode != 0
        combined = (generate.stdout + generate.stderr).lower()
        assert "smoke check failed" in combined
        assert not fake_registry_path.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_without_register_keeps_behavior() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        fake_src, fake_registry_path = _create_fake_app_registry_src(tmp_path)
        env = _factory_env(factory_root, extra_pythonpath=[str(fake_src)])
        env["APP_REGISTRY_SRC"] = str(fake_src)

        output_root = tmp_path / "apps"
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "plain_app",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr
        assert (output_root / "plain_app").is_dir()
        assert not fake_registry_path.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_evaluate_pass_reports_score() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        fake_evaluator_src = _create_fake_app_evaluator_src(tmp_path, score=6, ok=True)
        env = _factory_env(factory_root, extra_pythonpath=[str(fake_evaluator_src)])
        env["APP_EVALUATOR_SRC"] = str(fake_evaluator_src)

        output_root = tmp_path / "apps"
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "saha_guard",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
                "--smoke-check",
                "--evaluate",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr
        combined = generate.stdout + generate.stderr
        assert "evaluation passed: saha_guard score=6" in combined
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_evaluate_and_register_success() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        fake_evaluator_src = _create_fake_app_evaluator_src(tmp_path, score=7, ok=True)
        fake_registry_src, fake_registry_path = _create_fake_app_registry_src(tmp_path)
        env = _factory_env(
            factory_root, extra_pythonpath=[str(fake_evaluator_src), str(fake_registry_src)]
        )
        env["APP_EVALUATOR_SRC"] = str(fake_evaluator_src)
        env["APP_REGISTRY_SRC"] = str(fake_registry_src)

        output_root = tmp_path / "apps"
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "saha_guard",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
                "--smoke-check",
                "--evaluate",
                "--min-score",
                "5",
                "--register",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr
        combined = generate.stdout + generate.stderr
        assert "evaluation passed: saha_guard score=7" in combined
        assert "registry add passed: saha_guard status=active" in combined

        data = json.loads(fake_registry_path.read_text(encoding="utf8"))
        app = next(app for app in data.get("apps", []) if app.get("name") == "saha_guard")
        assert app["status"] == "active"
        assert app["score"] == 7
        assert app["verified"] is True
        assert app["source_template"] == "wrg_app"
        assert app["created_by"] == "devtool_factory"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_evaluate_threshold_fail_blocks_registry() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        fake_evaluator_src = _create_fake_app_evaluator_src(tmp_path, score=4, ok=True)
        fake_registry_src, fake_registry_path = _create_fake_app_registry_src(tmp_path)
        env = _factory_env(
            factory_root, extra_pythonpath=[str(fake_evaluator_src), str(fake_registry_src)]
        )
        env["APP_EVALUATOR_SRC"] = str(fake_evaluator_src)
        env["APP_REGISTRY_SRC"] = str(fake_registry_src)

        output_root = tmp_path / "apps"
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "saha_guard",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
                "--smoke-check",
                "--evaluate",
                "--min-score",
                "5",
                "--register",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode != 0
        combined = generate.stdout + generate.stderr
        assert "evaluation failed threshold: score=4 min_score=5" in combined
        assert "registry add skipped: quarantine not allowed" in combined
        assert not fake_registry_path.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_generate_with_evaluate_threshold_fail_and_allow_quarantine() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        fake_evaluator_src = _create_fake_app_evaluator_src(tmp_path, score=4, ok=True)
        fake_registry_src, fake_registry_path = _create_fake_app_registry_src(tmp_path)
        env = _factory_env(
            factory_root, extra_pythonpath=[str(fake_evaluator_src), str(fake_registry_src)]
        )
        env["APP_EVALUATOR_SRC"] = str(fake_evaluator_src)
        env["APP_REGISTRY_SRC"] = str(fake_registry_src)

        output_root = tmp_path / "apps"
        generate = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "saha_guard",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
                "--smoke-check",
                "--evaluate",
                "--min-score",
                "5",
                "--allow-quarantine",
                "--register",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert generate.returncode == 0, generate.stderr
        combined = generate.stdout + generate.stderr
        assert "evaluation failed threshold: score=4 min_score=5" in combined
        assert "registry add passed: saha_guard status=quarantine" in combined

        data = json.loads(fake_registry_path.read_text(encoding="utf8"))
        app = next(app for app in data.get("apps", []) if app.get("name") == "saha_guard")
        assert app["status"] == "quarantine"
        assert app["score"] == 4
        assert app["verified"] is True
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_factory_duplicate_quarantine_register_skips() -> None:
    project_root = Path(__file__).resolve().parents[2]
    factory_root = project_root / "devtool_factory"
    local_tmp_root = project_root / ".tmp_tests"
    local_tmp_root.mkdir(exist_ok=True)

    tmp_path = local_tmp_root / f"generate_smoke_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=False)
    try:
        fake_evaluator_src = _create_fake_app_evaluator_src(tmp_path, score=3, ok=True)
        fake_registry_src, fake_registry_path = _create_fake_app_registry_src(tmp_path)
        env = _factory_env(
            factory_root, extra_pythonpath=[str(fake_evaluator_src), str(fake_registry_src)]
        )
        env["APP_EVALUATOR_SRC"] = str(fake_evaluator_src)
        env["APP_REGISTRY_SRC"] = str(fake_registry_src)

        output_root = tmp_path / "apps"
        first = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "saha_guard",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
                "--smoke-check",
                "--evaluate",
                "--min-score",
                "5",
                "--allow-quarantine",
                "--register",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert first.returncode == 0, first.stderr
        shutil.rmtree(output_root / "saha_guard", ignore_errors=True)

        second = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli.factory_cli",
                "generate",
                "saha_guard",
                "--template",
                "wrg_app",
                "--output-root",
                str(output_root),
                "--smoke-check",
                "--evaluate",
                "--min-score",
                "5",
                "--allow-quarantine",
                "--register",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert second.returncode == 0, second.stderr
        combined = second.stdout + second.stderr
        assert "registry skip: app already exists: saha_guard" in combined

        data = json.loads(fake_registry_path.read_text(encoding="utf8"))
        assert len([app for app in data.get("apps", []) if app.get("name") == "saha_guard"]) == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
