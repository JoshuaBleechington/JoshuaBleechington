"""A small, dependency-free totals model for MLB runs and WNBA points."""

from .core import (
    DEFAULT_MAX_STAKE_PCT,
    DEFAULT_MIN_STAKE_PCT,
    DEFAULT_MODEL_WEIGHT,
    Market,
    Projection,
    evaluate,
)
from . import mlb, wnba

__all__ = [
    "Market",
    "Projection",
    "evaluate",
    "mlb",
    "wnba",
    "run_game",
    "run_slate",
    "DEFAULT_MODEL_WEIGHT",
    "DEFAULT_MAX_STAKE_PCT",
    "DEFAULT_MIN_STAKE_PCT",
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
    )


def run_slate(
    sport: str,
    games: list[dict],
    kelly_multiplier: float = 0.25,
    model_weight: float = DEFAULT_MODEL_WEIGHT,
    max_stake_pct: float = DEFAULT_MAX_STAKE_PCT,
    min_stake_pct: float = DEFAULT_MIN_STAKE_PCT,
) -> list[dict]:
    """Project a list of games, best edge first."""
    results = [
        run_game(sport, g, kelly_multiplier, model_weight, max_stake_pct, min_stake_pct)
        for g in games
    ]
    results.sort(key=lambda r: r.get("ev_per_unit", float("-inf")), reverse=True)
    return results
