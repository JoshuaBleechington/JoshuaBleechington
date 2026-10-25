@echo off
rem Every book's TOTAL, SPREAD and MONEYLINE for a past NBA season at two
rem moments a day (25 Oct 2026): noon Eastern for the opener and 6:30 pm
rem Eastern for the close, from The Odds API, into odds-history-NBA-SEASON.json
rem beside the NBA ledger (the same file the moneyline pull wrote; this adds
rem the other snapshot and the markets). Ten credits a market a snapshot: a
rem season is about 10,000. It prints the cost and asks before it spends,
rem stops when 3,000 credits are left, and carries on where it stopped when
rem run again. Run it twice: 2025-26 and 2024-25. Pinnacle rides in it as the
rem sharp line, so the sheet's Pinnacle-shade signal gets its two seasons.
cd /d "%~dp0"
set SEASON=
set /p SEASON=Season (2025-26 or 2024-25):
if "%SEASON%"=="" (
  echo No season given.
  pause
  exit /b 1
)
python slate.py odds-history --sports NBA --season %SEASON% --markets totals,spreads,h2h --times 16:00,22:30 --books fanatics,betmgm,draftkings,fanduel,caesars,espnbet,betrivers,pinnacle %*
echo.
echo ---------------------------------------------------------------
echo Done. Send odds-history-NBA-%SEASON%.json to Claude.
echo ---------------------------------------------------------------
pause
