@echo off
rem The hockey simulation's play-by-play (29 Oct 2026): every regular-season
rem game's events from ESPN (the shots, the penalties with their clocks and
rem kinds, the goals with the strength state, the officials), one call a game,
rem into nhl-pbp-SEASON.json beside the NHL ledger. The slate refreshes THIS
rem season's file itself each night (the days since the last game); run this
rem for a PAST season once, so last season's minors and power-play time feed
rem the profiles' prior. About 1,300 calls, 10-15 minutes, written every 100
rem games; it carries on where it stopped when run again.
cd /d "%~dp0"
set SEASON=
set /p SEASON=Season (blank = this season; 20252026 for last season):
if "%SEASON%"=="" (
  python slate.py nhl-pbp %*
) else (
  python slate.py nhl-pbp --season %SEASON% %*
)
echo.
echo ---------------------------------------------------------------
echo Done. The slate reads nhl-pbp-SEASON.json beside it on its next run.
echo ---------------------------------------------------------------
pause
