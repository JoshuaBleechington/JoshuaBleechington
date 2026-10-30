@echo off
rem The simulation's measuring stick (25 Oct 2026): a past season's FIRST-HALF,
rem FIRST-QUARTER and THIRD-QUARTER totals and the TEAM TOTALS at the close,
rem fifteen minutes before each tip, from The Odds API's historical event
rem endpoint, into odds-periods-NBA-SEASON.json beside the NBA ledger. The
rem dates come from the ledger (nba-ledger-SEASON.json), one credit a day to
rem list the games, then ten credits a market a game: a season of the four
rem markets is about 49,000 credits, the first half alone about 12,300. It
rem prints the cost and asks before it spends, writes every 20 games, stops
rem when 3,000 credits are left, and carries on where it stopped when run again.
rem
rem The plan on the 100,000-credit month: 2025-26 with all four markets, then
rem 2024-25 with the first half alone (type totals_h1 at the markets prompt).
cd /d "%~dp0"
set SEASON=
set /p SEASON=Season (2025-26 or 2024-25):
if "%SEASON%"=="" (
  echo No season given.
  pause
  exit /b 1
)
set MARKETS=
set /p MARKETS=Markets (blank = totals_h1,totals_q1,totals_q3,team_totals; or e.g. totals_h1):
if "%MARKETS%"=="" (
  python slate.py odds-periods --season %SEASON% %*
) else (
  python slate.py odds-periods --season %SEASON% --markets %MARKETS% %*
)
echo.
echo ---------------------------------------------------------------
echo Done. Send odds-periods-NBA-%SEASON%.json to Claude: the simulation's
echo first-half, quarter and team-total calls are measured against it.
echo ---------------------------------------------------------------
pause
