from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from ..core.version import __version__


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MANIFEST_SCHEMA_VERSION = "0.1"


@dataclass(frozen=True)
class ReleasePaths:
    repo_root: Path
    shorts_root: Path
    version_file: Path
    changelog_file: Path
    dist_dir: Path
    release_check: Path
    release_check_job: str


def _paths() -> ReleasePaths:
    shorts_root = Path(__file__).resolve().parents[2]
    repo_root = shorts_root.parent
    return ReleasePaths(
        repo_root=repo_root,
        shorts_root=shorts_root,
        version_file=shorts_root / "layer2" / "core" / "version.py",
        changelog_file=shorts_root / "CHANGELOG.md",
        dist_dir=shorts_root / "dist",
        release_check=shorts_root / "tools" / "release_check.ps1",
        release_check_job="layer2/examples/min_job.json",
    )


def _iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _json_dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_semver(v: str) -> tuple[int, int, int]:
    m = SEMVER_RE.match(v.strip())
    if not m:
        raise ValueError(f"invalid semver: {v}")
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _format_semver(parts: tuple[int, int, int]) -> str:
    return f"{parts[0]}.{parts[1]}.{parts[2]}"


def _bump(old_v: str, part: str) -> str:
    major, minor, patch = _parse_semver(old_v)
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise ValueError(f"invalid bump part: {part}")
    return _format_semver((major, minor, patch))


def _update_version_file(version_file: Path, new_v: str) -> None:
    txt = version_file.read_text(encoding="utf-8-sig")
    if "__version__" not in txt:
        raise RuntimeError(f"version symbol not found: {version_file}")
    new_txt = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new_v}"', txt, count=1)
    version_file.write_text(new_txt, encoding="utf-8")


def _ensure_changelog(changelog_path: Path) -> None:
    if changelog_path.exists():
        return
    header = (
        "# Changelog\n\n"
        "All notable changes to this project are documented in this file.\n\n"
    )
    changelog_path.write_text(header, encoding="utf-8")


def _prepend_changelog_entry(changelog_path: Path, version: str, date_yyyy_mm_dd: str) -> None:
    _ensure_changelog(changelog_path)
    content = changelog_path.read_text(encoding="utf-8-sig")
    section = (
        f"## [{version}] - {date_yyyy_mm_dd}\n"
        "- Added ...\n"
        "- Fixed ...\n\n"
    )
    if f"## [{version}] - " in content:
        return
    if content.startswith("# Changelog"):
        first_break = content.find("\n\n")
        if first_break == -1:
            new_content = content.rstrip() + "\n\n" + section
        else:
            insert_pos = first_break + 2
            new_content = content[:insert_pos] + section + content[insert_pos:]
    else:
        new_content = "# Changelog\n\n" + section + content
    changelog_path.write_text(new_content, encoding="utf-8")


def _git_clean() -> bool | None:
    try:
        r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=False)
        if r.returncode != 0:
            return None
        return not bool((r.stdout or "").strip())
    except Exception:
        return None


def _git_commit() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        s = (r.stdout or "").strip()
        return s or None
    except Exception:
        return None


def _git_branch() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=False)
        s = (r.stdout or "").strip()
        return s or None
    except Exception:
        return None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m shorts_engine.layer2.cli.release")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("status", help="show release status")

    b = sub.add_parser("bump", help="bump version and create changelog stub")
    b_group = b.add_mutually_exclusive_group(required=True)
    b_group.add_argument("--part", choices=["patch", "minor", "major"])
    b_group.add_argument("--set", dest="set_version")

    build = sub.add_parser("build", help="run gates and build dist zip")
    build.add_argument("--skip-gates", action="store_true", help="skip release_check gate (for internal smoke use)")
    build.add_argument("--job", dest="job", default=None, help="job path for release_check")
    return p.parse_args(argv)


def _run_release_check(paths: ReleasePaths, job: str | None) -> tuple[bool, str]:
    ps = shutil.which("pwsh") or shutil.which("powershell")
    if not ps:
        return False, "PowerShell not found (pwsh/powershell)"
    job_arg = job or paths.release_check_job
    cmd = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(paths.release_check), "-Job", job_arg]
    r = subprocess.run(cmd, cwd=str(paths.shorts_root), capture_output=True, text=True, check=False)
    if r.returncode != 0:
        stderr = (r.stderr or "").strip()
        stdout = (r.stdout or "").strip()
        msg = stderr if stderr else stdout
        msg = msg[-1000:] if msg else f"release_check failed rc={r.returncode}"
        return False, msg
    return True, "OK"


def _should_include(rel_posix: str, included_roots: list[str], excluded_globs: list[str]) -> bool:
    # include roots first
    root_ok = False
    for root in included_roots:
        rp = root.rstrip("/")
        if rel_posix == rp or rel_posix.startswith(rp + "/"):
            root_ok = True
            break
    if not root_ok:
        return False
    # exclude checks
    p = Path(rel_posix)
    for g in excluded_globs:
        if p.match(g):
            return False
    return True


