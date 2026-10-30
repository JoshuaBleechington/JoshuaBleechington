@echo off
rem Double-click to build tonight's NBA slate for The Super Model: each club's
rem ratings, pace and games to date from the ledger, rest, the injury report
rem as the who-is-out list, RotoWire's starting fives, and the context lines.
rem It brings this season's ledger up to date first, so the ratings and the
rem last-five cards are current, and plays each game 10,000 times for the
rem Simulation card (nbasim.py and nba-tend.json beside this file). Lines
rem come from "Run odds".
cd /d "%~dp0"
python slate.py nba %*
echo.
echo ---------------------------------------------------------------
echo Done. In The Super Model: Saving, Load slate, pick the nba-slate file.
echo Then run the odds. Run this again an hour before tip: the injury
echo report and the starting fives (expected, then confirmed) move all day.
echo ---------------------------------------------------------------
pause
