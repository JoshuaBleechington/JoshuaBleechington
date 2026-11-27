@echo off
rem Double-click to build or update the NBA ledger: every regular-season final
rem of a season with quarter scores, pace and every player's minutes, in one
rem file per season (nba-ledger-SEASON.json). Blank = this season up to today.
rem For the backtest run it twice: 2024-25 and 2025-26 (about ten minutes each;
rem it writes every 100 games, so it can be stopped and run again).
cd /d "%~dp0"
set SEASON=
set /p SEASON=Season to pull (blank = this season, or e.g. 2024-25):
if "%SEASON%"=="" (
  python slate.py nba-ledger %*
) else (
  python slate.py nba-ledger --season %SEASON% %*
)
echo.
echo ---------------------------------------------------------------
echo Done. The ledger lives in this folder as nba-ledger-SEASON.json.
echo ---------------------------------------------------------------
pause
