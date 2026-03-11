import os
import sys
from importlib import import_module
from pathlib import Path

from generator.generate_tool import generate_tool, run_structure_smoke_check


def register_generated_app(
    *,
    name: str,
    description: str | None,
    template: str,
    app_path: Path,
    status: str,
    score: int | None,
) -> None:
    app_registry_src_override = None
    if "APP_REGISTRY_SRC" in os.environ:
        app_registry_src_override = Path(os.environ["APP_REGISTRY_SRC"])
    if app_registry_src_override is not None:
        app_registry_src = app_registry_src_override
    else:
        repo_root = Path(__file__).resolve().parents[4]
        app_registry_src = repo_root / "apps" / "app_registry" / "src"
    if str(app_registry_src) not in sys.path:
        sys.path.insert(0, str(app_registry_src))

    core = import_module("app_registry.core")
    role = description or f"{name} generated app"
    core.add_record(
        name=name,
        version="0.1.0",
        role=role,
        entrypoint=f"{name}.cli:main",
        status=status,
        score=score,
        verified=True,
        source_template=template,
        created_by="devtool_factory",
        app_path=str(app_path.resolve()),
    )


def evaluate_generated_app(app_path: Path) -> dict:
    app_evaluator_src_override = None
    if "APP_EVALUATOR_SRC" in os.environ:
        app_evaluator_src_override = Path(os.environ["APP_EVALUATOR_SRC"])
    if app_evaluator_src_override is not None:
        app_evaluator_src = app_evaluator_src_override
    else:
        repo_root = Path(__file__).resolve().parents[4]
        app_evaluator_src = repo_root / "apps" / "app_evaluator" / "src"
    if str(app_evaluator_src) not in sys.path:
        sys.path.insert(0, str(app_evaluator_src))

    core = import_module("app_evaluator.core")
    return core.run_evaluation(app_path=str(app_path))


def main():
    if len(sys.argv) < 3:
        print("usage: factory generate <tool_name>")
        return

    command = sys.argv[1]

    if command != "generate":
        print("unknown command:", command)
        return

    name = sys.argv[2]
    description = None
    template = "cli_tool"
    output_root = None
    smoke_check = False
    evaluate = False
    min_score = 0
    allow_quarantine = False
    register = False
    extra = sys.argv[3:]
    i = 0
    while i < len(extra):
        flag = extra[i]
        if flag == "--smoke-check":
            smoke_check = True
            i += 1
            continue
        if flag == "--register":
            register = True
            i += 1
            continue
        if flag == "--evaluate":
            evaluate = True
            i += 1
            continue
        if flag == "--allow-quarantine":
            allow_quarantine = True
            i += 1
            continue
        if i + 1 >= len(extra):
            print(
                "usage: factory generate <tool_name> "
                "[--description <text>] [--template <name>] [--output-root <path>] "
                "[--smoke-check] [--evaluate] [--min-score <int>] [--allow-quarantine] [--register]"
            )
            raise SystemExit(1)
        value = extra[i + 1]
        if flag == "--description":
            description = value
        elif flag == "--template":
            template = value
        elif flag == "--output-root":
            output_root = value
        elif flag == "--min-score":
            try:
                min_score = int(value)
            except ValueError as exc:
                raise RuntimeError(f"invalid min-score: {value!r}") from exc
        else:
            print(
                "usage: factory generate <tool_name> "
                "[--description <text>] [--template <name>] [--output-root <path>] "
                "[--smoke-check] [--evaluate] [--min-score <int>] [--allow-quarantine] [--register]"
            )
            raise SystemExit(1)
        i += 2

    try:
        target = generate_tool(
            name,
            description=description,
            template=template,
            output_root=output_root,
        )
        if smoke_check or evaluate or register:
            run_structure_smoke_check(target, name)
            print(f"smoke check passed: {name}")
        eval_score: int | None = None
        record_status = "candidate"
        if evaluate:
            eval_report = evaluate_generated_app(target)
            score = int(eval_report.get("score", 0))
            eval_score = score
            if score < min_score:
                print(f"evaluation failed threshold: score={score} min_score={min_score}")
                if register and allow_quarantine:
                    record_status = "quarantine"
                else:
                    if register:
                        print("registry add skipped: quarantine not allowed")
                    raise SystemExit(1)
            if not bool(eval_report.get("ok", False)):
                print(f"evaluation failed: {name} score={score}")
                raise SystemExit(1)
            if score >= min_score:
                print(f"evaluation passed: {name} score={score}")
                record_status = "active"
        if register:
            try:
                register_generated_app(
                    name=name,
                    description=description,
                    template=template,
                    app_path=target,
                    status=record_status,
                    score=eval_score,
                )
                print(f"registry add passed: {name} status={record_status}")
            except ValueError as exc:
                if "app already exists" in str(exc).lower():
                    print(f"registry skip: app already exists: {name}")
                else:
                    raise
    except RuntimeError as exc:
        print("error:", exc)
        raise SystemExit(1)
    except ModuleNotFoundError as exc:
        print("error:", exc)
        raise SystemExit(1)
    except ValueError as exc:
        print("error:", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
