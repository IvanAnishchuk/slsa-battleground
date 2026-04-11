"""Tests for the CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from slsa_battleground.cli import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.0.2" in result.output


def test_hello_default() -> None:
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "Hello" in result.output
    assert "world" in result.output


def test_hello_with_name() -> None:
    result = runner.invoke(app, ["hello", "Alice"])
    assert result.exit_code == 0
    assert "Alice" in result.output


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0 or "Usage" in result.output
