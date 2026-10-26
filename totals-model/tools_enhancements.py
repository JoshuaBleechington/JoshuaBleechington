#!/usr/bin/env python3
"""The enhancements to date, as one page to print (25 Oct 2026, the user: "I
want a PDF of all the enhancements we did to the model to date so I can
track. Use color for the most impactful enhancements too").

Writes an HTML page; a browser prints it to PDF (tools_enhancements_pdf.js
does it with the pre-installed Playwright). Every entry is a commit or a
group of commits on the branch, dated by the commit, with what it changed
in a sentence and what kind of change it was:

  edge   changed what the sheet bets, and was measured before it shipped
  guard  protects the record or the data: grading, the close, storage, a
         feed left alone, an input measured null and kept off the score
  show   context shown beside the call, never scored, and the tools around
         the page: the slate, the feeds, the cards
  fix    housekeeping, a fix, docs

Usage: python3 tools_enhancements.py [out.html]
"""
from __future__ import annotations

import html
import sys

TIERS = {
    "edge": ("Scored and measured", "Changed what the sheet bets; measured on past seasons or the logged games before it shipped"),
    "guard": ("Protects the record", "Grading, the close, storage, a feed left alone, or an input measured null and kept off the score"),
    "show": ("Shown, not scored", "Context beside the call, and the tools that fill the page: the slate, the feeds, the cards"),
    "fix": ("Housekeeping", "A fix, a rename, docs"),
}

# The most impactful, in the order they matter tonight. Each names an entry below by its key.
TOP = [
    ("gap-rule", "The one inefficiency the period lines carried, scored over two seasons"),
    ("props-median", "The props' chance read around the median: the re-scored record went from 423-406 to 452-377"),
    ("props", "Every player prop the books post, projected from the ledgers and measured on 2025-26"),
    ("sim", "A possession-level game played 10,000 times, honest about what its confidence is worth"),
    ("indexeddb", "The page's memory had hit localStorage's wall and saves were failing silently"),
    ("short-dog", "The short dog: 5.6 points more than the NBA moneyline prices, both seasons, scored"),
    ("upset", "A dog starting its backup goalie: seven points more than priced, scored"),
    ("nhl-backtest", "The hockey constants measured on 2,624 games and tested on two seasons of closes"),
    ("nba-backtest", "The basketball engine built from two seasons of closes, with only what the backtest supports"),
    ("cs2", "Call Sheet 2.0: every market on a matchup ranked by edge, the parlay four, the board"),
    ("close-guard", "An in-play line was being graded as the close; the grade now passes over a snapshot taken after tip"),
    ("median-line", "The posted line is a median, not a mean: the first correction that made the chance honest"),
    ("take", "The bets you actually place, marked on the page and graded on their own line: the record of you, not only of the sheet"),
    ("tt-own", "The card's confidence now means what the replay found, not what the sim says: a 71% worth a coin reads as a coin"),
]

