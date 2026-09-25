"""Command line entry point: `katib`, `katib serve`, `katib share`, `katib app`, `katib dev`."""

import contextlib
import logging
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from katib import net
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


@app.command(name="app")
def desktop_app(
    config: Annotated[Path | None, typer.Option(help="Path to katib.toml.")] = None,
) -> None:
    """Open Katib in its own window. Needs the desktop extra."""
    from katib.desktop.window import DesktopUnavailable, run_desktop

    _configure_logging()
    try:
        run_desktop(load_settings(config))
    except DesktopUnavailable as err:
        raise typer.BadParameter(str(err)) from err


@app.command()
def share(
    port: Annotated[int | None, typer.Option(help="Port to bind.")] = None,
    config: Annotated[Path | None, typer.Option(help="Path to katib.toml.")] = None,
) -> None:
    """Start Katib for other devices on your network, with accounts turned on."""
    _run(open_browser=True, host="0.0.0.0", port=port, config=config, share=True)  # noqa: S104


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
    share: bool = False,
) -> None:
    _configure_logging()
    settings = load_settings(config)
    if share:
        settings.auth.mode = "local"
    if host is not None:
        settings.server.host = host
    if port is not None:
        settings.server.port = port
    try:
        settings.check_bind()
    except ValueError as err:
        raise typer.BadParameter(str(err)) from err

    from katib.api.app import create_app

    if share:
        _print_share_help(settings.server.port)
    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{settings.server.port}")
    uvicorn.run(create_app(settings), host=settings.server.host, port=settings.server.port)


def _print_share_help(port: int) -> None:
    urls = [f"http://{address}:{port}" for address in net.lan_addresses()]
    if not urls:
        typer.echo("Could not find this computer's address on your network.")
        return
    typer.echo("Katib is open to your network. Accounts are on, so people sign in.")
    typer.echo("On a phone or another computer, open:")
    for url in urls:
        typer.echo(f"  {url}")
    # Some consoles cannot draw the code. The addresses above still work.
    with contextlib.suppress(UnicodeEncodeError):
        typer.echo(net.qr_terminal(urls[0]))
