import json
import subprocess
import sys
from pathlib import Path


POLICY_PATH = (Path(__file__).resolve().parents[1] / 'policy.json')
def run_yyfe(*args: str) -> tuple[int, str]:
    cp = subprocess.run([sys.executable, "-m", "yyfe", *args], capture_output=True, text=True)
    out = (cp.stdout or "") + (cp.stderr or "")
    return cp.returncode, out

def test_validate_blocks_non_allowlisted_script():
    # generate fresh plan
    rc, out = run_yyfe('plan', '--profile', 'lab', '--policy', str(POLICY_PATH))
    assert rc == 0, out

    plan = json.loads(Path("output/plan.json").read_text(encoding="utf-8"))
    assert isinstance(plan.get("actions"), list) and plan["actions"]

    # force a blocked cmd
    plan["actions"][0]["cmd"] = [
        "powershell","-NoProfile","-ExecutionPolicy","Bypass","-File",
        r"C:\Windows\Temp\nope.ps1"
    ]

    bad = Path("output/plan_bad_test.json")
    bad.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rc, out = run_yyfe('validate', '--plan', str(bad), '--policy', str(POLICY_PATH))
    assert rc == 2, out
    assert ("blocked script" in out) or ("not allowlisted" in out), out



