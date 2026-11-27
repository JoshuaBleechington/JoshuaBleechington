@echo off
rem Double-click a few minutes before the first tip, after the morning's
rem "Run NBA props": pulls the same props again as the books post them now and
rem writes nba-props-close-DATE.json, the closing line on every prop. In The
rem Super Model: NBA PROPS, Load props, pick the close file; it attaches the
rem close to the props already loaded (it adds none), and the record reads every
rem pick against the close as well as the box: a pick that keeps beating the
rem close has an edge the market agrees with, read in weeks where the results
rem take months. About five credits a game, the same as the morning's run.
cd /d "%~dp0"
python slate.py nba-props --close %*
echo.
echo ---------------------------------------------------------------
echo Done. In The Super Model: NBA PROPS, Load props, pick the nba-props-close file.
echo ---------------------------------------------------------------
pause
