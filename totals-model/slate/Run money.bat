@echo off
rem Double-click any time, as often as you like: DraftKings' own count of the
rem bets and the money on today's NBA games. Free: no key, no credit. It adds
rem the count to splits-log.json and writes splits-DATE.json (today's date)
rem for the sheet. The odds run does the same by itself; this one refreshes
rem the count between odds runs.
cd /d "%~dp0"
python slate.py splits --sports NBA %*
echo.
echo ---------------------------------------------------------------
echo Done. In The Super Model: Saving, Load slate, pick the splits file
echo with today's date. The count is kept on each game and counted on the
echo NBA record. The box came off the game's card on 27 Nov 2026 (the side
echo with the larger bets had lost more than it won), so this run is optional.
echo ---------------------------------------------------------------
pause
