from typer.testing import CliRunner

from self_improving_outreach.cli import app
from self_improving_outreach.runtime import SAMPLE_QUEUE

runner = CliRunner()


def test_cli_show_config_is_mock():
    result = runner.invoke(app, ["show-config"])
    assert result.exit_code == 0
    assert "Cubiczan" in result.stdout
    assert "true" in result.stdout.lower() or "True" in result.stdout


def test_cli_run_one_lead():
    result = runner.invoke(
        app,
        [
            "run",
            "--lead",
            '{"company":"Northline Manufacturing","title":"CFO","contact_name":"Priya","industry":"manufacturing","signals":{"pain":"material weakness"}}',
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Cubiczan" in result.stdout
    assert "approved_for_scout" in result.stdout or "draft" in result.stdout.lower()


def test_cli_swarm_once():
    result = runner.invoke(
        app,
        ["swarm", "--once", "--concurrency", "2", "--queue", str(SAMPLE_QUEUE)],
    )
    assert result.exit_code == 0, result.stdout
    assert "succeeded" in result.stdout
