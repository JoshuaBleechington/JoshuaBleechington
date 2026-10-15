@echo off
rem Double-click to build tonight's NBA slate for The Super Model: each club's
rem ratings, pace and games to date from the ledger, rest, the injury report
rem as the who-is-out list, and the context lines. Run "Run NBA ledger" first
rem (blank season) so the ratings are current. Lines come from "Run odds".
cd /d "%~dp0"
python slate.py nba %*
echo.
echo ---------------------------------------------------------------
echo Done. In The Super Model: Saving, Load slate, pick the nba-slate file.
echo Then run the odds, and check the injury report an hour before tip.
echo ---------------------------------------------------------------
pause
