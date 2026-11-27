@echo off
rem Double-click in the EVENING to read TOMORROW's NBA totals for The Super
rem Model. For each of tomorrow's games it works out the simulation's plain
rem total (the two clubs' ratings at the game's pace, rest in it, nobody out)
rem and sets it against the number DraftKings shows tonight on ESPN's
rem scoreboard. Where the two stand 8 points or more apart, the window names
rem the side, the number, and the number it is good to. Free: no key and no
rem odds credit. It brings this season's ledger up to date first.
rem Why the evening: on three seasons the line then moved the simulation's
rem way 68 times to 18, by 2.8 points, and by the morning of the game the
rem number had caught up. (27 Nov 2026)
cd /d "%~dp0"
python slate.py nba-early %*
echo.
echo ---------------------------------------------------------------
echo Done. Bet a call TONIGHT, at the number shown or better.
echo In The Super Model: Saving, Load slate, pick the nba-early file.
echo The page keeps each call at tonight's number and grades it later.
echo If a game had no number yet, run this again later tonight.
echo ---------------------------------------------------------------
pause
