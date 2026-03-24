#!/bin/zsh

set -euo pipefail

# 基于脚本所在位置反推项目根目录，避免从任意目录启动时路径错乱。
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"

cd "${PROJECT_ROOT}"

echo "[local-test-agent] 项目目录: ${PROJECT_ROOT}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[local-test-agent] 未发现虚拟环境，开始创建 .venv"
  python3 -m venv "${VENV_DIR}"
fi

# 仅在关键依赖缺失时安装，避免每次启动都重复执行 pip。
if ! "${PYTHON_BIN}" -c "import PySide6, pydantic, pytest" >/dev/null 2>&1; then
  echo "[local-test-agent] 检测到基础依赖缺失，开始安装"
  "${PIP_BIN}" install -e '.[dev]'
fi

echo "[local-test-agent] 正在启动桌面应用"
"${PYTHON_BIN}" "${PROJECT_ROOT}/main.py"
