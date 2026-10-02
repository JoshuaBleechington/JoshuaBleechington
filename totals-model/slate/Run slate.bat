@echo off
rem Double-click to build today's slate. Runs slate.py from this folder and
rem keeps the window open so the output can be read.
cd /d "%~dp0"
python slate.py %*
echo.
echo ---------------------------------------------------------------
echo Done. In Call Sheet 2.0: Saving, Load slate, pick the slate file.
echo ---------------------------------------------------------------
pause
