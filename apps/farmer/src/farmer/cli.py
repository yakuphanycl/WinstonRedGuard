from __future__ import annotations

import argparse
import json

from .core import (
    bootstrap_data_files,
    care_run,
    care_show,
    doctor_report,
    decisions_list,
    events,
    grow_run,
    grow_show,
    grow_start,
    harvest_check,
    harvest_list,
    harvest_run,
    report_summary,
    seed_add,
    seed_list,
    seed_queue,
    seed_score,
    seed_show,
    select,
    warehouse_list,
    warehouse_move,
    warehouse_show,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="farmer", description="Farmer v2 lifecycle orchestration CLI")
    subparsers = parser.add_subparsers(dest="command")

    seed_parser = subparsers.add_parser("seed", help="seed operations")
    seed_sub = seed_parser.add_subparsers(dest="seed_command")

    seed_add_parser = seed_sub.add_parser("add", help="add a new seed")
    seed_add_parser.add_argument("--name", required=True)
    seed_add_parser.add_argument("--title")
    seed_add_parser.add_argument("--category", required=True, choices=["cli", "web", "content", "infra", "automation"])
    seed_add_parser.add_argument("--problem", required=True)
    seed_add_parser.add_argument("--target-user", required=True)
    seed_add_parser.add_argument("--internal-value", required=True, type=int)
    seed_add_parser.add_argument("--external-value", required=True, type=int)
    seed_add_parser.add_argument("--complexity", required=True, type=int)

    seed_sub.add_parser("list", help="list all seeds")
    seed_show_parser = seed_sub.add_parser("show", help="show seed details")
    seed_show_parser.add_argument("name")
    seed_show_parser.add_argument("--json", action="store_true", dest="as_json")
    seed_score_parser = seed_sub.add_parser("score", help="score one seed")
    seed_score_parser.add_argument("name")
    seed_queue_parser = seed_sub.add_parser("queue", help="move seed to queue")
    seed_queue_parser.add_argument("name")

    grow_parser = subparsers.add_parser("grow", help="growth pipeline operations")
    grow_sub = grow_parser.add_subparsers(dest="grow_command")
    grow_start_parser = grow_sub.add_parser("start", help="start growth for seed")
    grow_start_parser.add_argument("name")
    grow_sub.add_parser("run", help="run deterministic growth progression")
    grow_show_parser = grow_sub.add_parser("show", help="show growth job")
    grow_show_parser.add_argument("name")

    care_parser = subparsers.add_parser("care", help="care pipeline operations")
    care_sub = care_parser.add_subparsers(dest="care_command")
    care_sub.add_parser("run", help="run care checks")
    care_show_parser = care_sub.add_parser("show", help="show care notes")
    care_show_parser.add_argument("name")

    harvest_parser = subparsers.add_parser("harvest", help="harvest operations")
    harvest_sub = harvest_parser.add_subparsers(dest="harvest_command")
    harvest_check_parser = harvest_sub.add_parser("check", help="check harvest readiness")
    harvest_check_parser.add_argument("name")
    harvest_sub.add_parser("run", help="run harvest pipeline")
    harvest_sub.add_parser("list", help="list harvest events")

    warehouse_parser = subparsers.add_parser("warehouse", help="warehouse operations")
    warehouse_sub = warehouse_parser.add_subparsers(dest="warehouse_command")
    warehouse_sub.add_parser("list", help="list warehouse items")
    warehouse_show_parser = warehouse_sub.add_parser("show", help="show warehouse item")
    warehouse_show_parser.add_argument("name")
    warehouse_move_parser = warehouse_sub.add_parser("move", help="move warehouse item")
    warehouse_move_parser.add_argument("name")
    warehouse_move_parser.add_argument("--to", required=True)

    select_parser = subparsers.add_parser("select", help="create deterministic portfolio decision")
    select_parser.add_argument("name")

    show_parser = subparsers.add_parser("show", help="compact seed intelligence view")
    show_parser.add_argument("name")
    show_parser.add_argument("--json", action="store_true", dest="as_json")

    events_parser = subparsers.add_parser("events", help="inspect activity events")
    events_parser.add_argument("--seed")
    events_parser.add_argument("--json", action="store_true", dest="as_json")

    decisions_parser = subparsers.add_parser("decisions", help="decision records")
    decisions_sub = decisions_parser.add_subparsers(dest="decisions_command")
    decisions_sub.add_parser("list", help="list decisions")

    report_parser = subparsers.add_parser("report", help="reporting")
    report_sub = report_parser.add_subparsers(dest="report_command")
    report_sub.add_parser("summary", help="show pipeline summary")

    doctor_parser = subparsers.add_parser("doctor", help="read-only data integrity audit")
    doctor_parser.add_argument("--json", action="store_true", dest="as_json")

    return parser


def _print_seed_list(rows: list[dict]) -> None:
    if not rows:
        print("no seeds")
        return
    for row in rows:
        print(f"- {row.get('name')}: status={row.get('status')} category={row.get('category')} score={row.get('score')}")


