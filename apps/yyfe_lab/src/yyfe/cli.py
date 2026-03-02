from __future__ import annotations

import argparse
import os
from pathlib import Path

# GATE_REFACTOR_V03
def _canon_script_path(x: str) -> str:
    x = os.path.normcase(os.path.normpath(x))
    return x.replace("\\", "/")

def _cmd_prefix() -> list[str]:
    return ["powershell","-NoProfile","-ExecutionPolicy","Bypass"]

def _shape_ok(c: list[str]) -> bool:
    pref = _cmd_prefix()
    return (
        isinstance(c, list)
        and len(c) == len(pref) + 2
        and c[:len(pref)] == pref
        and c[len(pref)] == "-File"
        and isinstance(c[len(pref) + 1], str)
        and len(c[len(pref) + 1]) > 0
    )

def _load_allowlisted_scripts_canon(policy_path: str) -> set[str]:
    allow = _load_allowlisted_scripts(policy_path)
    return {_canon_script_path(x) for x in allow}

def _check_plan_actions_against_policy(plan: dict, policy_path: str) -> int:
    allow = _load_allowlisted_scripts_canon(policy_path)
    actions = plan.get("actions")
    if not isinstance(actions, list):
        print("VALIDATE_ERR: plan.actions must be a list")
        return 2
    for a in actions:
        if not isinstance(a, dict):
            print(f"VALIDATE_ERR: invalid action entry: {a!r}")
            return 2
        if a.get("type") != "run":
            print(f"VALIDATE_ERR: unsupported action type: {a.get('type')!r}")
            return 2
        cmd = a.get("cmd")
        if not isinstance(cmd, list):
            print(f"VALIDATE_ERR: cmd must be a list: {cmd!r}")
            return 2
        c = _canon_cmd(cmd)
        if not _shape_ok(c):
            print(f"VALIDATE_ERR: blocked cmd (prefix/shape): {cmd!r}")
            return 2
        script = _canon_script_path(c[len(_cmd_prefix()) + 1])
        if script not in allow:
            print(f"VALIDATE_ERR: blocked script (not allowlisted): {cmd!r}")
            return 2
    return 0

from yyfe.core.plan import load_plan, validate_plan_obj
from yyfe.core.policy import Policy
from yyfe.core.profiles import get_builder
from yyfe.core.runner import run


def _canon_script_path(p: str) -> str:
    # canonicalize for allowlist matching (handles slashes, .\, case on Windows)
    return os.path.normcase(str(Path(p).resolve()))

def _canon_cmd(cmd_list: list[str]) -> list[str]:
    out = list(cmd_list)
    try:
        i = out.index("-File")
    except ValueError:
        return out
    if i + 1 < len(out):
        out[i + 1] = _canon_script_path(out[i + 1])
    return out

def _load_allowlisted_scripts(policy_path: str) -> set[str]:
    # Best-effort: prefer Policy.load(), fallback to reading JSON directly.
    # Returns canonical (resolved + normcase) paths.
    allow: list[str] | None = None

    try:
        pol = Policy.load(policy_path)
        # Try common shapes
        if hasattr(pol, "data") and isinstance(getattr(pol, "data"), dict):
            allow = pol.data.get("allowlisted_scripts")
        elif hasattr(pol, "to_dict") and callable(getattr(pol, "to_dict")):
            d = pol.to_dict()
            if isinstance(d, dict):
                allow = d.get("allowlisted_scripts")
        elif isinstance(pol, dict):
            allow = pol.get("allowlisted_scripts")
        else:
            # last resort: attribute access
            allow = getattr(pol, "allowlisted_scripts", None)
    except Exception:
        allow = None

    if allow is None:
        try:
            d = json.loads(Path(policy_path).read_text(encoding="utf-8"))
            if isinstance(d, dict):
                allow = d.get("allowlisted_scripts")
        except Exception:
            allow = None

    if not isinstance(allow, list):
        # safe default
        allow = ["tools/golden.ps1"]

    out: set[str] = set()
    for p in allow:
        if isinstance(p, str) and p.strip():
            out.add(_canon_script_path(p))
    return out