# (key, date, area, title, what it did, tier)
ENTRIES = [
    # ---- August 2026: the totals model ----
    ("totals", "2026-08-04", "MLB · WNBA", "The totals model: MLB runs and WNBA points, with the browser calculator",
     "A projection of the game total from team and pitching inputs against the posted line, and a page to type it into.", "edge"),
    ("over-bias", "2026-08-05", "MLB", "The over-bias from a stale league constant fixed",
     "Every MLB projection had leaned over; the league constant was a season old.", "edge"),
    ("clv", "2026-08-05", "Record", "A track record with closing line value",
     "Every logged game graded against the close as well as the result, so a good call that lost still counts.", "guard"),
    ("era-regress", "2026-08-05", "MLB", "Starter ERA regressed toward the league by sample size",
     "A pitcher's few starts no longer read as his true level.", "edge"),
    ("storage-1", "2026-08-07", "Page", "Storage that fails is caught",
     "The track record was being lost silently when the browser blocked storage, or when storage worked but did not survive a reload.", "guard"),
    ("same-outcomes", "2026-08-07", "Record", "The model and the market compared on the same set of outcomes",
     "The record compares like with like, so a market record on more games cannot flatter or hide the model.", "guard"),
    ("median-line", "2026-08-10", "MLB · WNBA", "The posted line is a median, not a mean",
     "Run and point totals skew right; reading the line as the mean overstated the over. The chance is read around the median.", "edge"),
    ("moved-it", "2026-08-10", "Page", "What moved the projection, and why it is a bet",
     "Each input's push on the projection shown beside the call, so the number can be argued with.", "show"),
    ("calib", "2026-08-11", "Record", "The calibration view: is the model's confidence honest?",
     "The chance the model said against how often it happened, by band, on every logged game.", "guard"),
    ("floor", "2026-08-11", "MLB · WNBA", "A floor under a recommendation, not just a ceiling",
     "A read below a measured floor no longer earns a bet band.", "edge"),
    ("wnba-level", "2026-08-12", "WNBA", "The WNBA level calibrated against the market",
     "The league baseline set from the market's own totals, and the page says when the cap bites.", "edge"),
    ("verdict", "2026-08-13", "MLB · WNBA", "The verdict model: which side, and how sure, with no price involved",
     "A call on every game from the sheet's own information, graded apart from the bets.", "edge"),
    ("form-h2h", "2026-08-17", "MLB · WNBA", "Recent form weighted over head to head",
     "Head to head discounted by how many meetings it rests on; form carries more.", "edge"),
    ("bands-graded", "2026-08-17", "Record", "The bands graded on every logged game, not just the backed ones",
     "A band's record counts the games it would have called, bet or not.", "guard"),
    ("lean", "2026-08-19", "Page", "LEAN: a demoted read gets a name instead of going silent",
     "Every call has a band, so the record can grade the weak ones too.", "show"),
    ("wnba-spread", "2026-08-20", "WNBA · MLB", "The WNBA moved to the spread; MLB back on season pitching",
     "Each sport on the market its inputs predicted; the thin-sample flag came back with the season numbers.", "edge"),
    ("retire-mlb", "2026-08-23", "MLB", "The MLB totals verdict retired; the late-factor and game-day models",
     "The totals verdict failed its own record and was retired in writing; a model that decides whether to bet, not what the score is, replaced it.", "edge"),
    ("umpire", "2026-08-24", "MLB", "The umpire input rebuilt, then taken off the page",
     "The umpire's record did not earn its place; the gate it exposed was fixed.", "guard"),
    ("forecaster", "2026-08-25", "MLB · WNBA", "The forecaster: MLB first five and WNBA, a call on every card",
     "Every game gets a call with its why, and a verification section that counts itself.", "edge"),
    ("backup-file", "2026-08-25", "Page", "The half-typed form is kept, and a backup file offered",
     "Nothing typed is lost to a reload; the card can be saved and restored.", "guard"),
    # ---- September 2026: the full game, Call Sheet 2.0 and the slate ----
    ("fullgame", "2026-09-02", "MLB", "The full game rebuilt as a distribution rather than a mean",
     "The chance of every number comes from the shape of the scoring, not one projection against the line.", "edge"),
    ("wide-anchor", "2026-09-04", "MLB", "The anchor pulled back when the market is unusually wide; the domed games marked",
     "A wide market says less; the sheet leans on it less.", "edge"),
    ("by-band", "2026-09-04", "Record", "The record broken down band by band; a measured-null input cannot buy a band",
     "Each band's own record sits next to the band, and an input the tests found null cannot raise a call.", "guard"),
    ("rescore", "2026-09-05", "Page", "A card rescored against the current model",
     "A logged card can be re-read with today's engine and the difference seen.", "show"),
    ("bet-or-no", "2026-09-07", "MLB · WNBA", "Bet or no bet, with what the price already demands",
     "The break-even chance of the price beside the model's chance; the gap is the edge.", "edge"),
    ("nfl", "2026-09-13", "NFL", "NFL spreads tried, then swapped back for a WNBA totals book",
     "The NFL book did not hold; the WNBA totals came back with constants off the table its inputs come from.", "fix"),
    ("era-innings", "2026-09-16", "MLB", "Starter ERA weighed by the innings behind it; the alternate ladder priced off the main line",
     "A pitcher's number carries his workload; every alternate number gets a chance from the same distribution.", "edge"),
    ("likelihood", "2026-09-20", "Page", "Lead with the likelihood; the money split shown, not scored; the projection the over needs",
     "The sheet says the chance first and the verdict second, and names what it will not score.", "show"),
    ("wind-axis", "2026-09-22", "MLB", "Only the wind along the home-to-centre axis is scored; the build date stamped on the page",
     "A crosswind no longer moves the total; a cached old page is obvious.", "edge"),
    ("cs2", "2026-09-23", "Page", "Call Sheet 2.0: every market on a matchup ranked by edge, the parlay four, the board",
     "One matchup gives every market a chance and a price; the rail ranks them, the parlay four takes the likeliest legs, the board lists the night.", "edge"),
    ("rail-locks", "2026-09-23", "Record", "A graded row grades the rail and locks",
     "Once the final is in, the row is a record and cannot be edited.", "guard"),
    ("record-tiles", "2026-09-24", "Record", "Is it working split by sport; the record tiles show each market by side; the labels",
     "The cold-under profile, same or split lean, and over-against-the-grain labels, each with its own line in the record.", "show"),
    ("wnba-16", "2026-09-25", "WNBA", "The WNBA total's spread 11.5 to 16, measured on the first fourteen games",
     "The season's own scatter set the sigma; the bands moved with it.", "edge"),
    ("starters-shown", "2026-09-26", "MLB", "The starters shown, not scored, in the full game; the moneyline and run line shown, not picked",
     "What the backtest did not support came off the score and stayed on the card.", "guard"),
    ("slate", "2026-09-28", "Slate", "The slate: MLB inputs and finals fetched on your own computer, double-click bat files, the slate loader",
     "The night's inputs and the morning's finals come from a script run at home and load in one click; the last five starts ride along.", "show"),
    ("one-row", "2026-09-29", "Record", "One row per matchup per date",
     "A game cannot be logged twice; a second load updates the row instead.", "guard"),
    ("close", "2026-09-30", "Record", "The closing line on the record",
     "Every graded game carries the close it was bet into.", "guard"),
    # ---- October 1-14: the hockey book, Call Sheet 3.0, the odds feed, the pick ----
    ("nhl", "2026-10-01", "NHL", "The NHL total and its markets, built a week before the season; the slate's NHL mode",
     "Scoring rates, goalies and the first period on one card, with the slate filling it.", "edge"),
    ("cs3", "2026-10-01", "Page", "Call Sheet 3.0: MLB, NHL and WNBA on one page",
     "One page derived from 2.0 at build time, with a harness that checks every case before it ships.", "show"),
    ("wnba-sides", "2026-10-02", "WNBA", "The WNBA sides carry the ratings and are picked; the cheaper side a tracked rule",
     "The spread and the moneyline get the same read; the cheaper-side rule is tracked rather than trusted.", "edge"),
    ("nhl-anchor", "2026-10-04", "NHL", "The first-period anchor reads its prices straight; the league save percentage measured at .898",
     "The wide-hold regression was dropped; the constant came from the data.", "edge"),
    ("ledger", "2026-10-05", "Slate", "The league ledger: every final, the first period's own last ten; recent form and the crowd on the hockey card",
     "A file of every game, kept up to date by the slate, that every measurement since has run on.", "show"),
    ("xg", "2026-10-06", "NHL · MLB", "Expected goals from MoneyPuck; park factors from a file",
     "Two inputs the slate fills from the web; expected goals were later measured null and kept shown.", "show"),
    ("nhl-backtest", "2026-10-07", "NHL", "The hockey constants measured on 2,624 games; the backtest against two seasons of closes",
     "Shots out, form at 0.6, the October delta tried and later retired; every input on the card earned its weight on the closes.", "edge"),
    ("goalies", "2026-10-07", "NHL", "Goalies measured at 1.6 and scored only with two regular starters; a cold backup takes the bigger delta",
     "The goalie is the one hockey input that moves the total; the rule says when it may.", "edge"),
    ("nhl-null", "2026-10-07", "NHL", "Measured null and kept off the score: head to head, special teams, expected goals, schedule spots, referee crews",
     "Each was tested against the closes, found to carry nothing, and left shown beside the call.", "guard"),
    ("goalie-picker", "2026-10-11", "NHL", "The goalie picker, and the grade records who actually started",
     "The record can split on whether the carded goalie played.", "guard"),
    ("forecast-line", "2026-10-11", "Record", "The forecast line and its scorecard",
     "What the sheet expects, betting aside, graded on its own.", "show"),
    ("nhl-week", "2026-10-12", "NHL", "Hockey: the full-game total alone for a week, a call on every game with its why",
     "The period market became a second read; the call it likes most gets a colour.", "edge"),
    ("odds", "2026-10-12", "Slate", "The odds feed: The Odds API fills lines, prices, the opener, the shop and the close; the sharp line, the alternates, the history",
     "Every line on the card comes from the feed, the last run before tip is the close, and the history mode replays past seasons.", "show"),
    ("pick", "2026-10-12", "Page", "The pick: one side per matchup, the likeliest on the board, with its kind of game and its why",
     "Measured first: nothing on the hockey sheet picks a winner better than the moneyline, so the pick comes from the sheet's own information and says so.", "edge"),
    ("sides-cal", "2026-10-13", "NHL", "The sides calibrated: the moneyline was right, the puck line's margin model measured; parity in the goal distribution; Pinnacle's shade a recorded rule",
     "The odds history replayed; what held is scored, what did not is a rule the record tracks.", "edge"),
    ("nhl-null-2", "2026-10-13", "NHL", "Scoring rates faded; a goalie on consecutive nights null; empty-net habits tagged; travel null; the backup rule's anatomy watched",
     "More inputs tested and placed: faded, tagged, or watched.", "guard"),
    ("gsax", "2026-10-14", "NHL", "Goals saved above expected weaker than the raw line; time-decayed form beats nothing",
     "Two refinements tried against the flat versions and not adopted.", "guard"),
    ("context", "2026-10-14", "Page", "Colour in the record section; the context card with each club's league ranks and what the sheet did with each fact",
     "Every context line says scored, tagged or shown.", "show"),
    # ---- October 15-18: the basketball book ----
    ("nba-ledger", "2026-10-15", "NBA", "The NBA ledger: every final with quarters, pace, every player's minutes, tip time and the crew, read from ESPN",
     "Three seasons of games the backtest, the props and the simulation all run on.", "show"),
    ("nba-backtest", "2026-10-15", "NBA", "The NBA backtest: two seasons of closes against the ledger's inputs; the engine carries only what the backtest supports",
     "Ratings, pace, rest and the stage of the season; the rest shown.", "edge"),
    ("nba-slate", "2026-10-15", "NBA", "The NBA slate: ratings, rest, who is out by player id, the context lines, the grade run, the side watch",
     "The who-is-out list reads each man's own line by his id, so a traded player is never read against the wrong club.", "show"),
    ("super-model", "2026-10-15", "Page", "The page is The Super Model",
     "The user's name for Call Sheet 3.0, on the eve of the basketball book.", "fix"),
    ("crew", "2026-10-15", "NBA", "The crew on the context card: the day's assignments from the league's feed, each referee's line from three seasons of ledgers",
     "Shown, not scored: crews predict the night's free throws and the total does not follow.", "show"),
    ("likeliest", "2026-10-15", "Page", "The likeliest side at any price: its own card, a mark on its row, the board's six two-leg parlays, all graded",
     "The board lists the likeliest side in each game and builds parlays from them; the record keeps them as built.", "edge"),
    ("ref-close", "2026-10-16", "NBA", "Each referee against the close on the crew line; this season graded from the odds log",
     "Two backtest seasons shipped in the slate, this one filling night by night.", "show"),
    ("upset", "2026-10-16", "NHL", "The upset signal: a dog starting its backup goalie wins seven points more than the market prices, scored",
     "The one hockey side that beat the moneyline; the upset watch names the rest.", "edge"),
    ("short-dog", "2026-10-16", "NBA", "The short dog: a dog the book makes 40% or better wins 5.6 points more than the NBA moneyline prices, both seasons; scored and pickable",
     "On the record from the first night.", "edge"),
    ("void", "2026-10-17", "Page", "A void button for a postponed game; the saved file named for The Super Model",
     "A postponed game leaves the record cleanly.", "guard"),
    # ---- October 19-24: player props, lineups, the watches ----
    ("props", "2026-10-19", "NBA props", "Player props: the ledger keeps every box line, the slate projects each prop, The Super Model gets a Props tab",
     "Rate times minutes, the regulars out, pace and the defence by position, each measured on 2025-26 before it shipped; every book's line kept.", "edge"),
    ("goalies-live", "2026-10-19", "NHL", "Tonight's goalies from RotoWire and CBS; a confirmed start ticks the box",
     "The slate reads the goalie news so the card does not wait on it.", "show"),
    ("alt-verdict", "2026-10-19", "Page", "The alternate total with a verdict; the parlay four from the likelier side",
     "An alternate number can carry its own band and join the record.", "edge"),
    ("lineups", "2026-10-20", "NBA", "The starting five from RotoWire on the NBA card; each last game's stat marked against the prop's line",
     "Expected or confirmed, with the men who may not play under it; a later slate replaces it.", "show"),
    ("prop-panel", "2026-10-21", "NBA props", "The prop's own panel with what moves it; a table row opens it; sort and filter by any column",
     "Every factor's push on the projection ranked with a bar, the two biggest named on the card.", "show"),
    ("props-median", "2026-10-22", "NBA props", "The blowout test, and the props' chance read around the median",
     "The mean shifted down a measured fraction of a sigma per market; re-scoring the first two nights' 829 props read 452-377 against 423-406 as shipped. Trimming minutes for a blowout made it worse and was not adopted.", "edge"),
    ("watches", "2026-10-22", "Page", "The Props tab's own Is it working block; the referees as a watch; recent form on the NBA card; the Referee stats card with a crew call",
     "In colour, each a record of its own; the referee lean is a watch until the season repeats it.", "show"),
    ("lineup-refresh", "2026-10-23", "Page", "A later slate refreshes the starting five on a carded row; the props run says which ledger it read",
     "The newest lineup wins; a run without last season's games says so on the page.", "guard"),
    ("started", "2026-10-23", "Slate", "A game already under way is left alone by the odds and props runs",
     "An in-play line can no longer overwrite the pre-tip numbers on the card.", "guard"),
    ("close-guard", "2026-10-24", "Record", "The grade passes over an odds snapshot taken after tip",
     "An in-play total had been graded as the close on one game; the close is now the last snapshot before tip, and the grade files were regenerated.", "guard"),
    # ---- October 25: storage, the simulation, the period lines ----
    ("indexeddb", "2026-10-25", "Page", "The page's memory moves to IndexedDB",
     "The card, the props and the slate had outgrown localStorage's 10 MB and saves were failing silently; a failed save now shows on the page.", "guard"),
    ("topup", "2026-10-25", "Slate", "The ledger is brought up to date inside the slate and props runs; a run without last season says so",
     "One click fewer each day, and a thin run is flagged rather than quietly worse.", "guard"),
    ("graded-night", "2026-10-25", "NBA props", "The graded night joins a prop's last games, with his minutes; a second grade load fills older props in",
     "The panel shows the game the call was made on, marked like the rest.", "show"),
    ("sim", "2026-10-25", "NBA", "The simulation: a possession-level engine from three seasons of play-by-play, the measured tendencies, 10,000 runs a game, the Simulation card and its says-against-does record",
     "Starters' share by quarter, fouling, the last minute, the bench gap and rest, each from the play-by-play; every market's chance read off the runs with the band and what it is worth.", "edge"),
    ("sim-cal", "2026-10-25", "NBA", "The simulation calibrated: its own total and spread carry nothing beyond the close; its win chances are nearly true",
     "The worth shown beside each call is the chance shrunk by what the replay found, so 70% means what it says.", "guard"),
    ("match-lever", "2026-10-25", "NBA props", "The props take a matchup lever from the simulation's profiles; the pace lever's form fixed",
     "The club's efficiency into tonight's defence, at the half weight that cut the miss; the pace lever no longer double-counts the club's own pace.", "edge"),
    ("gap-rule", "2026-10-25", "NBA", "The period lines pulled and replayed: the first half a coin, the quarters nothing, the team totals the one inefficiency; the gap rule scored",
     "A home team total a point or more above the implied number goes under 63% and 62% of the time, a point below over 63% and 68%, two seasons; on the Simulation card and in the record.", "edge"),
    ("sim-props", "2026-10-25", "NBA props", "The Simulation card restyled; the props run plays each game 10,000 times and attaches the runs to every prop; a later slate refreshes the injury report and the sim",
     "The prop's panel shows the club's points in the runs, the sim's read of his number, the matchup lever as the scored part, the blowout and overtime chances.", "show"),
    ("take", "2026-10-25", "Page", "The bets you take: a Take button on every market, pick card and prop; Taking tonight on the board; What you took in the record",
     "A click marks the bet as shown, with its side and price; the marked bets list at the top of the day board and the Props tab with a copy button, ride through reloads and rescores, and grade on their own tiles at one unit each. A graded row cannot be marked after the fact.", "guard"),
    ("take-sim", "2026-10-25", "NBA", "The simulation's calls can be taken too",
     "A Take button under every chip on the Simulation card and beside the gap rule's call, live once the game is on the card; the mark keeps the call as shown (line, price, chance, worth, band) and grades on a Simulation calls tile.", "guard"),
    ("runs", "2026-10-25", "NBA", "10,000 runs measured as the right count",
     "Twenty seeds a game at 1,000 to 50,000 runs against a 400,000-run reference: at 10,000 a chance wanders half a point, inside what the chip shows; 50,000 buys a decimal the page never prints at five times the time. A call within a point of a band edge flips at every count.", "guard"),
    ("rotowire", "2026-10-25", "Slate", "The injury report together with RotoWire's lineups page",
     "A man RotoWire marks Out joins ESPN's list with his id from the ledgers; a man ESPN has Out but RotoWire shows in a confirmed five is counted in. Runs in the slate and the props; on its first live night it found two men out that ESPN's report did not.", "guard"),
    ("levers", "2026-10-25", "NBA props", "The levers' tally: a Levers column, a filter for the props whose levers all lean the pick's way, the tag and the heading",
     "How many of What moves it's factors push toward the pick and how many against, sortable, filterable, on the card and the panel. Shown, not scored: it counts the pushes, the chance carries their sizes.", "show"),
    ("phone", "2026-10-25", "Page", "Tonight on your phone: a QR code that carries the night's picks to a read-only phone sheet",
     "The code holds the picks themselves, compressed into the link; nothing is uploaded. The bets marked Taking, the parlay four, the best bets, the likeliest sides, the best props and the simulation's calls, trimmed from the least important end on a long night. The harness decodes the drawn code with an independent reader.", "show"),
    ("lineup-test", "2026-10-26", "NBA", "The lineups test: five-man stints from the play-by-play, player impact ratings, and the club model kept",
     "2,481 games cut into stints (five a side in 99.99%, minutes within 0.26 of the box); adjusted plus-minus per player, refit weekly; the players matched the club model on margins, were worse in the first month, and nothing added to the close. A continuity-weighted prior gained one percent. The model stays.", "guard"),
    ("tt-own", "2026-10-26", "NBA", "The own view's team totals measured null on both seasons; the Simulation card's band now comes from the worth",
     "After a 71% own-view team total read STRONG and lost by seventeen: its 65-70% calls had landed 47% in both seasons, the anchored home total's 66-68%. The worth now splits by view and side, and every chip's band reads off its worth, so the card says which calls the replay backs.", "guard"),
    ("props-usage", "2026-10-26", "Props", "Usage and the role set the sigma: a star's chance reads sharper, a low-usage bench man's wider",
     "Measured on 2025-26 before it shipped: the over rate at the median is 50% in every usage bucket, so usage says nothing about the side, but the miss runs 0.93 sigmas at 24% and up against 1.13 under 18%, stable across the season's halves, and a starter's one sigma against a bench man's 1.17 to 1.25 at low usage (the user's Lakers starters at 8.5 and 5.5 points). The slate reads his usage and his role (RotoWire's five, else his last game) and scales the sigma; a Usage tile, a role tag and usage and role filters on the page.", "edge"),
    ("props-floors", "2026-10-26", "Props", "The floors: the number he clears 95, 90 and 80% of nights, and his 95% floors across his markets",
     "The user's alternate-line read (Sengun 10+ points, 5+ rebounds, 3+ assists at 95%). Measured: the model's 95% floor cleared 97.5% of nights, posted as a book's whole number 98%, and one man's three floors together 96.5% against 85.7% if independent, his minutes carrying all three. Shown on the panel, not priced: the books' alternate lines would be a second market a game on the feed.", "show"),
    ("props-pairs", "2026-10-26", "Props", "Same-game pairs: two props from one game as a ticket, the chance both land measured, graded on their own tile",
     "The user saw the night's quick winners were two-leg same-game parlays. The likeliest four legs a game at 52% or better, every pair a ticket: two players' props land almost as independence says (23.7% and 25.2% against 25%), a man's own two markets together more often (28 to 29%, his points with his threes 38%), so the product carries a measured factor, capped at the lesser leg; the parlay price, what it needs, whether the price agrees; graded from the first night and carried on the phone sheet.", "show"),
]