def _print_rows(rows: list[dict], field: str) -> None:
    if not rows:
        print("no records")
        return
    for row in sorted(rows, key=lambda r: str(r.get(field, ""))):
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def _print_events_human(payload: dict) -> None:
    events_rows = list(payload.get("events", []))
    print(f"events: {int(payload.get('total', 0))}")
    for row in events_rows:
        ts = str(row.get("timestamp", ""))
        event_type = str(row.get("event_type", ""))
        seed_name = str(row.get("seed_name", ""))
        details = json.dumps(row.get("payload", {}), ensure_ascii=False, sort_keys=True)
        print(f"- {ts} {event_type} {seed_name} {details}")


def _print_seed_intelligence_human(payload: dict) -> None:
    seed = dict(payload.get("seed", {}))
    print(f"seed: {seed.get('name', '')}")
    print(f"status: {seed.get('status', '')}")
    if seed.get("score") is not None:
        print(f"score: {seed.get('score')}")
    selection = payload.get("selection")
    if selection is None:
        print("selection: none")
    else:
        reasons = ",".join(str(code) for code in list(selection.get("reason_codes", [])))
        print(
            f"selection: selected={bool(selection.get('selected'))} "
            f"reasons={reasons if reasons else '-'}"
        )
    print("recent events:")
    events_rows = list(payload.get("recent_events", []))
    if not events_rows:
        print("- none")
        return
    for row in events_rows:
        ts = str(row.get("timestamp", ""))
        event_type = str(row.get("event_type", ""))
        details = json.dumps(row.get("payload", {}), ensure_ascii=False, sort_keys=True)
        print(f"- {ts} {event_type} {details}")


def _print_doctor_human(payload: dict) -> None:
    summary = dict(payload.get("summary", {}))
    print(f"doctor: {summary.get('overall', 'OK')}")
    print(
        "summary: "
        f"total={int(summary.get('total', 0))} "
        f"errors={int(summary.get('errors', 0))} "
        f"warnings={int(summary.get('warnings', 0))}"
    )
    for row in list(payload.get("findings", [])):
        seed = row.get("seed_name")
        seed_text = f" seed={seed}" if seed is not None else ""
        print(f"{row.get('severity', '')} {row.get('code', '')}{seed_text} {row.get('message', '')}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    bootstrap_data_files()

    try:
        if args.command == "seed" and args.seed_command == "add":
            row = seed_add(
                name=args.name,
                title=args.title,
                category=args.category,
                problem=args.problem,
                target_user=args.target_user,
                internal_value=int(args.internal_value),
                external_value=int(args.external_value),
                complexity=int(args.complexity),
            )
            print(f"seed added: {row['name']}")
            return 0

        if args.command == "seed" and args.seed_command == "list":
            _print_seed_list(seed_list())
            return 0

        if args.command == "seed" and args.seed_command == "show":
            payload = seed_show(args.name)
            if args.as_json:
                _print_json(payload)
            else:
                _print_seed_intelligence_human(payload)
            return 0

        if args.command == "seed" and args.seed_command == "score":
            _print_json(seed_score(args.name))
            return 0

        if args.command == "seed" and args.seed_command == "queue":
            row = seed_queue(args.name)
            print(f"seed queued: {row['name']} status={row['status']}")
            return 0

        if args.command == "grow" and args.grow_command == "start":
            row = grow_start(args.name)
            print(f"growth started: {row['seed_name']} stage={row['current_growth_stage']}")
            return 0

        if args.command == "grow" and args.grow_command == "run":
            rows = grow_run()
            _print_json({"processed": len(rows)})
            return 0

        if args.command == "grow" and args.grow_command == "show":
            _print_json(grow_show(args.name))
            return 0

        if args.command == "care" and args.care_command == "run":
            rows = care_run()
            _print_json({"processed": len(rows)})
            return 0

        if args.command == "care" and args.care_command == "show":
            _print_json(care_show(args.name))
            return 0

        if args.command == "harvest" and args.harvest_command == "check":
            _print_json(harvest_check(args.name))
            return 0

        if args.command == "harvest" and args.harvest_command == "run":
            rows = harvest_run()
            _print_json({"processed": len(rows)})
            return 0

        if args.command == "harvest" and args.harvest_command == "list":
            _print_rows(harvest_list(), "seed_name")
            return 0

        if args.command == "warehouse" and args.warehouse_command == "list":
            _print_rows(warehouse_list(), "name")
            return 0

        if args.command == "warehouse" and args.warehouse_command == "show":
            _print_json(warehouse_show(args.name))
            return 0

        if args.command == "warehouse" and args.warehouse_command == "move":
            row = warehouse_move(args.name, args.to)
            print(f"warehouse moved: {row['name']} bucket={row['bucket']}")
            return 0

        if args.command == "select":
            _print_json(select(args.name))
            return 0

        if args.command == "show":
            payload = seed_show(args.name)
            if args.as_json:
                _print_json(payload)
            else:
                _print_seed_intelligence_human(payload)
            return 0

        if args.command == "events":
            payload = events(seed_name=args.seed)
            if args.as_json:
                _print_json(payload)
            else:
                _print_events_human(payload)
            return 0

        if args.command == "decisions" and args.decisions_command == "list":
            _print_rows(decisions_list(), "name")
            return 0

        if args.command == "report" and args.report_command == "summary":
            _print_json(report_summary())
            return 0

        if args.command == "doctor":
            payload = doctor_report()
            if args.as_json:
                _print_json(payload)
            else:
                _print_doctor_human(payload)
            if payload["summary"]["errors"] > 0:
                return 1
            return 0

        parser.print_help()
        return 1
    except ValueError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
