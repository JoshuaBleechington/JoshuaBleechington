@echo off
rem The backtest's openers: a past season's hockey lines at two moments a
rem day (noon and 7:30 pm Eastern) from The Odds API, into
rem odds-history-NHL-SEASON.json, beside the season ledger. Ten credits a
rem snapshot; a season is about 3,700. It prints the cost and asks before it
rem spends, stops when 3,000 credits are left for the nightly runs, and
rem carries on where it stopped when run again.
cd /d "%~dp0"
set SEASON=
set /p SEASON=Season id (20252026 or 20242025):
if "%SEASON%"=="" (
  echo No season given.
  pause
  exit /b 1
)
python slate.py odds-history --sports NHL --season %SEASON% --books fanatics,betmgm,draftkings,fanduel,caesars,espnbet,betrivers,pinnacle %*
echo.
echo ---------------------------------------------------------------
echo Done. Send odds-history-NHL-%SEASON%.json to Claude with the season
echo ledger; tools_backtest_nhl_odds.py measures the opener, the move and
echo the sharp line against the finals.
echo ---------------------------------------------------------------
pause
