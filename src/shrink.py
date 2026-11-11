"""Shrink one wallet's record toward what the population of wallets looks like.

A wallet picked off a leaderboard is picked because its record looks good, and part of
any good-looking record is luck, so the top of a board over-states itself (the winner's
curse). The bars in hl_wallet answer "could this be luck?" with a yes or no. This module
answers "given how skill is spread across all wallets, what is this one's edge most likely
to be?" by empirical Bayes.

Model. For wallet i with a record of y_i years, the site's score gives z_i (t on the
normal scale). Treat z_i ~ Normal(s_i * sqrt(y_i), 1), where s_i is the wallet's true
annual Sharpe. The spread of s across wallets, g, is estimated from a random sample of
wallets by nonparametric maximum likelihood on a fixed grid (EM, Jiang & Zhang 2009;
Koenker & Mizera 2014), with no shape assumed. Each wallet's posterior over s is then
g times its own likelihood. Records of different length are handled by the likelihood,
which Tweedie's formula (one noise level for every unit) does not.

What this does not handle. Wallets trade the same markets in the same weeks, so their
returns are correlated. The estimate of g stays usable under that, but the posterior
treats each wallet's noise as its own, so its intervals are likely too narrow. Callers
should say so next to any interval.

Standard library only, like the rest of the package.
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional, Sequence, Tuple

GRID_LO, GRID_HI, GRID_STEP = -6.0, 6.0, 0.1
_N = statistics.NormalDist()


def grid(lo: float = GRID_LO, hi: float = GRID_HI, step: float = GRID_STEP) -> List[float]:
    n = int(round((hi - lo) / step))
    return [lo + k * step for k in range(n + 1)]


def _lik_row(z: float, years: float, g: Sequence[float]) -> List[float]:
    r = math.sqrt(years)
    return [math.exp(-0.5 * (z - s * r) ** 2) for s in g]


def fit_prior(obs: Sequence[Tuple[float, float]], g: Optional[Sequence[float]] = None,
              iters: int = 500, tol: float = 1e-7) -> Dict[str, Any]:
    """NPMLE of the spread of true annual Sharpe across wallets.

    obs: (z, years) per wallet. Returns {"grid", "weights", "iters", "loglik", "n"}.
    EM on fixed support: w_k <- mean_i( L_ik w_k / sum_j L_ij w_j ). Converges to the
    NPMLE restricted to the grid; stops when the log-likelihood gains less than tol per wallet.
    """
    g = list(g) if g is not None else grid()
    obs = [(float(z), float(y)) for z, y in obs if z is not None and y and y > 0]
    if not obs:
        raise ValueError("no usable observations")
    L = [_lik_row(z, y, g) for z, y in obs]
    m = len(g)
    w = [1.0 / m] * m
    prev = -math.inf
    ll = prev
    for it in range(1, iters + 1):
        acc = [0.0] * m
        ll = 0.0
        for row in L:
            d = sum(map(float.__mul__, row, w))
            if d <= 0:
                continue
            ll += math.log(d)
            inv = 1.0 / d
            acc = list(map(lambda a, b: a + b * inv, acc, row))
        w = [w[k] * acc[k] / len(L) for k in range(m)]
        if (ll - prev) / len(L) < tol:
            break
        prev = ll
    return {"grid": g, "weights": w, "iters": it, "loglik": ll, "n": len(obs)}


def posterior(z: float, years: float, prior: Dict[str, Any], level: float = 0.9) -> Dict[str, Any]:
    """Posterior of one wallet's true annual Sharpe under the fitted prior.

    Returns the raw estimate (z / sqrt(years)), the posterior mean, a central interval at
    `level`, P(s > 0), and `shrunk`: the share of the raw estimate removed (1 - mean / raw),
    which is what a reader most needs ("this record claims X, about Y of it is believable").
    """
    g, w = prior["grid"], prior["weights"]
    raw = z / math.sqrt(years)
    post = [a * b for a, b in zip(_lik_row(z, years, g), w)]
    tot = sum(post)
    if tot <= 0:
        return {"raw": round(raw, 4), "mean": None}
    post = [p / tot for p in post]
    mean = sum(s * p for s, p in zip(g, post))
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    lo = hi = None
    c = 0.0
    for s, p in zip(g, post):
        c += p
        if lo is None and c >= lo_q:
            lo = s
        if hi is None and c >= hi_q:
            hi = s
            break
    p_pos = sum(p for s, p in zip(g, post) if s > 0)
    return {"raw": round(raw, 4), "mean": round(mean, 4), "lo": round(lo, 4), "hi": round(hi, 4),
            "level": level, "p_positive": round(p_pos, 4),
            "shrunk": (round(1 - mean / raw, 4) if raw != 0 else None)}


def prior_summary(prior: Dict[str, Any]) -> Dict[str, Any]:
    """Mean, spread and a few quantiles of the fitted spread of skill."""
    g, w = prior["grid"], prior["weights"]
    mean = sum(s * p for s, p in zip(g, w))
    sd = math.sqrt(max(sum((s - mean) ** 2 * p for s, p in zip(g, w)), 0.0))
    q = {}
    c = 0.0
    targets = [0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
    ti = 0
    for s, p in zip(g, w):
        c += p
        while ti < len(targets) and c >= targets[ti]:
            q["q%02d" % int(targets[ti] * 100)] = round(s, 3)
            ti += 1
    return {"mean": round(mean, 4), "sd": round(sd, 4), "p_positive": round(sum(p for s, p in zip(g, w) if s > 0), 4),
            **q, "n": prior["n"], "iters": prior["iters"]}


def predictive(z: float, years: float, prior: Dict[str, Any], years_after: float,
               level: float = 0.9) -> Dict[str, Any]:
    """Where this wallet's score over a later, separate stretch of `years_after` years should land.

    z_after ~ Normal(s * sqrt(years_after), 1) with s drawn from this wallet's posterior.
    Returns the mean and a central interval at `level` (by bisection on the mixture CDF).
    """
    g, w = prior["grid"], prior["weights"]
    post = [a * b for a, b in zip(_lik_row(z, years, g), w)]
    tot = sum(post)
    post = [p / tot for p in post]
    r = math.sqrt(years_after)
    centres = [s * r for s in g]
    nd = _N

    def cdf(x):
        return sum(p * nd.cdf(x - c) for p, c in zip(post, centres) if p > 1e-12)

    def quant(q):
        lo, hi = min(centres) - 8, max(centres) + 8
        for _ in range(80):
            mid = (lo + hi) / 2
            if cdf(mid) < q:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    return {"mean": round(sum(p * c for p, c in zip(post, centres)), 4),
            "lo": round(quant((1 - level) / 2), 4), "hi": round(quant(1 - (1 - level) / 2), 4), "level": level}
