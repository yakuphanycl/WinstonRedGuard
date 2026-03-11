from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ToolRecord:
    """
    Canonical representation of a developer tool.

    IMPORTANT:
    ToolRecord is the primary entity of devtool_genome.

    Packages are treated only as evidence or distribution artifacts.
    This avoids the PyPI noise problem.
    """

    id: str
    name: str
    category: str
    tags: List[str]
    summary: str

    homepage: Optional[str] = None
    source_repo: Optional[str] = None
    cli_command: Optional[str] = None
    install_methods: Optional[List[str]] = None