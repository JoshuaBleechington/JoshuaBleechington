@echo off
rem Double-click to update the league ledger: every NHL final this season, with
rem period scores, shots, empty-net goals and overtime, in one growing file.
rem It also prints the measured league figures against the sheet's assumptions
rem and fills the first-period last ten on tomorrow's slate.
cd /d "%~dp0"
python slate.py nhl-ledger %*
echo.
echo ---------------------------------------------------------------
echo Done. The ledger lives in this folder as nhl-ledger-SEASON.json.
echo Run it before "Run NHL slate" so the first-period form fills.
echo ---------------------------------------------------------------
pause
