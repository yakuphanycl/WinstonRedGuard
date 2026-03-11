from __future__ import annotations

import json
import typer

from devtool_genome.core.catalog import list_tools
from devtool_genome.core.query import search_tools
from devtool_genome.collector.ranked import collect_watchlist_ranked

app = typer.Typer()


@app.command("watchlist")
def watchlist_command() -> None:
    results = collect_watchlist_ranked()

    for item in results:
        print(f"{item.score:>3} | {item.name:<16} | {item.summary[:100]}")

@app.command("list")
def list_command(
    category: str | None = typer.Option(None, "--category"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:

    tools = list_tools()

    if category:
        tools = [t for t in tools if t.category == category]

    if json_output:
        print(json.dumps([t.__dict__ for t in tools], indent=2))
        raise typer.Exit()

    if not tools:
        print("No tools found.")
        raise typer.Exit()

    for tool in tools:
        print(f"{tool.name} | {tool.category} | {tool.summary}")


@app.command("search")
def search_command(
    query: str,
    json_output: bool = typer.Option(False, "--json"),
) -> None:

    results = search_tools(query)

    if json_output:
        print(json.dumps([t.__dict__ for t in results], indent=2))
        raise typer.Exit()

    if not results:
        print("No tools found.")
        raise typer.Exit()

    for tool in results:
        print(f"{tool.name} | {tool.category} | {tool.summary}")


def main():
    app()


if __name__ == "__main__":
    main()