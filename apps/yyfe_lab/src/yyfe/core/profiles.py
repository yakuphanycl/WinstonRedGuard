from __future__ import annotations

from importlib import import_module
from typing import Any, Callable

# builtins
_BUILTIN = {
    "lab": "yyfe.profiles.lab:build_plan",
}

BuildPlanFn = Callable[[Any], dict[str, Any]]


def _load_ref(ref: str) -> BuildPlanFn:
    mod_name, fn_name = ref.split(":")
    mod = import_module(mod_name)
    fn = getattr(mod, fn_name)
    if not callable(fn):
        raise TypeError(f"profile builder is not callable: {ref}")
    return fn


def get_builder(profile: str) -> BuildPlanFn:
    ref = _BUILTIN.get(profile)
    if not ref:
        raise KeyError(f"unknown profile: {profile!r}")
    return _load_ref(ref)
