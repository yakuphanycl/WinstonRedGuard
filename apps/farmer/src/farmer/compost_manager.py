from __future__ import annotations

from .seed_bank import find_seed, update_seed


def add_to_compost(name: str, reason: str) -> dict:
    seed = find_seed(name)
    if seed is None:
        raise ValueError(f"seed not found: {name}")
    if not reason or not reason.strip():
        raise ValueError("reason is required")
    return update_seed(name, {"status": "composted", "notes": f"compost reason: {reason.strip()}"})
