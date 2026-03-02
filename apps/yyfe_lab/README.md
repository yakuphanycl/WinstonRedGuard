# yyfe-lab

A tiny Python lab project with tests and a QA gate.

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -U build setuptools wheel
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\golden.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\qa.ps1