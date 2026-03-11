from devtool_genome.data.schema import ToolRecord


def ingest_sample():
    tools = [
        ToolRecord(
            id="typer",
            name="typer",
            category="cli",
            tags=["python","cli"],
            summary="Modern Python CLI framework"
        ),
        ToolRecord(
            id="click",
            name="click",
            category="cli",
            tags=["python","cli"],
            summary="Composable CLI toolkit"
        )
    ]

    return tools