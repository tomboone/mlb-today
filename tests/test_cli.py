import re

import pytest
from typer.testing import CliRunner

from mlb_today.cli import app

runner = CliRunner()

COMMANDS = ["run", "send", "preview", "health"]


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in COMMANDS:
        assert re.search(rf"\b{command}\b", result.output), command


@pytest.mark.parametrize("command", COMMANDS)
def test_stub_commands_exit_1(monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    monkeypatch.setenv("RECIPIENTS", "fan@example.com")

    result = runner.invoke(app, [command])

    assert result.exit_code == 1
    assert '"msg": "not implemented"' in result.output


def test_invalid_config_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RECIPIENTS", raising=False)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 2
    assert "invalid configuration" in result.output