COLORS = {"edge": "#b4232c", "guard": "#c2700a", "show": "#1f5fa8", "fix": "#6b7280"}
SOFT = {"edge": "#fbe9ea", "guard": "#fdf1e0", "show": "#e6eef9", "fix": "#eef0f3"}


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def month_name(d: str) -> str:
    y, m, _ = d.split("-")
    return ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"][int(m)] + " " + y


def build() -> str:
    by_key = {e[0]: e for e in ENTRIES}
    assert len(by_key) == len(ENTRIES), "duplicate key"
    for k, _ in TOP:
        assert k in by_key, k
    counts = {t: sum(1 for e in ENTRIES if e[5] == t) for t in TIERS}
    css = """
  @page { size: Letter; margin: 14mm 13mm; }
  * { box-sizing: border-box; }
  body { font: 10.5pt/1.45 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1a1d23; margin: 0; }
  h1 { font-size: 22pt; margin: 0 0 2pt; letter-spacing: -.01em; }
  .sub { color: #5b6270; margin: 0 0 14pt; font-size: 10.5pt; }
  h2 { font-size: 13.5pt; margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 1.5pt solid #1a1d23; break-after: avoid; }
  .legend { display: grid; grid-template-columns: 1fr 1fr; gap: 6pt 10pt; margin: 0 0 12pt; }
  .leg { display: grid; grid-template-columns: 14pt 1fr; gap: 6pt; align-items: start; font-size: 9.5pt; }
  .leg .sw { width: 12pt; height: 12pt; border-radius: 3pt; margin-top: 2pt; }
  .leg b { display: block; font-size: 10pt; }
  .top { counter-reset: n; margin: 0; padding: 0; list-style: none; display: grid; grid-template-columns: 1fr 1fr; gap: 5pt 10pt; }
  .top li { counter-increment: n; display: grid; grid-template-columns: 16pt 1fr; gap: 6pt; padding: 6pt 8pt; border-radius: 5pt; border-left: 4pt solid; font-size: 9.6pt; break-inside: avoid; }
  .top li::before { content: counter(n); font-weight: 800; font-size: 12pt; color: inherit; }
  .top li b { display: block; font-size: 10pt; line-height: 1.3; }
  .top li span { color: #3b4250; }
  .ent { display: grid; grid-template-columns: 58pt 60pt 1fr; gap: 8pt; padding: 5pt 7pt; border-left: 4pt solid; margin: 0 0 4pt; border-radius: 0 4pt 4pt 0; break-inside: avoid; }
  .ent .d { font: 600 9pt/1.4 "SF Mono", Menlo, Consolas, monospace; color: #3b4250; }
  .ent .a { font-size: 9pt; color: #5b6270; line-height: 1.4; }
  .ent .t { font-weight: 700; font-size: 10.2pt; line-height: 1.3; }
  .ent .w { color: #3b4250; font-size: 9.6pt; margin-top: 1pt; }
  .ent .tags { margin: 0 0 2pt; }
  .ent .tag { display: inline-block; font: 700 7pt/1 inherit; letter-spacing: .06em; text-transform: uppercase; padding: 2pt 5pt; border-radius: 3pt; color: #fff; margin-right: 4pt; }
  .count { font-size: 9.5pt; color: #5b6270; margin: 0 0 10pt; }
  .null { columns: 2; column-gap: 14pt; font-size: 9.5pt; margin: 0; padding-left: 14pt; }
  .null li { margin: 0 0 3pt; break-inside: avoid; }
  .foot { margin-top: 16pt; font-size: 9pt; color: #5b6270; border-top: 1pt solid #d5d9e0; padding-top: 6pt; }
"""
    out = ['<!doctype html><html><head><meta charset="utf-8"><title>The Super Model: the enhancements to date</title><style>' + css + '</style></head><body>']
    out.append('<h1>The Super Model: the enhancements to date</h1>')
    out.append('<p class="sub">Every change to the model and the page from the first totals model on 4 August 2026 through 26 October 2026, dated by the commit that shipped it. '
               'The colour says what kind of change it was; the ones in the box are the ones that matter most to what is bet tonight.</p>')
    out.append('<div class="legend">' + "".join(
        '<div class="leg"><div class="sw" style="background:%s"></div><div><b>%s</b>%s · %d</div></div>' % (COLORS[t], TIERS[t][0], TIERS[t][1], counts[t]) for t in TIERS) + '</div>')
    out.append('<h2>The %s that matter most</h2>' % ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen"][len(TOP)])
    out.append('<ol class="top">' + "".join(
        '<li style="border-color:%s;background:%s;color:%s"><div><b>%s</b><span>%s</span></div></li>' % (COLORS[by_key[k][5]], SOFT[by_key[k][5]], COLORS[by_key[k][5]], esc(by_key[k][3]), esc(why))
        for k, why in TOP) + '</ol>')
    # the log, by month
    month = None
    for key, d, area, title, what, tier in ENTRIES:
        m = month_name(d)
        if m != month:
            month = m
            out.append('<h2>%s</h2>' % esc(m))
        top = any(k == key for k, _ in TOP)
        out.append('<div class="ent" style="border-color:%s;background:%s"><div class="d">%s</div><div class="a">%s</div><div><div class="tags"><span class="tag" style="background:%s">%s</span>%s</div><div class="t">%s</div><div class="w">%s</div></div></div>' % (
            COLORS[tier], SOFT[tier] if top else "#fff", esc(d[5:].replace("-", "/")), esc(area), COLORS[tier], esc(TIERS[tier][0]),
            '<span class="tag" style="background:#1a1d23">top %d</span>' % len(TOP) if top else "", esc(title), esc(what)))
    out.append('<h2>Measured and kept off the score</h2>')
    out.append('<p class="count">What the tests found carried nothing against the closes, and so stays shown beside the call rather than inside it. Each one is a line on the card that says so.</p>')
    out.append('<ul class="null">' + "".join('<li>%s</li>' % esc(x) for x in [
        "MLB: the umpire (taken off the page); the crosswind; the starters in the full game (shown); the moneyline and run line (shown, not picked)",
        "NHL: head to head; special teams; expected goals (MoneyPuck, and the backtest against Natural Stat Trick); schedule and travel spots; referee crews; a goalie on consecutive nights; goals saved above expected as the goalie prior; time-decayed form; the October delta (retired)",
        "NHL sides: nothing on the sheet picks a winner better than the moneyline, except the backup-goalie dog (scored)",
        "NBA: the referee crews on the total (they predict free throws, not points); a club's own over/under run within a season; a player's home and road split; HashtagBasketball's defence rank (shown beside the ledger's own, which is scored)",
        "NBA props: minutes trimmed for an expected blowout (the projection got worse out of sample); the market's implied team points beyond pace; the simulation at full weight on a prop (the defence counted twice)",
        "The simulation: its own total and spread against the close (slopes near zero, so the derivative markets are anchored to the market); the first-half total (a coin both seasons); the first and third quarters; Pinnacle's shade and the opener-to-close move on the period lines",
    ]) + '</ul>')
    out.append('<p class="foot">Generated by tools_enhancements.py from the branch\'s history; the detail behind each entry is in CALLSHEET2.md, CALLSHEET3.md, NBA.md, FINDINGS.md and slate/README.md. %d entries: %s.</p>' % (
        len(ENTRIES), ", ".join("%d %s" % (counts[t], TIERS[t][0].lower()) for t in TIERS)))
    out.append('</body></html>')
    return "\n".join(out)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "enhancements.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(build())
    print("wrote", path)