def main() -> int:
    ap = argparse.ArgumentParser(prog="yyfe", description="YY-FE v0.1 lab engine")
    ap.add_argument("--policy", default="policy.json", help="Path to policy.json")
    ap.add_argument("--profile", default="lab", help="Plan profile (builtin: lab)")
    ap.add_argument("--out", default="output/plan.json", help="(plan) Path to write plan.json")
    ap.add_argument(
        "--plan",
        default="output/plan.json",
        help="(apply/validate) Path to read plan.json",
    )
    ap.add_argument("cmd", choices=["golden", "plan", "validate", "apply"], help="Command to run")
    args = ap.parse_args()

    _ = Policy.load(args.policy)

    if args.cmd == "golden":
        r = run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(Path("tools") / "golden.ps1"),
            ]
        )
        print(r.stdout, end="")
        if not r.ok:
            print(r.stderr, end="")
        return r.exit_code

    if args.cmd == "plan":
        import json

        out_path = Path(getattr(args, "out", "output/plan.json"))
        out_path.parent.mkdir(parents=True, exist_ok=True)

        builder = get_builder(getattr(args, "profile", "lab"))
        plan = builder(args)

        ok, msg = validate_plan_obj(plan)
        if not ok:
            print(f"PLAN_ERR: {msg}")
            return 2

        out_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(f"PLAN_OK: wrote {out_path}")
        return 0

    if args.cmd == "validate":

        plan_path = Path(getattr(args, "plan", "output/plan.json"))

        if not plan_path.exists():

            print(f"VALIDATE_ERR: missing plan file: {plan_path}")

            return 2


        plan = load_plan(plan_path)

        ok, msg = validate_plan_obj(plan)

        if not ok:

            print(f"VALIDATE_ERR: {msg}")

            return 2


        rc = _check_plan_actions_against_policy(plan, getattr(args, "policy", "policy.json"))

        if rc:

            return rc


        policy_path = getattr(args, "policy", "policy.json")

        try:

            _n_allow = len(_load_allowlisted_scripts_canon(policy_path))

        except Exception:

            _n_allow = -1

        print(f"VALIDATE_OK (policy={policy_path}, allow_scripts={_n_allow})")

        return 0


    if args.cmd == "apply":
        cmd_prefix = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
        ]
        allow_scripts = _load_allowlisted_scripts_canon(getattr(args, "policy", "policy.json"))
        # PATHNORM_V03
        def _canon_script_path(x: str) -> str:
            x = os.path.normcase(os.path.normpath(x))
            return x.replace('\\', '/')
        allow_scripts = {_canon_script_path(x) for x in allow_scripts}

        plan_path = Path(getattr(args, "plan", "output/plan.json"))
        if not plan_path.exists():
            print(f"APPLY_ERR: missing plan file: {plan_path}. Run `yyfe plan` or pass --plan PATH.")
            return 2

        plan = load_plan(plan_path)

        ok, msg = validate_plan_obj(plan)
        if not ok:
            print(f"APPLY_ERR: {msg}")
            return 2

        actions = plan.get("actions")
        assert isinstance(actions, list)

        allowed_cmd = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(Path("tools") / "golden.ps1"),
        ]

        for a in actions:
            if not isinstance(a, dict):
                print(f"APPLY_ERR: invalid action entry: {a!r}")
                return 2

            if a.get("type") != "run":
                print(f"APPLY_ERR: unsupported action type: {a.get('type')!r}")
                return 2

            cmd = a.get("cmd")
            c = _canon_cmd(cmd)

            # strict mode: must be exactly: <prefix> -File <script>
            if not (isinstance(c, list) and len(c) == len(cmd_prefix) + 2 and c[: len(cmd_prefix)] == cmd_prefix and c[len(cmd_prefix)] == "-File"):
                print(f"APPLY_ERR: blocked cmd (prefix/shape): {cmd!r}")
                return 2

            script = _canon_script_path(c[len(cmd_prefix) + 1])
            script = _canon_script_path(script)
            if script not in allow_scripts:
                print(f"APPLY_ERR: blocked script (not allowlisted): {cmd!r}")
                return 2
                print(f"APPLY_ERR: blocked cmd (not allowlisted): {cmd!r}")
                return 2

            r = run(cmd)
            print(r.stdout, end="")
            if not r.ok:
                print(r.stderr, end="")
                return r.exit_code

        print("APPLY_OK")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())







