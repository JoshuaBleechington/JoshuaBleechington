"""A small, dependency-free totals model for MLB runs and WNBA points."""

from .core import (
    DEFAULT_MAX_STAKE_PCT,
    DEFAULT_MIN_STAKE_PCT,
    DEFAULT_MODEL_WEIGHT,
    DEFAULT_SIDES,
    Market,
    Projection,
    evaluate,
)
from . import confidence, mlb, wnba

__all__ = [
    "Market",
    "Projection",
    "evaluate",
    "confidence",
    "mlb",
    "wnba",
    "run_verdict",
    "run_verdict_slate",
    "run_game",
    "run_slate",
    "DEFAULT_MODEL_WEIGHT",
    "DEFAULT_MAX_STAKE_PCT",
    "DEFAULT_MIN_STAKE_PCT",
    "DEFAULT_SIDES",
]

__version__ = "1.0.0"

_MODELS = {"mlb": mlb, "wnba": wnba}


def run_game(
    sport: str,
    game: dict,
    kelly_multiplier: float = 0.25,
    model_weight: float = DEFAULT_MODEL_WEIGHT,
    max_stake_pct: float = DEFAULT_MAX_STAKE_PCT,
    min_stake_pct: float = DEFAULT_MIN_STAKE_PCT,
    sides: str = DEFAULT_SIDES,
) -> dict:
    """Project one game and, if a market is attached, grade it."""
    key = sport.lower()
    if key not in _MODELS:
        raise ValueError(f"Unknown sport {sport!r}; expected one of {sorted(_MODELS)}")
    projection = _MODELS[key].project(game)
    return evaluate(
        projection,
        Market.from_dict(game.get("market")),
        kelly_multiplier=kelly_multiplier,
        model_weight=model_weight,
        max_stake_pct=max_stake_pct,
        min_stake_pct=min_stake_pct,
        sides=sides,
    )


def run_slate(
    sport: str,
    games: list[dict],
    kelly_multiplier: float = 0.25,
    model_weight: float = DEFAULT_MODEL_WEIGHT,
    max_stake_pct: float = DEFAULT_MAX_STAKE_PCT,
    min_stake_pct: float = DEFAULT_MIN_STAKE_PCT,
    sides: str = DEFAULT_SIDES,
) -> list[dict]:
    """Project a list of games, best edge first."""
    results = [
        run_game(sport, g, kelly_multiplier, model_weight, max_stake_pct,
                 min_stake_pct, sides)
        for g in games
    ]
    results.sort(key=lambda r: r.get("ev_per_unit", float("-inf")), reverse=True)
    return results


def run_verdict(sport: str, game: dict) -> dict:
    """The confidence read: which side, and how sure, with no price involved.

    A separate question from ``run_game`` -- not a replacement. This one wants
    only a posted total, and answers on a High / Medium / Low scale.

    A team's own park factor is ignored here by design; only the venue being
    played in adjusts the total.
    """
    key = sport.lower()
    if key not in _MODELS:
        raise ValueError(f"Unknown sport {sport!r}; expected one of {sorted(_MODELS)}")
    if "line" not in game:
        raise ValueError("A posted total is required: set 'line'.")

    payload = dict(game)
    if key == "mlb":
        for side in ("away", "home"):
            team = dict(payload.get(side) or {})
            team.pop("own_park_factor", None)
            payload[side] = team

    projection = _MODELS[key].project(payload)
    return confidence.decide(key.upper(), projection, payload).to_dict()


def run_verdict_slate(sport: str, games: list[dict]) -> list[dict]:
    """Grade a slate, strongest read first."""
    # Derived from confidence.BANDS rather than hand-listed, so adding a band
    # there (LEAN was) can't silently leave this ranking one step behind.
    order = {b: i for i, b in enumerate(confidence.BANDS)}
    results = [run_verdict(sport, g) for g in games]
    results.sort(key=lambda r: (order[r["band"]], r["win_pct"]), reverse=True)
    return results
