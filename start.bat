@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   LoraTool - Qwen3-VL 本地标注
echo ========================================
echo.

REM 检查 venv Python
set VENV_PYTHON=venv\Scripts\python.exe
if not exist "%VENV_PYTHON%" (
    echo [错误] 未找到虚拟环境: %VENV_PYTHON%
    echo 请先创建 venv 并安装依赖:
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo 使用虚拟环境: %VENV_PYTHON%
echo 访问地址: http://127.0.0.1:5000/qwen_vl_label/
echo 按 Ctrl+C 停止
echo.

"%VENV_PYTHON%" app.py
pause
