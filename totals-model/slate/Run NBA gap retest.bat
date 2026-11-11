@echo off
rem The team-total gap rule, re-tested (11 Nov 2026). The rule is scored on two
rem seasons where a gap of a point or more showed on two games in three; this
rem season a book against its own total and spread shows one on about one line
rem in ten, and the calls are 20-18 at home. This reads the three files already
rem in this folder for 2024-25 and 2025-26 and holds every team-total line
rem against three numbers: as the backtest had it, the same book's own total
rem and spread, and the middle of the other books'.
rem
rem   nba-ledger-SEASON.json          (Run NBA ledger.bat)
rem   odds-periods-NBA-SEASON.json    (Run NBA period lines.bat)
rem   odds-history-NBA-SEASON.json    (Run NBA lines history.bat)
rem
rem It reads files only: no site is called and no credit is spent. It writes
rem nba-gap-retest.txt in this folder. Send that file to Claude.
cd /d "%~dp0"
python slate.py nba-gap-retest %*
echo.
echo ---------------------------------------------------------------
echo Done. Send nba-gap-retest.txt from this folder to Claude.
echo ---------------------------------------------------------------
pause
