@echo off
rem Double-click to build tonight's NHL slate for Call Sheet 3.0.
cd /d "%~dp0"
python slate.py nhl %*
echo.
echo ---------------------------------------------------------------
echo Done. In Call Sheet 3.0: Saving, Load slate, pick the nhl-slate file.
echo The slate reads RotoWire's lineups and CBS's goalie depth chart: a confirmed start is ticked already.
echo Check the ones it calls EXPECTED on RotoWire before you bet, and tick the box when they turn green.
echo ---------------------------------------------------------------
pause
