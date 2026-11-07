@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

title Video Boost

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python -c "import sys" >nul 2>&1 && set "PY=python"
)

if not defined PY (
    echo.
    echo ============================================================
    echo   Не найден Python 3.
    echo.
    echo   Установите Python 3.10 или новее с сайта python.org
    echo   и обязательно отметьте "Add Python to PATH".
    echo   Затем запустите этот файл снова.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

%PY% main.py
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo ------------------------------------------------------------
    echo   Программа завершилась с ошибкой, код %RC%.
    echo   Скопируйте текст выше, чтобы понять причину.
    echo ------------------------------------------------------------
    echo.
    pause
)

endlocal
exit /b %RC%
