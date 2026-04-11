"""CLI entry point for slsa-battleground."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from slsa_battleground import __version__

app = typer.Typer(
    name="slsa-battleground",
    help="Minimal package for testing SLSA provenance in GitHub Actions",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"slsa-battleground {__version__}")
        raise typer.Exit


@app.callback()
def main(
    _version: Annotated[
        bool,
        typer.Option("--version", "-V", callback=version_callback, is_eager=True, help="Show version and exit."),
    ] = False,
) -> None:
    """Minimal package for testing SLSA provenance in GitHub Actions."""


@app.command()
def hello(
    name: Annotated[str, typer.Argument(help="Name to greet.")] = "world",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output.")] = False,
) -> None:
    """Say hello (placeholder command)."""
    if verbose:
        console.print("[dim]verbose mode enabled[/]")
    console.print(f"Hello, [bold]{name}[/]!")
