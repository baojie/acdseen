"""命令行入口。

关键是 --help / --version 必须在建 QApplication 之前返回 —— 否则
在无显示环境下会直接卡住或弹出窗口。
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
    assert "用法" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_version不开GUI(flag, capsys):
    assert main(["acdseen", flag]) == 0
    assert __version__ in capsys.readouterr().out


def test_子进程里help能秒退():
    """真正验证"不开 GUI"：连 QT_QPA_PLATFORM 都不设也必须瞬间返回。"""
    r = subprocess.run([sys.executable, "-m", "acdseen", "--help"],
                       capture_output=True, text=True, timeout=20)
    assert r.returncode == 0
    assert "用法" in r.stdout
