# TASK-001 — Fill missing edge-case tests for math_utils

## Goal
Expand tests for src/math_utils.py to cover edge cases and define expected behavior.

## Scope
- Only modify: tests/test_math_utils.py
- Use deterministic tests (no randomness, no time).

## Out of Scope
- Do not change src/math_utils.py in Task-001.
- No new dependencies besides pytest.

## Definition of Done (DoD)
- python -m pytest -q PASS
- Added tests for:
  - divide by zero
  - percentage total == 0
  - moving_average window <= 0
  - moving_average window > len(values)

## Notes
We accept that some tests may initially fail until spec is clarified, but for Task-001 we will **define** behavior via tests and keep code unchanged.
