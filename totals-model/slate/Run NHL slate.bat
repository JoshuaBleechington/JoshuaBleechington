@echo off
rem Double-click to build tonight's NHL slate for Call Sheet 3.0.
rem Run the odds first (Run odds.bat): the simulation anchors its market view
rem to the day's odds-DATE.json, and without it runs its own view only.
rem The slate also refreshes this season's play-by-play from ESPN (the days
rem since the last game) and this season's shot file from MoneyPuck before
rem it simulates; the first run also fetches last season's shots once.
cd /d "%~dp0"
python slate.py nhl %*
echo.
echo ---------------------------------------------------------------
echo Done. In Call Sheet 3.0: Saving, Load slate, pick the nhl-slate file.
echo The slate reads RotoWire's lineups and CBS's goalie depth chart: a confirmed start is ticked already.
echo Check the ones it calls EXPECTED on RotoWire before you bet, and tick the box when they turn green.
echo The simulation on each row decides the full-game and first-period totals.
echo ---------------------------------------------------------------
pause
