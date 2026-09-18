"""Turning a projected total into over/under/push probabilities.

Two shapes are used:

* Baseball scoring is discrete, right-skewed and over-dispersed relative to a
  Poisson (a team that averages 4.4 runs has a variance closer to 9). A negative
  binomial per team, convolved, matches that well.
* Basketball scoring is high-frequency enough that the game total is very close
  to normal, so we use a normal with an empirical standard deviation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TotalProbs:
    p_over: float
    p_under: float
    p_push: float


# --------------------------------------------------------------------------
# Discrete (baseball)
# --------------------------------------------------------------------------


def negative_binomial_pmf(mean: float, dispersion: float, kmax: int = 30) -> list[float]:
    """PMF over 0..kmax for a negative binomial with the given mean.

    ``dispersion`` is the NB ``r`` parameter: variance = mean + mean**2 / r.
    Smaller r means a fatter tail. r = 4 reproduces MLB's observed team
    runs-per-game spread (mean ~4.4, sd ~3.0).
    """
    if mean <= 0:
        raise ValueError("mean must be positive")
    if dispersion <= 0:
        raise ValueError("dispersion must be positive")

    r = dispersion
    p = r / (r + mean)  # P(success); mean = r(1-p)/p
    log_p = math.log(p)
    log_q = math.log1p(-p)

    pmf = []
    for k in range(kmax + 1):
        log_pmf = (
            math.lgamma(k + r)
            - math.lgamma(r)
            - math.lgamma(k + 1)
            + r * log_p
            + k * log_q
        )
        pmf.append(math.exp(log_pmf))

    # Dump the truncated tail into the last bucket so it still sums to 1.
    leftover = 1.0 - sum(pmf)
    pmf[-1] += max(leftover, 0.0)
    return pmf


def convolve(a: list[float], b: list[float]) -> list[float]:
    """Distribution of the sum of two independent scores."""
    out = [0.0] * (len(a) + len(b) - 1)
    for i, pa in enumerate(a):
        if pa == 0.0:
            continue
        for j, pb in enumerate(b):
            out[i + j] += pa * pb
    return out


def discrete_total_probs(pmf: list[float], line: float) -> TotalProbs:
    """Over/under/push for a discrete total distribution.

    A whole-number line (8.0) can push; a half line (8.5) cannot.
    """
    p_push = 0.0
    p_over = 0.0
    p_under = 0.0
    for total, prob in enumerate(pmf):
        if total > line:
            p_over += prob
        elif total < line:
            p_under += prob
        else:
            p_push += prob
    return TotalProbs(p_over, p_under, p_push)


# --------------------------------------------------------------------------
# Continuous (basketball)
# --------------------------------------------------------------------------


def normal_cdf(x: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))


def normal_pdf(x: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    z = (x - mu) / sigma
    return math.exp(-0.5 * z * z) / (sigma * math.sqrt(2.0 * math.pi))


def normal_total_probs(mu: float, sigma: float, line: float) -> TotalProbs:
    """Over/under/push, treating the (integer) final total as a normal.

    A whole-number line gets a continuity correction so the push probability is
    the mass in [line - 0.5, line + 0.5] rather than zero.
    """
    is_whole = abs(line - round(line)) < 1e-9
    if is_whole:
        p_push = normal_cdf(line + 0.5, mu, sigma) - normal_cdf(line - 0.5, mu, sigma)
        p_under = normal_cdf(line - 0.5, mu, sigma)
        p_over = 1.0 - p_under - p_push
    else:
        p_under = normal_cdf(line, mu, sigma)
        p_over = 1.0 - p_under
        p_push = 0.0
    return TotalProbs(p_over, p_under, p_push)
