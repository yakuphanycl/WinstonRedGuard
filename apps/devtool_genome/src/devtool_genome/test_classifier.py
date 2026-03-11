from __future__ import annotations

from devtool_genome.classifier import looks_like_devtool, score_package

CASES = [
    ("pytest", "", "", True),
    ("ruff", "", "", True),
    ("black", "", "", True),
    ("mypy", "", "", True),
    ("tox", "", "", True),
    ("nox", "", "", True),
    ("pre-commit", "", "", True),
    ("requests", "", "", False),
    ("numpy", "", "", False),
    ("pandas", "", "", False),
    ("fastapi", "", "", False),
    ("sqlalchemy", "", "", False),
    ("httpx", "", "", False),
    ("pydantic", "", "", False),
    ("00101s", "", "", False),
    ("02122Group14", "", "", False),
    ("090807040506030201testpip", "", "", False),
]

passed = 0

for name, summary, keywords, expected in CASES:
    score = score_package(name=name, summary=summary, keywords=keywords)
    got = looks_like_devtool(name=name, summary=summary, keywords=keywords)
    ok = got == expected
    if ok:
        passed += 1
    print(
        f"{name:28} score={score:3} got={str(got):5} expected={str(expected):5} ok={ok}"
    )

print(f"\nscore: {passed}/{len(CASES)}")