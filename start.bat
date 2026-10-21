@echo off
chcp 65001 >nul
title 资产经营公司管理系统
cd /d "%~dp0backend"

if exist "..\.venv\Scripts\python.exe" (
  set "PY=..\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo 正在启动资产经营公司管理系统，端口 8000 ...
%PY% -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
pause
