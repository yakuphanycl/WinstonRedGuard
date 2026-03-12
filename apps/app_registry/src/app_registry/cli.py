from __future__ import annotations

import argparse
import json

from .core import (
    add_record,
    classify_record,
    format_audit_report,
    format_reevaluate_all_report,
    list_records,
    reevaluate_record,
    reevaluate_all_records,
    run_audit,
    show_record,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app_registry")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="list all app records")
    list_parser.add_argument("--status")

    show_parser = subparsers.add_parser("show", help="show one app by name")
    show_parser.add_argument("name")

    add_parser = subparsers.add_parser("add", help="add one app record")
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--version", required=True)
    add_parser.add_argument("--role", required=True)
    add_parser.add_argument("--entrypoint", required=True)
    add_parser.add_argument("--status")
    add_parser.add_argument("--score", type=int)
    add_parser.add_argument("--verified", action="store_true")
    add_parser.add_argument("--source-template", dest="source_template")
    add_parser.add_argument("--created-by", dest="created_by")
    add_parser.add_argument("--app-path", dest="app_path")
    add_parser.add_argument("--class", dest="class_name")
    add_parser.add_argument("--primary-role", dest="primary_role")
    add_parser.add_argument("--internal-customer", dest="internal_customer", nargs="+")
    add_parser.add_argument("--external-product-potential", dest="external_product_potential")
    add_parser.add_argument("--productization-stage", dest="productization_stage")
    add_parser.add_argument("--class-assigned-at", dest="class_assigned_at")
    add_parser.add_argument("--class-assigned-by", dest="class_assigned_by")
    add_parser.add_argument("--reclassification-reason", dest="reclassification_reason")

    classify_parser = subparsers.add_parser("classify", help="set app classification metadata")
    classify_parser.add_argument("name")
    classify_parser.add_argument("--class", dest="class_name", required=True)
    classify_parser.add_argument("--primary-role", dest="primary_role", required=True)
    classify_parser.add_argument("--internal-customer", dest="internal_customer", required=True, nargs="+")
    classify_parser.add_argument(
        "--external-product-potential",
        dest="external_product_potential",
        required=True,
    )
    classify_parser.add_argument("--productization-stage", dest="productization_stage", required=True)
    classify_parser.add_argument("--assigned-by", dest="assigned_by", default="human")
    classify_parser.add_argument("--reason", dest="reason")

    reevaluate_parser = subparsers.add_parser("reevaluate", help="reevaluate one app by name")
    reevaluate_parser.add_argument("name")
    reevaluate_parser.add_argument("--min-score", type=int, default=0)
    reevaluate_parser.add_argument("--activate-on-pass", action="store_true")

    reevaluate_all_parser = subparsers.add_parser("reevaluate-all", help="reevaluate all apps")
    reevaluate_all_parser.add_argument("--min-score", type=int, required=True)
    reevaluate_all_parser.add_argument("--activate-on-pass", action="store_true")
    reevaluate_all_parser.add_argument("--status")

    subparsers.add_parser("audit", help="audit registry entries")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        records = list_records(status=args.status)
        print(json.dumps(records, indent=2, ensure_ascii=False))
        return 0

    if args.command == "show":
        try:
            print(json.dumps(show_record(args.name), indent=2, ensure_ascii=False))
            return 0
        except ValueError as exc:
            print("error:", exc)
            return 1

    if args.command == "add":
        try:
            app = add_record(
                name=args.name,
                version=args.version,
                role=args.role,
                entrypoint=args.entrypoint,
                status=args.status or "active",
                score=args.score,
                verified=bool(args.verified),
                source_template=args.source_template,
                created_by=args.created_by,
                app_path=args.app_path,
                class_name=args.class_name,
                primary_role=args.primary_role,
                internal_customer=args.internal_customer[0]
                if isinstance(args.internal_customer, list) and len(args.internal_customer) == 1
                else args.internal_customer,
                external_product_potential=args.external_product_potential,
                productization_stage=args.productization_stage,
                class_assigned_at=args.class_assigned_at,
                class_assigned_by=args.class_assigned_by,
                reclassification_reason=args.reclassification_reason,
            )
            print(json.dumps(app, indent=2, ensure_ascii=False))
            return 0
        except ValueError as exc:
            print("error:", exc)
            return 1

    if args.command == "classify":
        try:
            internal_customer = (
                args.internal_customer[0]
                if isinstance(args.internal_customer, list) and len(args.internal_customer) == 1
                else args.internal_customer
            )
            app = classify_record(
                name=args.name,
                class_name=args.class_name,
                primary_role=args.primary_role,
                internal_customer=internal_customer,
                external_product_potential=args.external_product_potential,
                productization_stage=args.productization_stage,
                assigned_by=args.assigned_by,
                reason=args.reason,
            )
            print(json.dumps(app, indent=2, ensure_ascii=False))
            return 0
        except ValueError as exc:
            print("error:", exc)
            return 1

    if args.command == "reevaluate":
        try:
            result = reevaluate_record(
                name=args.name,
                min_score=int(args.min_score),
                activate_on_pass=bool(args.activate_on_pass),
            )
            if result["passed"]:
                print(
                    f"reevaluation passed: {result['name']} "
                    f"score={result['score']} min_score={result['min_score']}"
                )
                print(
                    f"registry update passed: {result['name']} status={result['status']}"
                )
                return 0

            print(
                f"reevaluation failed threshold: {result['name']} "
                f"score={result['score']} min_score={result['min_score']}"
            )
            print(f"registry update passed: {result['name']} status={result['status']}")
            return 0
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("app not found:"):
                app_name = msg.split(":", 1)[1].strip()
                print(f"error: app not found in registry: {app_name}")
                return 1
            if msg.startswith("app_path missing for registry entry:"):
                app_name = msg.split(":", 1)[1].strip()
                print(f"error: app_path missing for registry entry: {app_name}")
                return 1
            print("error:", exc)
            return 1
        except Exception as exc:
            print("error:", exc)
            return 1

    if args.command == "audit":
        report = run_audit()
        print(format_audit_report(report))
        return 1 if int(report["summary"]["error"]) > 0 else 0

    if args.command == "reevaluate-all":
        report = reevaluate_all_records(
            min_score=int(args.min_score),
            activate_on_pass=bool(args.activate_on_pass),
            status=args.status,
        )
        print(format_reevaluate_all_report(report))
        return 1 if int(report["summary"]["error"]) > 0 else 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
