import json
import subprocess
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
POLICY_PATH = APP_DIR / "policy.json"
OUTPUT_DIR = APP_DIR / "output"


def run_yyfe(*args: str) -> tuple[int, str]:
    cp = subprocess.run(
        [sys.executable, "-m", "yyfe", "--policy", str(POLICY_PATH), *args],
        capture_output=True,
        text=True,
        cwd=str(APP_DIR),
    )
    out = (cp.stdout or "") + (cp.stderr or "")
    return cp.returncode, out


def test_validate_blocks_non_allowlisted_script():
    assert POLICY_PATH.exists(), f"missing policy file: {POLICY_PATH}"

    # generate fresh plan
    rc, out = run_yyfe("plan", "--profile", "lab")
    assert rc == 0, out

    plan_file = OUTPUT_DIR / "plan.json"
    assert plan_file.exists(), f"missing plan file: {plan_file}"

    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    assert isinstance(plan.get("actions"), list) and plan["actions"]

    # force a blocked cmd
    plan["actions"][0]["cmd"] = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        r"C:\Windows\Temp\nope.ps1",
    ]

    bad = OUTPUT_DIR / "plan_bad_test.json"
    bad.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rc, out = run_yyfe("validate", "--plan", str(bad))
    assert rc == 2, out
    assert ("blocked script" in out) or ("not allowlisted" in out), out