@echo off
chcp 65001 > nul
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0unlock_files.py" %*
    goto :end
)

where py >nul 2>nul
if %errorlevel%==0 (
    py "%~dp0unlock_files.py" %*
    goto :end
)

echo 未找到 Python，请先安装 Python 并勾选 Add Python to PATH。
pause

:end