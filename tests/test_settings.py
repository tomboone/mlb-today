from datetime import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from mlb_today.settings import Settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECIPIENTS", "fan@example.com")

    settings = Settings()

    assert str(settings.tz_local) == "America/New_York"
    assert settings.plan_time == time(3, 0)
    assert settings.send_lead_minutes == 30
    assert settings.scores_only_time == time(9, 0)
    assert settings.data_dir == Path("/data")
    assert settings.smtp_host == "smtp.fastmail.com"
    assert settings.smtp_port == 465
    assert settings.transports == ["resend", "smtp"]
    assert settings.resend_api_key is None
    assert settings.healthchecks_url is None
    assert settings.dry_run is False
    assert settings.log_level == "INFO"
    assert settings.mlb_api_base == "https://statsapi.mlb.com"
    assert settings.fangraphs_api_base == "https://www.fangraphs.com/api/leaders/major-league/data"


def test_recipients_parsed_from_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECIPIENTS", " a@example.com, b@example.com,,")

    assert Settings().recipients == ["a@example.com", "b@example.com"]


def test_transports_parsed_from_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECIPIENTS", "fan@example.com")
    monkeypatch.setenv("TRANSPORTS", "smtp")

    assert Settings().transports == ["smtp"]


def test_unknown_transport_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECIPIENTS", "fan@example.com")
    monkeypatch.setenv("TRANSPORTS", "resend,carrier-pigeon")

    with pytest.raises(ValidationError, match="transports"):
        Settings()


def test_log_level_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECIPIENTS", "fan@example.com")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    assert Settings().log_level == "DEBUG"


def test_missing_recipients_rejected() -> None:
    with pytest.raises(ValidationError, match="recipients"):
        Settings()


@pytest.mark.parametrize("value", ["", " , "])
def test_empty_recipients_rejected(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("RECIPIENTS", value)

    with pytest.raises(ValidationError, match="recipients"):
        Settings()
