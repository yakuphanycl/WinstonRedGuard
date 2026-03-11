from __future__ import annotations

from typing import List

from devtool_genome.data.schema import ToolRecord


def load_tools() -> List[ToolRecord]:
    return [
        ToolRecord(
            id="pytest",
            name="pytest",
            category="testing",
            tags=["python", "tests", "qa"],
            summary="Python test runner and testing framework",
        ),
        ToolRecord(
            id="nox",
            name="nox",
            category="testing",
            tags=["python", "automation"],
            summary="Python automation tool similar to tox",
        ),
        ToolRecord(
            id="tox",
            name="tox",
            category="testing",
            tags=["python", "env", "ci"],
            summary="Automate Python testing across environments",
        ),
        ToolRecord(
            id="ruff",
            name="ruff",
            category="linting",
            tags=["python", "lint", "format"],
            summary="Fast Python linter and formatter",
        ),
        ToolRecord(
            id="flake8",
            name="flake8",
            category="linting",
            tags=["python", "lint"],
            summary="Python style guide enforcement tool",
        ),
        ToolRecord(
            id="mypy",
            name="mypy",
            category="linting",
            tags=["python", "typing", "static-analysis"],
            summary="Static type checker for Python",
        ),
        ToolRecord(
            id="black",
            name="black",
            category="formatting",
            tags=["python", "format"],
            summary="Opinionated Python code formatter",
        ),
        ToolRecord(
            id="isort",
            name="isort",
            category="formatting",
            tags=["python", "imports"],
            summary="Sort Python imports automatically",
        ),
        ToolRecord(
            id="pre-commit",
            name="pre-commit",
            category="workflow",
            tags=["git", "hooks"],
            summary="Framework for managing git pre-commit hooks",
        ),
        ToolRecord(
            id="uv",
            name="uv",
            category="packaging",
            tags=["python", "package-manager"],
            summary="Extremely fast Python package installer",
        ),
        ToolRecord(
            id="pipx",
            name="pipx",
            category="packaging",
            tags=["python", "cli"],
            summary="Install and run Python CLI tools in isolated environments",
        ),
        ToolRecord(
            id="poetry",
            name="poetry",
            category="packaging",
            tags=["python", "dependency"],
            summary="Python dependency management and packaging tool",
        ),
        ToolRecord(
            id="httpie",
            name="httpie",
            category="cli-tools",
            tags=["http", "api"],
            summary="User-friendly HTTP client for the terminal",
        ),
        ToolRecord(
            id="ripgrep",
            name="ripgrep",
            category="cli-tools",
            tags=["search", "files"],
            summary="Fast recursive search tool",
        ),
        ToolRecord(
            id="fd",
            name="fd",
            category="cli-tools",
            tags=["files", "search"],
            summary="Simple, fast alternative to find",
        ),
    ]