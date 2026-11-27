@echo off
setlocal
cd /d "%~dp0"
set "TOOLKIT_WORKSPACE=%~dp0job-search-workspace"
if not "%~1"=="" set "TOOLKIT_WORKSPACE=%~f1"
python -B "skills\careerpilot\scripts\toolkit.py" --workspace "%TOOLKIT_WORKSPACE%" init
if errorlevel 1 goto failed
python -B "skills\careerpilot\scripts\toolkit.py" --workspace "%TOOLKIT_WORKSPACE%" dashboard --port 0 --open
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Dashboard could not start. Check the error above and that Python 3.10+ is available.
echo The dashboard requests an available local port automatically.
echo If socket access is still denied, check whether security software blocks Python local connections.
pause
exit /b 1
