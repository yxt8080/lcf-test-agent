#!/bin/zsh

set -euo pipefail

# macOS 下可双击执行，内部统一转到脚本入口，减少启动逻辑分散。
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

exec "${PROJECT_ROOT}/scripts/start.sh"
