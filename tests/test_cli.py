"""One-shot CLI tests (no display needed)."""

from __future__ import annotations

import pytest

from radix import __version__
from radix.__main__ import main


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_help_shows_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-e", "help"]) == 0
    assert f"Radix v{__version__}" in capsys.readouterr().out


def test_evaluate_prints_integer_views(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-e", "0xFF << 2"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("1020")
    assert "0x0000_03FC" in out
