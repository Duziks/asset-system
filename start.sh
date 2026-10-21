#!/usr/bin/env bash
# 资产经营公司管理系统 - Linux 启动脚本
# 用法: ./start.sh        默认 8000 端口
#       PORT=9000 ./start.sh
set -e
cd "$(dirname "$0")/backend"

if [ -x "../.venv/bin/python" ]; then
  PY="../.venv/bin/python"
else
  PY="python3"
fi

exec "$PY" -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
