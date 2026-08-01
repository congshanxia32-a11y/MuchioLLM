@echo off
rem MuchioLLM launcher. Works with or without VRCPet running.
rem NOTE: keep this file ASCII-only. Japanese text breaks cmd parsing.
rem ---- audio device names, empty = system default ----
rem For VR via Virtual Desktop, set both to "Virtual Desktop".
rem See README.md for details.
set MIC=
set SPK=
rem ----------------------------------------------------
cd /d %~dp0
rem Pick python: the one recorded by setup.bat, else first non-Store python, else PATH.
set "PY=python"
set "PYX="
if exist python_path.txt set /p PY=<python_path.txt
if not exist "%PY%" for /f "delims=" %%P in ('where python 2^>nul ^| findstr /v /i "WindowsApps"') do if not defined PYX set "PYX=%%P"
if not exist "%PY%" if defined PYX set "PY=%PYX%"
rem Kill old instances first to avoid port conflicts and double listening.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'muchio_llm.py|vrc_listener.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
start "MuchioLLM" /min "%PY%" muchio_llm.py
rem Start the ear processes only when their libraries exist, else warn visibly
rem instead of letting the windows flash-crash (happens when setup.bat was skipped).
"%PY%" -c "import numpy, pyaudiowpatch" >nul 2>&1
if not errorlevel 1 goto :ears
echo.
echo [WARN] Listener libraries are missing - the pet cannot HEAR anyone yet.
echo [WARN] Please run setup.bat first, then run.bat again.
echo.
pause
goto :open
:ears
start "VRCListener" /min "%PY%" vrc_listener.py %SPK%
start "OwnerMic" /min "%PY%" vrc_listener.py --mic %MIC%
:open
rem Open the settings page once the UI server is up.
timeout /t 3 /nobreak >nul
start "" http://localhost:8787
