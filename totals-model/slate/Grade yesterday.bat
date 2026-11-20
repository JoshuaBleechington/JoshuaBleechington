@echo off
rem Double-click the morning after: writes yesterday's finals file.
cd /d "%~dp0"
python slate.py grade %*
echo.
echo ---------------------------------------------------------------
echo Done. In Call Sheet 2.0: Saving, Load slate, pick the grade file.
echo ---------------------------------------------------------------
pause
