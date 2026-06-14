@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   LoraTool
echo ========================================
echo.

REM 检测虚拟环境
set "VENV_DIR=%~dp0venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_ACTIVATE=%VENV_DIR%\Scripts\activate.bat"

if not exist "%VENV_PYTHON%" (
    echo [错误] 未找到虚拟环境: %VENV_DIR%
    echo.
    echo 请先执行以下命令创建虚拟环境:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo 激活虚拟环境...
call "%VENV_ACTIVATE%"

REM 检测关键依赖
"%VENV_PYTHON%" -c "import flask" 2>nul
if %errorlevel% neq 0 (
    echo [错误] 缺少依赖，请安装:
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo 访问地址: http://127.0.0.1:5000
echo 按 Ctrl+C 停止
echo ========================================
echo.

python run.py
pause
