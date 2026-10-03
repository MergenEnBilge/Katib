"""Command line entry point: `katib`, `katib serve`, `katib share`, `katib app`, `katib status`,
`katib stop`, `katib dev`."""

import contextlib
import logging
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from katib import net
from katib.config import Settings, get_settings, load_settings

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
def status(
    config: Annotated[Path | None, typer.Option(help="Path to katib.toml.")] = None,
) -> None:
    """Say whether a Katib server is running for this data folder, and where."""
    from katib.server import instance

    settings = load_settings(config)
    running = instance.find_running(settings.data_dir)
    if running is None:
        typer.echo(f"Katib is not running for {settings.data_dir}.")
        raise typer.Exit(1)
    typer.echo(f"Katib {running.version} is running at {running.url} (process {running.pid}).")


@app.command()
def stop(
    config: Annotated[Path | None, typer.Option(help="Path to katib.toml.")] = None,
) -> None:
    """Stop the Katib server running for this data folder."""
    from katib.server import instance

    settings = load_settings(config)
    running = instance.find_running(settings.data_dir)
    if running is None:
        typer.echo("Katib is not running, so there is nothing to stop.")
        return
    if not instance.stop(running, settings.data_dir):
        raise typer.BadParameter(f"Katib at {running.url} did not stop. Is it still busy?")
    typer.echo("Katib has stopped.")


@app.command()
def share(
    port: Annotated[int | None, typer.Option(help="Port to bind.")] = None,
    config: Annotated[Path | None, typer.Option(help="Path to katib.toml.")] = None,
) -> None:
    """Start Katib for other devices on your network, with accounts turned on."""
    _run(open_browser=True, host="0.0.0.0", port=port, config=config, share=True)  # noqa: S104


@app.command()
def restore(
    backup_file: Annotated[Path, typer.Argument(help="A backup zip made from Katib's settings.")],
    replace: Annotated[
        bool, typer.Option("--replace", help="Replace the database that is already there.")
    ] = False,
    config: Annotated[Path | None, typer.Option(help="Path to katib.toml.")] = None,
) -> None:
    """Put a backup back into the data folder. Stop Katib first."""
    from katib.server import instance
    from katib.services import backup
    from katib.services.errors import InvalidInput

    settings = load_settings(config)
    if not instance.lock_is_free(settings.data_dir):
        raise typer.BadParameter("Katib is running for this data folder. Run `katib stop` first.")
    try:
        report = backup.restore(backup_file, settings.data_dir, replace)
    except InvalidInput as err:
        raise typer.BadParameter(err.message) from err
    typer.echo(f"Restored {report.files} files into {settings.data_dir}. Start Katib again.")


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

    from katib.server import instance
    from katib.server.run import AlreadyRunning, ManagedServer

    running = instance.find_running(settings.data_dir)
    if running is not None:
        if open_browser:
            # Asked to open Katib, and it is already open somewhere: show that one.
            webbrowser.open(running.url)
            return
        raise typer.BadParameter(
            f"Katib is already running at {running.url} for this data folder. "
            "Run `katib stop` first, or give it another folder."
        )
    if share:
        _print_share_help(settings)
    if open_browser:
        webbrowser.open(instance.local_url(settings.server.host, settings.server.port))
    try:
        ManagedServer(settings).run_in_foreground()
    except AlreadyRunning as err:
        raise typer.BadParameter(str(err)) from err


def _print_share_help(settings: Settings) -> None:
    urls = [f"http://{address}:{settings.server.port}" for address in net.lan_addresses()]
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
    typer.echo("The first account needs the setup code, printed just below as Katib starts.")
