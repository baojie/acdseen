#!/usr/bin/env bash
# ACDSeeN 启动脚本。
# 用法:
#   ./run.sh                  打开上次的目录（没有就是当前目录）
#   ./run.sh ~/Pictures       打开指定目录的浏览器
#   ./run.sh photo.jpg        直接全屏看这张图
set -euo pipefail

# 切换到脚本所在目录，保证从任意位置运行都正确
cd "$(dirname "$0")"

VENV_DIR=".venv"
PY="$VENV_DIR/bin/python"

if [ ! -x "$PY" ]; then
    echo "错误：找不到虚拟环境，请先运行 ./setup.sh" >&2
    exit 1
fi

if ! "$PY" -c "import PySide6" 2>/dev/null; then
    echo "错误：PySide6 未安装，请运行 ./setup.sh" >&2
    exit 1
fi

exec "$PY" -m acdseen "$@"
