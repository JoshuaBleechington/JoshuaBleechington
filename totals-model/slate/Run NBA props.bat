@echo off
rem Double-click to build tonight's NBA player props for The Super Model's
rem Props tab: every prop the books post on the day's games (points, rebounds,
rem assists, threes, points + rebounds + assists) with the slate's own
rem projection beside each. Run "Run NBA ledger" first (blank season) so the
rem game logs are current; the first time, run it for last season too, so the
rem rebounds, assists and threes have a history. About five credits a game.
cd /d "%~dp0"
python slate.py nba-props %*
echo.
echo ---------------------------------------------------------------
echo Done. In The Super Model: NBA PROPS, Load props, pick the nba-props file.
echo Tomorrow's "Grade NBA yesterday" grades the props with the card.
echo ---------------------------------------------------------------
pause
