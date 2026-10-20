import json
import os
import re
import signal
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from typer.testing import CliRunner

from mlb_today.cli import app
from mlb_today.scheduler import Scheduler
from mlb_today.settings import Settings
from mlb_today.sources.snapshot import SnapshotStore
from tests.mocked_sources import mock_sources, seed_snapshots

runner = CliRunner()

COMMANDS = ["run", "send", "preview", "health"]
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    # Typer forces Rich styling under GITHUB_ACTIONS; strip it so word boundaries match.
    output = ANSI_ESCAPE.sub("", result.output)
    for command in COMMANDS:
        assert re.search(rf"\b{command}\b", output), command


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A clean environment with recipients and a data volume under `tmp_path`; returns it."""
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.setenv("RECIPIENTS", "fan@example.com")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


def test_invalid_config_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RECIPIENTS", raising=False)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 2
    assert "invalid configuration" in result.output


@respx.mock
def test_send_dry_run_writes_the_outbox_for_the_date(env: Path) -> None:
    mock_sources(respx.mock)

    result = runner.invoke(app, ["send", "--date", "2026-09-23", "--dry-run"])

    assert result.exit_code == 0, result.output
    html = env / "outbox" / "2026-09-23.html"
    assert "MLB Today" in html.read_text()
    assert (env / "outbox" / "2026-09-23.txt").exists()
    receipt = json.loads(result.output.splitlines()[-1])
    assert (receipt["transport"], receipt["message_id"]) == ("outbox", str(html))


@respx.mock
def test_send_honours_dry_run_from_the_environment(
    env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DRY_RUN", "true")
    mock_sources(respx.mock)

    result = runner.invoke(app, ["send", "--date", "2026-06-15"])

    assert result.exit_code == 0, result.output
    assert (env / "outbox" / "2026-06-15.html").exists()


@respx.mock
def test_send_defaults_to_today_in_the_local_zone(env: Path) -> None:
    mock_sources(respx.mock)

    result = runner.invoke(app, ["send", "--dry-run"])

    assert result.exit_code == 0, result.output
    today = datetime.now(UTC).astimezone(ZoneInfo("America/New_York")).date()
    assert (env / "outbox" / f"{today.isoformat()}.html").exists()


def test_send_without_a_configured_transport_exits_2(env: Path) -> None:
    result = runner.invoke(app, ["send", "--date", "2026-09-23"])

    assert result.exit_code == 2
    assert "no transport is configured" in result.output


def test_preview_from_snapshots_writes_html_and_text_without_network(env: Path) -> None:
    seed_snapshots(SnapshotStore(env))
    out = env / "d.html"

    with respx.mock(assert_all_called=False) as router:
        anything = router.route().mock(return_value=httpx.Response(500))
        result = runner.invoke(
            app, ["preview", "--date", "2026-09-23", "--from-snapshots", "--out", str(out)]
        )

    assert result.exit_code == 0, result.output
    assert anything.call_count == 0
    assert "<html" in out.read_text()
    assert "MLB Today" in out.with_suffix(".txt").read_text()
    assert not (env / "outbox").exists()


def test_run_without_a_configured_transport_exits_2(env: Path) -> None:
    result = runner.invoke(app, ["run"])

    assert result.exit_code == 2
    assert "no transport is configured" in result.output


def test_run_stops_cleanly_on_sigterm(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DRY_RUN", "true")
    handlers: dict[int, Callable[[int, object], None]] = {}

    def record(signum: int, handler: Callable[[int, object], None]) -> None:
        handlers[signum] = handler

    def no_cycle(self: Scheduler) -> None:
        raise AssertionError("the scheduler planned after SIGTERM")

    real_run_forever = Scheduler.run_forever

    def sigterm_then_run(self: Scheduler) -> None:
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        real_run_forever(self)

    monkeypatch.setattr("mlb_today.cli.signal.signal", record)
    monkeypatch.setattr(Scheduler, "cycle", no_cycle)
    monkeypatch.setattr(Scheduler, "run_forever", sigterm_then_run)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0, result.output
    assert '"msg": "scheduler stopped"' in result.output


def _state_file(data_dir: Path, age_hours: float) -> Path:
    path = data_dir / "state.json"
    path.write_text("{}")
    mtime = time.time() - age_hours * 3600
    os.utime(path, (mtime, mtime))
    return path


def test_health_exits_0_with_a_fresh_state_file(env: Path) -> None:
    _state_file(env, age_hours=1)

    result = runner.invoke(app, ["health"])

    assert result.exit_code == 0, result.output


def test_health_exits_1_with_a_27_hour_old_state_file(env: Path) -> None:
    _state_file(env, age_hours=27)

    result = runner.invoke(app, ["health"])

    assert result.exit_code == 1
    assert "state file last updated 27.0 hours ago" in result.output


def test_health_exits_1_without_a_state_file(env: Path) -> None:
    result = runner.invoke(app, ["health"])

    assert result.exit_code == 1
    assert "no state file" in result.output


def test_health_exits_1_not_2_on_invalid_config(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Docker reserves health-check exit code 2.
    monkeypatch.delenv("RECIPIENTS")

    result = runner.invoke(app, ["health"])

    assert result.exit_code == 1
