from __future__ import annotations

from typing import List

from devtool_genome.data.schema import ToolRecord
from devtool_genome.data.store import load_tools


def list_tools() -> List[ToolRecord]:
    return load_tools()
