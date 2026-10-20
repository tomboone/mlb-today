"""Command-line entry point (spec §9). Every command is a stub until its ticket lands."""

import logging

import typer
from pydantic import ValidationError

from mlb_today.logging import configure_logging
from mlb_today.settings import Settings

app = typer.Typer(no_args_is_help=True, add_completion=False)
log = logging.getLogger(__name__)


def _bootstrap() -> Settings:
    try:
        settings = Settings()
    except ValidationError as exc:
        configure_logging()
        log.error("invalid configuration", extra={"errors": exc.errors(include_url=False)})
        raise typer.Exit(2) from exc
    configure_logging(settings.log_level)
    return settings


def _not_implemented(command: str) -> None:
    _bootstrap()
    log.error("not implemented", extra={"command": command})
    raise typer.Exit(1)


@app.command()
def run() -> None:
    """Run the scheduler loop (container entrypoint)."""
    _not_implemented("run")


@app.command()
def send() -> None:
    """Build and send one digest now."""
    _not_implemented("send")


@app.command()
def preview() -> None:
    """Render a digest to a file without sending."""
    _not_implemented("preview")


@app.command()
def health() -> None:
    """Exit 0 if the scheduler has been active recently."""
    _not_implemented("health")
