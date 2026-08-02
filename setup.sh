#!/usr/bin/env bash
# ACDSeeN 环境搭建：创建虚拟环境并安装依赖。
set -euo pipefail

# 切换到脚本所在目录，保证从任意位置运行都正确
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV_DIR=".venv"

echo "==> 使用解释器: $($PYTHON --version 2>&1)"

if [ ! -d "$VENV_DIR" ]; then
    echo "==> 创建虚拟环境 $VENV_DIR"
    "$PYTHON" -m venv "$VENV_DIR"
else
    echo "==> 虚拟环境已存在，跳过创建"
fi

PIP="$VENV_DIR/bin/pip"
echo "==> 升级 pip"
"$PIP" install --upgrade pip

echo "==> 安装依赖（见 requirements.txt）"
"$PIP" install -r requirements.txt

echo ""
echo "完成！运行 ./run.sh 启动。"
