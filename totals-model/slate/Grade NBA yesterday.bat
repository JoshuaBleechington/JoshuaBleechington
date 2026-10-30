@echo off
rem Double-click the morning after: writes yesterday's NBA finals file with the
rem half-time score and the close the odds run last saw.
cd /d "%~dp0"
python slate.py nba-grade %*
echo.
echo ---------------------------------------------------------------
echo Done. In The Super Model: Saving, Load slate, pick the nba-grade file.
echo ---------------------------------------------------------------
pause
