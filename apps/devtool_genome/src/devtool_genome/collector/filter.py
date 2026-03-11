from __future__ import annotations

import re

VALID_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,49}$")
VERSION_LIKE_RE = re.compile(r"^\d+(\.\d+){1,3}$")
UUID_LIKE_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

TOO_MANY_SYMBOL_BLOCKS_RE = re.compile(r"([._-])\1{1,}")
WEIRD_MIX_RE = re.compile(r"^[._-]|[._-]$")
TRAILING_LONG_DIGITS_RE = re.compile(r".*\d{5,}$")
TOY_NAME_RE = re.compile(r"(foo|bar|demo|testpkg|sample)", re.IGNORECASE)


def is_reasonable_name(name: str) -> bool:
    n = name.strip()

    if len(n) < 3:
        return False

    if len(n) > 50:
        return False

    if not VALID_NAME_RE.match(n):
        return False

    lower = n.lower()

    if lower.isdigit():
        return False

    if VERSION_LIKE_RE.match(lower):
        return False

    if UUID_LIKE_RE.match(lower):
        return False

    if WEIRD_MIX_RE.search(lower):
        return False

    if TOO_MANY_SYMBOL_BLOCKS_RE.search(lower):
        return False

    symbol_count = sum(1 for ch in lower if ch in "._-")
    if symbol_count > max(3, len(lower) // 3):
        return False

    parts = re.split(r"[._-]+", lower)
    non_empty_parts = [p for p in parts if p]

    if len(non_empty_parts) > 5:
        return False

    if any(len(part) > 20 for part in non_empty_parts):
        return False

    if TRAILING_LONG_DIGITS_RE.match(lower):
        return False

    if TOY_NAME_RE.search(lower):
        return False

    banned_fragments = {
        "odoo",
        "addon",
        "addons",
        "django",
        "plone",
        "tryton",
    }
    if sum(1 for part in non_empty_parts if part in banned_fragments) >= 2:
        return False

    return True


def filter_reasonable(names: list[str]) -> list[str]:
    return [name for name in names if is_reasonable_name(name)]