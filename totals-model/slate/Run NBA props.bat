@echo off
rem Double-click to build tonight's NBA player props for The Super Model's
rem Props tab: every prop the books post on the day's games (points, rebounds,
rem assists, threes, points + rebounds + assists) with the slate's own
rem projection beside each. It brings this season's ledger (the game logs)
rem up to date first; the first time, run "Run NBA ledger" for last season
rem too, so the rebounds, assists and threes have a history. About five
rem credits a game. It reads ESPN's injury report together with RotoWire's
rem lineups page (a RotoWire Out counts; a confirmed starter ESPN still has
rem Out is counted in), plays each game 10,000 times (the slate's own
rem simulation, with that report) and attaches the runs to every prop; run
rem it again nearer tip and the newer runs replace the ungraded props when
rem the file is loaded.
cd /d "%~dp0"
python slate.py nba-props %*
echo.
echo ---------------------------------------------------------------
echo Done. In The Super Model: NBA PROPS, Load props, pick the nba-props file.
echo Tomorrow's "Grade NBA yesterday" grades the props with the card.
echo ---------------------------------------------------------------
pause
