@echo off
rem The hockey simulation's measuring stick (29 Oct 2026): a past season's
rem FIRST-PERIOD totals, and the TEAM TOTALS beside them, at the close, fifteen
rem minutes before each puck drop, from The Odds API's historical event endpoint,
rem into odds-periods-NHL-SEASON.json beside the NHL ledger. The dates come from
rem the ledger (nhl-ledger-SEASON.json), one credit a day to list the games, then
rem ten credits a market a game: a season of the first-period total alone is
rem about 13,300 credits, with the team totals about 26,500. It prints the cost
rem and asks before it spends, writes every 20 games, stops when 3,000 credits
rem are left, and carries on where it stopped when run again.
rem
rem The plan before the credits reset on the 1st: 2025-26 with totals_p1 alone
rem (type totals_p1 at the markets prompt), then 2024-25 the same if the credits
rem allow; the team totals can wait for next month's credits.
cd /d "%~dp0"
set SEASON=
set /p SEASON=Season (20252026 or 20242025):
if "%SEASON%"=="" (
  echo No season given.
  pause
  exit /b 1
)
set MARKETS=
set /p MARKETS=Markets (blank = totals_p1,team_totals; or totals_p1 for the first period alone):
if "%MARKETS%"=="" (
  python slate.py odds-periods --sport NHL --season %SEASON% %*
) else (
  python slate.py odds-periods --sport NHL --season %SEASON% --markets %MARKETS% %*
)
echo.
echo ---------------------------------------------------------------
echo Done. Send odds-periods-NHL-%SEASON%.json to Claude: the hockey
echo simulation's first-period and team-total calls are measured against it.
echo ---------------------------------------------------------------
pause
