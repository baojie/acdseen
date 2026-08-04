"""Command-line entry point.

The key is that --help / --version must return before QApplication is created --
otherwise they'd hang or pop a window in a displayless environment.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from acdseen import __version__
from acdseen.main import main


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help不开GUI(flag, capsys):
    assert main(["acdseen", flag]) == 0
    # Usage text follows the UI language; only assert the fragment common to both languages
    assert "acdseen" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_version不开GUI(flag, capsys):
    assert main(["acdseen", flag]) == 0
    assert __version__ in capsys.readouterr().out


def test_子进程里help能秒退():
    """Truly verifies "no GUI": must return instantly even without QT_QPA_PLATFORM set."""
    r = subprocess.run([sys.executable, "-m", "acdseen", "--help"],
                       capture_output=True, text=True, timeout=20)
    assert r.returncode == 0
    assert "acdseen" in r.stdout   # child process doesn't inherit the test's language isolation; assert a language-neutral fragment
