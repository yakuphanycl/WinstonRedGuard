from typer.testing import CliRunner

from devtool_genome.cli.main import app

runner = CliRunner()


def test_list_category_filter():
    result = runner.invoke(app, ["list", "--category", "testing"])
    assert result.exit_code == 0
    assert "pytest" in result.stdout


def test_json_output():
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0
    assert "pytest" in result.stdout