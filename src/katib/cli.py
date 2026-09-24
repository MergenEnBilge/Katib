"""Command line entry point: `katib`, `katib serve`, `katib dev`."""

import logging
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from katib.config import get_settings, load_settings

app = typer.Typer(add_completion=False, help="Katib annotation server.")


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Start Katib on loopback and open the browser."""
    if ctx.invoked_subcommand is not None:
        return
    _run(open_browser=True)


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Address to bind.")] = None,
    port: Annotated[int | None, typer.Option(help="Port to bind.")] = None,
    config: Annotated[Path | None, typer.Option(help="Path to katib.toml.")] = None,
) -> None:
    """Start the server without opening a browser."""
    _run(open_browser=False, host=host, port=port, config=config)


@app.command()
def dev() -> None:
    """Run the API with auto-reload on the configured port."""
    _configure_logging()
    settings = get_settings()
    uvicorn.run(
        "katib.api.factory:build_app",
        factory=True,
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
    )


def _run(
    *,
    open_browser: bool,
    host: str | None = None,
    port: int | None = None,
    config: Path | None = None,
) -> None:
    _configure_logging()
    settings = load_settings(config)
    if host is not None:
        settings.server.host = host
    if port is not None:
        settings.server.port = port
    try:
        settings.check_bind()
    except ValueError as err:
        raise typer.BadParameter(str(err)) from err

    from katib.api.app import create_app

    if open_browser:
        webbrowser.open(f"http://{settings.server.host}:{settings.server.port}")
    uvicorn.run(create_app(settings), host=settings.server.host, port=settings.server.port)
