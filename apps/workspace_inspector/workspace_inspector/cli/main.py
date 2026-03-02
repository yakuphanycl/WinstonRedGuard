import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from workspace_inspector import __version__

AUDIO_EXT = {".mp3", ".wav", ".flac"}
VIDEO_EXT = {".mp4", ".mov", ".avi"}
IMAGE_EXT = {".png", ".jpg", ".jpeg"}


def classify(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in AUDIO_EXT:
        return "audio"
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    return "other"


def format_size_binary(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    unit_idx = 0

    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024
        unit_idx += 1

    return f"{size:.2f} {units[unit_idx]}"


def scan(folder: Path, ignore_names: set[str]):
    counts = {"audio": 0, "video": 0, "image": 0, "other": 0}
    total_size = 0

    for root, dirs, files in os.walk(folder):
        # Skip ignored directories (in-place so os.walk won't enter them)
        dirs[:] = [d for d in dirs if d not in ignore_names]

        for fname in files:
            p = Path(root) / fname
            kind = classify(p)
            counts[kind] += 1
            try:
                total_size += p.stat().st_size
            except OSError:
                # If a file is unreadable, just skip its size
                pass

    return counts, total_size


def main() -> int:
    usage = "Usage: workspace-inspector <folder> [--ignore name1,name2,...] [--json report.json|-] [--quiet] [--version]"

    if "--version" in sys.argv:
        print(f"workspace-inspector {__version__}")
        return 0

    # Help
    if len(sys.argv) >= 2 and sys.argv[1] in {"-h", "--help"}:
        print(usage)
        print("Scans the folder and prints a summary (read-only).")
        print("Default ignores: .git,node_modules,.venv,venv,__pycache__")
        return 0

    # Basic usage
    if len(sys.argv) < 2:
        print(usage, file=sys.stderr)
        return 1

    # Folder must be the first argument (keep V0 simple)
    if sys.argv[1].startswith("-"):
        print("Error: folder must be provided first.", file=sys.stderr)
        print(usage, file=sys.stderr)
        return 1

    # Default ignore set (common noisy folders)
    ignore_names: set[str] = {".git", "node_modules", ".venv", "venv", "__pycache__"}

    # Optional: extra ignores from CLI
    if "--ignore" in sys.argv:
        i = sys.argv.index("--ignore")
        if i + 1 >= len(sys.argv):
            print("Error: --ignore requires a value like: .git,node_modules,venv", file=sys.stderr)
            return 1
        extra = sys.argv[i + 1]
        for part in extra.split(","):
            name = part.strip()
            if name:
                ignore_names.add(name)

    # Optional: JSON output
    json_out: str | None = None
    if "--json" in sys.argv:
        j = sys.argv.index("--json")
        # `--json` without a value defaults to stdout ("-").
        if j + 1 >= len(sys.argv):
            json_out = "-"
        else:
            candidate = sys.argv[j + 1].strip()
            if candidate == "-" or not candidate.startswith("-"):
                json_out = candidate
            else:
                # Next token is another flag, so treat as bare `--json`.
                json_out = "-"
        if not json_out:
            print("Error: --json output path cannot be empty", file=sys.stderr)
            return 1
    json_to_stdout = json_out == "-"

    quiet = "--quiet" in sys.argv

    folder = Path(sys.argv[1])
    if not folder.exists() or not folder.is_dir():
        print("Error: folder does not exist or is not a directory", file=sys.stderr)
        return 1

    counts, total_size = scan(folder, ignore_names)

    report = {
        "schema_version": "1",
        "tool": "workspace-inspector",
        "tool_version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "folder": str(folder.resolve()),
        "counts": counts,
        "total_files": sum(counts.values()),
        "total_size_bytes": total_size,
        "ignore_names": sorted(ignore_names),
    }

    if json_out is not None:
        json_text = json.dumps(report, ensure_ascii=False, indent=2)
        if json_to_stdout:
            # Ensure JSON can be piped as UTF-8 bytes.
            if hasattr(sys.stdout, "buffer"):
                sys.stdout.buffer.write(json_text.encode("utf-8"))
                sys.stdout.buffer.write(b"\n")
            else:
                print(json_text)
        else:
            out_path = Path(json_out)
            try:
                out_path.write_text(
                    json_text,
                    encoding="utf-8",
                )
                if not quiet:
                    print(f"JSON report written: {out_path}")
            except OSError as e:
                print(f"Error: cannot write JSON report: {e}", file=sys.stderr)
                return 1

    if not quiet and not json_to_stdout:
        print(f"Total files: {report['total_files']}")
        print(f"Audio: {counts['audio']}")
        print(f"Video: {counts['video']}")
        print(f"Images: {counts['image']}")
        print(f"Other: {counts['other']}")
        print(f"Total size: {format_size_binary(total_size)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

