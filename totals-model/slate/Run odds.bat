@echo off
rem Double-click after the slate: today's lines, prices, openers, Pinnacle's
rem sharp line, the alternate and team totals and every book's price from
rem The Odds API, into odds-DATE.json. Needs odds_key.txt beside slate.py
rem (your key, one line). The first book in --books is the one carded; the
rem rest are shopped for the best price; pinnacle is read beside the carded
rem line and never carded. The last line printed is the credits used and left.
cd /d "%~dp0"
python slate.py odds --books fanatics,betmgm,draftkings,fanduel,caesars,espnbet,betrivers,pinnacle %*
echo.
echo ---------------------------------------------------------------
echo Done. In Call Sheet 3.0: Saving, Load slate, pick the odds file.
echo Blank line boxes fill; anything you typed stays. The rail shows the
echo sharp line, the alternates with their edge, and the book's split.
echo ---------------------------------------------------------------
pause
