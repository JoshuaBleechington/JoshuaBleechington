@echo off
rem The dog's price for the upset test: a past NBA season's closing MONEYLINES,
rem one snapshot a game day (6:30 pm Eastern, before the 7 pm tips) from The
rem Odds API, into odds-history-NBA-SEASON.json beside the NBA ledger. The
rem dates come from the ledger (nba-ledger-SEASON.json: run Run NBA ledger for
rem the season first), so no off day is spent on. Ten credits a snapshot: a
rem season is about 1,650. It prints the cost and asks before it spends, stops
rem when 3,000 credits are left for the nightly runs, and carries on where it
rem stopped when run again. Run it twice: 2024-25 and 2025-26.
cd /d "%~dp0"
set SEASON=
set /p SEASON=Season (2024-25 or 2025-26):
if "%SEASON%"=="" (
  echo No season given.
  pause
  exit /b 1
)
python slate.py odds-history --sports NBA --season %SEASON% --books fanatics,betmgm,draftkings,fanduel,caesars,espnbet,betrivers,pinnacle %*
echo.
echo ---------------------------------------------------------------
echo Done. Send odds-history-NBA-%SEASON%.json to Claude: the upset test
echo measures each dog at the price it paid.
echo ---------------------------------------------------------------
pause
