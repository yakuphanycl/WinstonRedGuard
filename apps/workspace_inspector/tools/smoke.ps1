Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Help must work
python -m workspace_inspector --help | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# JSON to stdout must be clean JSON
python -m workspace_inspector . --json - |
  python -c "import sys,json; json.load(sys.stdin); print('SMOKE_JSON_OK')"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# JSON to file must be valid JSON
python -m workspace_inspector . --json report.json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -c "import json; json.load(open('report.json','r',encoding='utf-8')); print('SMOKE_FILE_OK')"
exit $LASTEXITCODE
