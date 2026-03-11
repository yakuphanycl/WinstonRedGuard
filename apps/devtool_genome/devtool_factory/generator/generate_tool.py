import keyword
import shutil
from pathlib import Path

TEMPLATES_ROOT = Path(__file__).parent.parent / "templates"
TEMPLATE_REGISTRY = {
    "cli_tool": TEMPLATES_ROOT / "cli_tool",
    "single_file_cli": TEMPLATES_ROOT / "single_file_cli",
    "wrg_app": TEMPLATES_ROOT / "wrg_app",
}
TEXT_TEMPLATE_SUFFIXES = {
    ".py",
    ".toml",
    ".json",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
}
TEXT_TEMPLATE_FILENAMES = {".gitignore"}


def _is_text_template(path: Path) -> bool:
    if path.name in TEXT_TEMPLATE_FILENAMES:
        return True
    return path.suffix.lower() in TEXT_TEMPLATE_SUFFIXES


def run_structure_smoke_check(target: Path, name: str) -> None:
    checks = [
        (target.is_dir(), f"missing target directory: {target}"),
        (
            (target / "src" / name / "__init__.py").is_file(),
            f"missing file: {target / 'src' / name / '__init__.py'}",
        ),
        (
            (target / "src" / name / "cli.py").is_file(),
            f"missing file: {target / 'src' / name / 'cli.py'}",
        ),
    ]
    errors = [message for ok, message in checks if not ok]
    if errors:
        raise RuntimeError("smoke check failed: " + "; ".join(errors))


def generate_tool(
    name: str,
    description: str | None = None,
    template: str = "cli_tool",
    output_root: str | None = None,
) -> Path:
    if not name.isidentifier() or keyword.iskeyword(name):
        raise RuntimeError(
            f"invalid tool name: {name!r}. Use a valid Python package/module name."
        )
    if template not in TEMPLATE_REGISTRY:
        raise RuntimeError(f"unknown template: {template}")

    if output_root is None:
        target = Path.cwd() / name
    else:
        target = Path(output_root) / name
    rendered_description = description or f"{name} CLI tool"
    template_dir = TEMPLATE_REGISTRY[template]

    if target.exists():
        raise RuntimeError(f"target already exists: {target}")

    # template kopyala
    shutil.copytree(
        template_dir,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )

    # placeholder rename in paths (deepest first)
    token_pairs = [("{{tool_name}}", name), ("__tool_name__", name)]
    paths = sorted(target.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    for path in paths:
        new_name = path.name
        for token, value in token_pairs:
            new_name = new_name.replace(token, value)
        if new_name != path.name:
            path.rename(path.with_name(new_name))

    # placeholder replace
    for path in target.rglob("*"):
        if not path.is_file() or not _is_text_template(path):
            continue
        text = path.read_text(encoding="utf-8-sig")
        text = text.replace("{{tool_name}}", name)
        text = text.replace("{{description}}", rendered_description)
        path.write_text(text, encoding="utf-8")

    print("tool created:", target)
    return target
