"""Tests for cli endpoints"""
import sys

import pytest

import squirrel.bin.main as ss_main


def test_cli_help(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["squirrel", "demo", "--help"])
    with pytest.raises(SystemExit):
        ss_main.main()


@pytest.mark.parametrize('subcommand', list(ss_main.MODULES))
def test_help_module(monkeypatch, subcommand: str):
    monkeypatch.setattr(sys, "argv", ["squirrel", subcommand, "--help"])
    with pytest.raises(SystemExit):
        ss_main.main()
