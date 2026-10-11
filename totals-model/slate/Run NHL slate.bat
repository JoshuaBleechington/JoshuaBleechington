@echo off
rem Double-click to build tonight's NHL slate for Call Sheet 3.0.
cd /d "%~dp0"
python slate.py nhl %*
echo.
echo ---------------------------------------------------------------
echo Done. In Call Sheet 3.0: Saving, Load slate, pick the nhl-slate file.
echo Then confirm each goalie on Daily Faceoff and tick the box.
echo ---------------------------------------------------------------
pause