def _collect_release_files(paths: ReleasePaths) -> tuple[list[Path], list[str], list[str]]:
    included_roots = [
        "shorts_engine/layer1",
        "shorts_engine/layer2",
        "shorts_engine/tools",
        "shorts_engine/docs",
        "shorts_engine/CHANGELOG.md",
        "shorts_engine/README.md",
        "shorts_engine/LICENSE",
    ]
    excluded_globs = [
        "**/__pycache__/**",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.mp4",
        "**/runs/**",
        "**/output/**",
        "**/_tmp/**",
        "**/_junk/**",
        "**/dist/**",
        "shorts_engine/tools/output/**",
    ]
    out: list[Path] = []
    for f in paths.shorts_root.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(paths.repo_root).as_posix()
        if _should_include(rel, included_roots, excluded_globs):
            out.append(f)
    out.sort(key=lambda x: x.relative_to(paths.repo_root).as_posix())
    return out, included_roots, excluded_globs


def _build_zip(paths: ReleasePaths, version: str) -> tuple[Path, int, int, list[str], list[str]]:
    files, included_roots, excluded_globs = _collect_release_files(paths)
    zip_path = paths.dist_dir / f"shorts_engine_{version}.zip"
    paths.dist_dir.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    total_bytes = 0
    with ZipFile(zip_path, mode="w", compression=ZIP_DEFLATED, compresslevel=9) as zf:
        for f in files:
            arc = f.relative_to(paths.repo_root).as_posix()
            zf.write(f, arcname=arc)
            total_bytes += int(f.stat().st_size)
    return zip_path, len(files), total_bytes, included_roots, excluded_globs


def _cmd_status() -> int:
    out = {"ok": True, "exit_code": 0, "version": __version__, "git_clean": _git_clean()}
    print(f"release status: version={__version__} git_clean={out['git_clean']}")
    print(json.dumps(out, ensure_ascii=False))
    return 0


def _cmd_bump(args: argparse.Namespace) -> int:
    try:
        paths = _paths()
        old_v = __version__
        if args.set_version:
            _parse_semver(str(args.set_version))
            new_v = str(args.set_version)
        else:
            new_v = _bump(old_v, str(args.part))
        _update_version_file(paths.version_file, new_v)
        _prepend_changelog_entry(paths.changelog_file, new_v, datetime.now().strftime("%Y-%m-%d"))
        out = {"ok": True, "exit_code": 0, "old_version": old_v, "new_version": new_v}
        print(f"release bump: {old_v} -> {new_v}")
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except ValueError as e:
        print(f"ERROR: {e}")
        return 2
    except Exception as e:
        print(f"ERROR: {e}")
        print(json.dumps({"ok": False, "exit_code": 1, "error": str(e)}, ensure_ascii=False))
        return 1


def _cmd_build(args: argparse.Namespace) -> int:
    try:
        paths = _paths()
        gates_passed = True
        if not bool(args.skip_gates):
            gates_passed, msg = _run_release_check(paths, args.job)
            if not gates_passed:
                print(f"ERROR: release gates failed: {msg}")
                print(
                    json.dumps(
                        {"ok": False, "exit_code": 2, "version": __version__, "error": "release_check_failed", "message": msg},
                        ensure_ascii=False,
                    )
                )
                return 2

        zip_path, file_count, total_bytes, included_roots, excluded_globs = _build_zip(paths, __version__)
        zip_sha = _sha256_file(zip_path)
        manifest_path = paths.dist_dir / "release_manifest.json"
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "created_at": _iso_now(),
            "version": __version__,
            "engine_version": __version__,
            "git": {"commit": _git_commit(), "branch": _git_branch()},
            "inputs": {"release_check_job": args.job or paths.release_check_job, "gates_passed": bool(gates_passed)},
            "artifacts": {
                "zip_path": str(zip_path.relative_to(paths.repo_root)).replace("\\", "/"),
                "zip_sha256": zip_sha,
                "manifest_sha256": None,
            },
            "included_counts": {"files": int(file_count), "bytes": int(total_bytes)},
            "rules": {"excluded_globs": excluded_globs, "included_roots": included_roots},
        }
        _json_dump(manifest_path, manifest)
        manifest_sha = _sha256_file(manifest_path)
        manifest["artifacts"]["manifest_sha256"] = manifest_sha
        _json_dump(manifest_path, manifest)

        out = {
            "ok": True,
            "exit_code": 0,
            "version": __version__,
            "zip_path": str(zip_path.relative_to(paths.repo_root)).replace("\\", "/"),
            "manifest_path": str(manifest_path.relative_to(paths.repo_root)).replace("\\", "/"),
        }
        print(
            "release build: version={0} files={1} zip={2}".format(
                __version__, file_count, str(zip_path.relative_to(paths.repo_root)).replace("\\", "/")
            )
        )
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except ValueError as e:
        print(f"ERROR: {e}")
        return 2
    except Exception as e:
        print(f"ERROR: {e}")
        print(json.dumps({"ok": False, "exit_code": 1, "error": str(e)}, ensure_ascii=False))
        return 1


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        if args.cmd == "status":
            return _cmd_status()
        if args.cmd == "bump":
            return _cmd_bump(args)
        if args.cmd == "build":
            return _cmd_build(args)
        print("ERROR: missing subcommand (status|bump|build)")
        return 2
    except SystemExit as e:
        try:
            return int(getattr(e, "code", 2))
        except Exception:
            return 2
    except Exception as e:
        print(f"ERROR: {e}")
        print(json.dumps({"ok": False, "exit_code": 1, "error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

