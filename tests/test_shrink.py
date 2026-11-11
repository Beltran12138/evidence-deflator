import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import shrink  # noqa: E402


def _sim(n, seed, true_sd=0.5, true_mean=0.0, years=(0.5, 4.0)):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        s = rnd.gauss(true_mean, true_sd)
        y = rnd.uniform(*years)
        out.append((s, y, rnd.gauss(s * math.sqrt(y), 1.0)))
    return out


def test_prior_recovers_normal_spread():
    data = _sim(800, 1)
    pr = shrink.fit_prior([(z, y) for _, y, z in data])
    sm = shrink.prior_summary(pr)
    assert abs(sm["mean"]) < 0.1
    assert 0.35 < sm["sd"] < 0.65


def test_posterior_matches_normal_normal_closed_form():
    # with a normal prior N(0, tau^2) the posterior mean is raw * (y tau^2) / (y tau^2 + 1)
    tau = 0.5
    g = shrink.grid()
    w = [math.exp(-0.5 * (s / tau) ** 2) for s in g]
    tot = sum(w)
    pr = {"grid": g, "weights": [x / tot for x in w], "n": 0, "iters": 0}
    z, y = 3.0, 2.0
    p = shrink.posterior(z, y, pr)
    raw = z / math.sqrt(y)
    want = raw * (y * tau ** 2) / (y * tau ** 2 + 1)
    assert abs(p["mean"] - want) < 1e-3
    assert abs(p["shrunk"] - (1 - want / raw)) < 1e-3
    assert p["lo"] < p["mean"] < p["hi"]


def test_shrinkage_cuts_winners_curse():
    # pick the top 20 by raw z out of 1000 no-better-than-average wallets: raw over-states
    # their true Sharpe, the posterior mean much less so
    data = _sim(1000, 7)
    pr = shrink.fit_prior([(z, y) for _, y, z in data])
    top = sorted(data, key=lambda r: -r[2])[:20]
    err_raw = sum((z / math.sqrt(y) - s) ** 2 for s, y, z in top)
    err_post = sum((shrink.posterior(z, y, pr)["mean"] - s) ** 2 for s, y, z in top)
    assert err_post < 0.5 * err_raw
    assert all(shrink.posterior(z, y, pr)["shrunk"] > 0 for s, y, z in top)


def test_longer_record_shrunk_less():
    data = _sim(600, 3)
    pr = shrink.fit_prior([(z, y) for _, y, z in data])
    short = shrink.posterior(2.5, 0.5, pr)
    long_ = shrink.posterior(2.5 * math.sqrt(8), 4.0, pr)  # same raw Sharpe, 8x the record
    assert abs(short["raw"] - long_["raw"]) < 1e-9
    assert long_["shrunk"] < short["shrunk"]


def test_predictive_interval_covers():
    data = _sim(600, 11)
    pr = shrink.fit_prior([(z, y) for _, y, z in data])
    rnd = random.Random(12)
    hit = 0
    for s, y, z in data[:300]:
        ya = 8 / 52
        zf = rnd.gauss(s * math.sqrt(ya), 1.0)
        p = shrink.predictive(z, y, pr, ya)
        hit += p["lo"] <= zf <= p["hi"]
    assert 0.84 < hit / 300 < 0.96
