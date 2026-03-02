# YYFE Policy (V0)

Policy file controls which scripts are allowed to run in plans.

## File: policy.json

Minimum schema:

`json
{
  "allow_scripts": [
    "C:/Users/lenovo/yyfe-lab/tasks/run_tests.ps1"
  ]
}
'@

Rules

allow_scripts must be a JSON array of strings.

Each string is a script path.

Canonicalization:

path is normalized for Windows (case + separators)

\ and / are treated equivalently

A plan action is allowed only if its command matches:

powershell -NoProfile -ExecutionPolicy Bypass -File <script>

…and <script> is in allow_scripts.

Why

This prevents a plan file from running arbitrary commands/scripts.