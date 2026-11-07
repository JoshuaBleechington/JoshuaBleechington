@echo off
rem Double-click the morning after: writes yesterday's NHL finals file.
cd /d "%~dp0"
python slate.py nhl-grade %*
echo.
echo ---------------------------------------------------------------
echo Done. In Call Sheet 3.0: Saving, Load slate, pick the nhl-grade file.
echo ---------------------------------------------------------------
pause
