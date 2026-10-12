@echo off
rem Double-click after the slate: today's lines, prices, openers and every
rem book's price from The Odds API, into odds-DATE.json. Needs odds_key.txt
rem beside slate.py (your key, one line). The first book in --books is the
rem one carded; the rest are shopped for the best price.
cd /d "%~dp0"
python slate.py odds --books fanatics,betmgm,draftkings,fanduel,caesars,espnbet,betrivers %*
echo.
echo ---------------------------------------------------------------
echo Done. In Call Sheet 3.0: Saving, Load slate, pick the odds file.
echo Blank line boxes fill; anything you typed stays.
echo ---------------------------------------------------------------
pause
