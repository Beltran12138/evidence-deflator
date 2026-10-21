"""Hyperliquid wallet check: is this record skill, or could it be luck?

The scoring that powers evidencedeflator.com/wallet/, in the standard library.
docs/assets/hl.js is the browser port; tools/check_hl_parity.py runs both on
the same portfolios and diffs them.

Returns come from the PnL history, not the account-value history: account
value moves with deposits and withdrawals, PnL does not. Each interval's return
is the change in cumulative PnL divided by account value at its start. History
is put on a weekly grid anchored at the last sample; a week with no new sample
is merged into the next interval, not scored as zero. The t statistic uses the
n - 1 variance for unequal intervals and Student's t on Satterthwaite degrees
of freedom, put back on the normal scale, so the bars are 2 for one record
picked blind and the Bonferroni best-of-N bar for one found on a leaderboard.

This is the one module in the package that touches the network, and only in
``fetch_portfolio`` (Hyperliquid's public info API, no key).
"""
from __future__ import annotations

import json
import math
import statistics
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

N = statistics.NormalDist()

INFO_URL = "https://api.hyperliquid.xyz/info"
WEEK_MS = 7 * 24 * 3600 * 1000
MIN_WEEKS = 8
MIN_AV = 1000.0  # weeks starting below this account value are skipped
ALPHA = 1 - N.cdf(2)


def bar(n):
    return N.inv_cdf(1 - ALPHA / n)


def months_to_clear(b, sharpe):
    return (b / sharpe) ** 2 * 12 if sharpe and sharpe > 0 else None


def _betacf(a, b, x):
    """Continued fraction for the incomplete beta function (Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return h


def _betai(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1 - bt * _betacf(b, a, 1 - x) / b


def t_to_z(t, dof):
    """The normal score with the same tail probability as Student's t with `dof` degrees of freedom.

    A t computed from a few intervals has fat tails: with 8 intervals and no skill,
    t >= 2 turns up about twice as often as the normal bar of 2 assumes. Putting t on
    the normal scale keeps the bars (2 and best-of-N) the same for every record length.
    """
    if t == 0:
        return 0.0
    p = 0.5 * _betai(dof / 2, 0.5, dof / (dof + t * t))  # P(T > |t|)
    return math.copysign(-N.inv_cdf(max(p, 1e-300)), t)


def weekly_returns(pf, since=None, with_times=False):
    """Returns between weekly grid nodes, merged where the source has no new sample.

    Each node takes the last source sample at or before it. Two nodes that land
    on the same sample carry no information about the week between them, so
    that week is merged into the next interval instead of being scored as a
    zero return (which would inflate the week count and shrink the spread).
    Returns (list of (return, interval_in_weeks), start ms, end ms, dollar PnL
    inside the counted intervals).

    With `since` (ms), the grid starts at `since` and steps forward, so only the
    record after that moment is scored (the forward record of a frozen cohort).
    The first node is the last sample at or before `since`.

    With `with_times`, each interval is (return, interval_in_weeks, start ms, end ms), so it
    can be matched against a benchmark over the same dates (alpha_vs).
    """
    av = [(t, float(v)) for t, v in pf["allTime"]["accountValueHistory"]]
    pnl = dict((t, float(v)) for t, v in pf["allTime"]["pnlHistory"])
    if len(av) < 2:
        return [], None, None, 0.0
    start, end = av[0][0], av[-1][0]
    if since is None:
        grid = list(range(end, start - 1, -WEEK_MS))[::-1]
    else:
        grid = list(range(since, end + 1, WEEK_MS))

    nodes, i = [], 0
    for g in grid:
        while i + 1 < len(av) and av[i + 1][0] <= g:
            i += 1
        if av[i][0] <= g and (not nodes or nodes[-1] != i):
            nodes.append(i)

    out, counted = [], 0.0
    for a, b in zip(nodes, nodes[1:]):
        ta, va = av[a]
        tb = av[b][0]
        if va < MIN_AV or ta not in pnl or tb not in pnl:
            continue
        out.append(((pnl[tb] - pnl[ta]) / va, (tb - ta) / WEEK_MS, ta, tb))
        counted += pnl[tb] - pnl[ta]
    if with_times:
        return out, start, end, counted
    return [(r, w) for r, w, _, _ in out], start, end, counted


def recent_returns(pf, window="month"):
    """Returns between consecutive samples of a short portfolio window (``month``: about one sample a
    day for the last 30 days). Same rule as the weekly series: change in PnL over account value at the
    start, intervals in weeks, samples starting below MIN_AV skipped. A finer look at the recent record,
    reported next to the verdict and never used for it: the verdict and every pre-registered reading use
    ``weekly_returns``, because only the weekly grid covers the whole history."""
    w = pf.get(window) or {}
    av = [(t, float(v)) for t, v in w.get("accountValueHistory", [])]
    pnl = dict((t, float(v)) for t, v in w.get("pnlHistory", []))
    out = []
    for (ta, va), (tb, _) in zip(av, av[1:]):
        if va >= MIN_AV and ta in pnl and tb in pnl and tb > ta:
            out.append(((pnl[tb] - pnl[ta]) / va, (tb - ta) / WEEK_MS))
    return out


def flags(pf, rets, counted):
    """What t cannot see, reported next to it. Same rules as HL.flags in docs/assets/hl.js."""
    out = []
    if len(rets) >= MIN_WEEKS:
        if not any(r < 0 for r, _ in rets):
            out.append("no_losing_week")
        gains = [r for r, _ in rets if r > 0]
        if sum(r for r, _ in rets) > 0 and gains and max(gains) / sum(gains) > 0.5:
            out.append("one_week_majority")
    pnl = pf["allTime"]["pnlHistory"]
    total = float(pnl[-1][1]) - float(pnl[0][1]) if pnl else 0.0
    if total > 0 and (total - counted) / total > 0.5:
        out.append("pnl_outside_record")
    return out


def score(rets):
    """Evidence in returns over unequal intervals.

    mu is the drift per week (sum r / sum dt); the variance per week divides the
    squared residuals by W - sum(dt^2)/W rather than W, which is the n - 1 correction
    for unequal intervals (it is n - 1 when all intervals are one week). Then
    t_student = Sharpe * sqrt(years), and `t` is that value put on the normal scale
    (t_to_z), so short records are not over-read. Degrees of freedom are
    Satterthwaite's for these residuals, (tr A)^2 / tr(A^2), which in power sums
    S_k = sum dt^k is (W - S2/W)^2 / (S2 - 2 S3/W + S2^2/W^2): n - 1 for equal
    intervals, fewer when a few long intervals carry most of the record.
    """
    n = len(rets)
    if n < MIN_WEEKS:
        return {"weeks": n, "sharpe": None, "t": None}
    tot_r = sum(r for r, _ in rets)
    tot_w = sum(w for _, w in rets)
    mu = tot_r / tot_w
    ss = sum((r - mu * w) ** 2 for r, w in rets)
    s2 = sum(w * w for _, w in rets)
    s3 = sum(w ** 3 for _, w in rets)
    eff = tot_w - s2 / tot_w
    if ss == 0 or tot_w <= 0 or eff <= 0:
        return {"weeks": n, "sharpe": None, "t": None}
    sigma_w = math.sqrt(ss / eff)  # per sqrt(week)
    sharpe = mu / sigma_w * math.sqrt(52)
    t_student = tot_r / (sigma_w * math.sqrt(tot_w))
    dof = eff ** 2 / (s2 - 2 * s3 / tot_w + s2 * s2 / tot_w ** 2)
    return {"weeks": round(tot_w, 1), "intervals": n, "sharpe": round(sharpe, 3),
            "t_student": round(t_student, 3), "dof": round(dof, 1), "t": round(t_to_z(t_student, dof), 3)}


def luck(t, n=1):
    """Chance that luck alone produces a record at least this strong: for one record picked blind
    (n = 1), the one-sided tail of t; for the best of n records with no skill, the chance that any
    of them gets this far, 1 - (1 - tail)^n. Same as HL.luck in docs/assets/hl.js."""
    if t is None:
        return None
    q = 1 - N.cdf(t)
    return -math.expm1(max(n, 1) * math.log1p(-q)) if q < 1 else 1.0


def bench_returns(candles, intervals):
    """Benchmark return over each interval, from daily candles [{"t": open ms, "T": close ms, "c": close}]:
    the close of the last candle that closed at or before each end. Intervals that start before the
    first candle get None."""
    cs = sorted((int(c["T"]), float(c["c"])) for c in candles)
    ts = [t for t, _ in cs]
    import bisect

    def px(ms):
        i = bisect.bisect_right(ts, ms) - 1
        return cs[i][1] if i >= 0 else None
    out = []
    for *_, ta, tb in intervals:
        a, b = px(ta), px(tb)
        out.append(None if a is None or b is None or a <= 0 else b / a - 1)
    return out


def alpha_vs(intervals, bench):
    """Evidence after taking out a benchmark's moves (BTC for wallets).

    Each interval's return r_i over dt_i weeks is fit as r_i = alpha * dt_i + beta * b_i + e_i with
    Var(e_i) proportional to dt_i (weighted least squares, weights 1/dt_i), where b_i is the
    benchmark's return over the same dates. With beta fixed at 0 this is the drift score() uses.
    t_alpha is alpha over its standard error, put on the normal scale with n - 2 degrees of
    freedom, like `t`. Intervals without a benchmark return are left out. Same as HL.alphaVs.
    """
    pts = [(r, w, b) for (r, w, *_), b in zip(intervals, bench) if b is not None and w > 0]
    n = len(pts)
    if n < MIN_WEEKS:
        return {"t_btc": None, "beta_btc": None, "n_btc": n}
    # y = r/sqrt(w), x1 = sqrt(w), x2 = b/sqrt(w); OLS without intercept
    sxx11 = sum(w for _, w, _ in pts)
    sxx12 = sum(b for _, _, b in pts)
    sxx22 = sum(b * b / w for _, w, b in pts)
    sxy1 = sum(r for r, _, _ in pts)
    sxy2 = sum(r * b / w for r, w, b in pts)
    det = sxx11 * sxx22 - sxx12 ** 2
    if det <= 0:
        return {"t_btc": None, "beta_btc": None, "n_btc": n}
    a = (sxx22 * sxy1 - sxx12 * sxy2) / det
    be = (sxx11 * sxy2 - sxx12 * sxy1) / det
    rss = sum((r - a * w - be * b) ** 2 / w for r, w, b in pts)
    s2 = rss / (n - 2)
    if s2 <= 0:
        return {"t_btc": None, "beta_btc": round(be, 3), "n_btc": n}
    t_a = a / math.sqrt(s2 * sxx22 / det)
    return {"t_btc": round(t_to_z(t_a, n - 2), 3), "beta_btc": round(be, 3), "n_btc": n}


SIEGMUND = 0.5826  # -zeta(1/2) / sqrt(2 pi)


def drawdown(rets):
    """Where the record stands against its own peak, and how ordinary that is if its edge is real.

    The path adds up the scored weekly returns: the same arithmetic returns t is built
    from. Most accounts add and withdraw money, so compounding would describe a portfolio
    nobody held (a volatile account with a positive mean compounds toward zero). `now` and
    `deepest` are sums of weekly returns below the running peak, so they can exceed 1.
    For a path drifting at m per week with variance s2 per week, the distance below the
    running peak settles to an exponential
    with rate 2m/s2 (reflected Brownian motion), so the share of time spent at least d
    below the peak is exp(-2 m d / s2). Measured weekly, the walk overshoots the peak
    between samples; Siegmund's correction (d + 0.5826 s) keeps the share within about 2%
    of simulation up to Sharpe 3, where the plain formula is 1.6x too high
    (tests/test_drawdown.py). m and s2 are measured on the same record, with the same
    estimator as score(). Same as HL.drawdown in docs/assets/hl.js.

    The edge is measured on the record itself, often one picked for being good, so it is
    more likely overstated than understated; a smaller true edge makes drawdowns more
    common, so share_if_real leans toward calling a drawdown unusual.
    """
    if len(rets) < MIN_WEEKS:
        return None
    w = peak = max_dd = since = tot_r = tot_w = 0.0
    for r, dt in rets:
        w += r
        tot_r += r
        tot_w += dt
        if w >= peak:
            peak, since = w, 0.0
        else:
            since += dt
        max_dd = max(max_dd, peak - w)
    mu = tot_r / tot_w
    ss = sum((r - mu * dt) ** 2 for r, dt in rets)
    s2 = sum(dt * dt for _, dt in rets)
    eff = tot_w - s2 / tot_w
    v = ss / eff if eff > 0 else 0.0
    m, d = mu, peak - w
    return {"now": round(d, 4), "weeks_below": round(since, 1), "deepest": round(max_dd, 4),
            "share_if_real": (None if not (m > 0 and v > 0) else 1.0 if d == 0 else
                              round(math.exp(-2 * m * (d + SIEGMUND * math.sqrt(v)) / v), 4))}


def verdict(sc: Dict[str, Any], picked_from: Optional[int] = None) -> Dict[str, Any]:
    """Same keys as HL.verdict in docs/assets/hl.js."""
    b = bar(picked_from) if picked_from and picked_from > 1 else 2.0
    t = sc.get("t")
    if t is None:
        key = "too_short"
    elif t >= b and picked_from and picked_from > 1:
        key = "clears_board"
    elif t >= 2:
        key = "clears_single"
    elif t <= -2:
        key = "loses"
    else:
        key = "luck"
    return {"key": key, "bar": round(b, 2)}


def fetch_portfolio(address: str, timeout: float = 30.0) -> Dict[str, Any]:
    """Portfolio history from Hyperliquid's public info API (no key)."""
    body = json.dumps({"type": "portfolio", "user": address}).encode()
    req = urllib.request.Request(INFO_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    if not isinstance(data, list) or not data:
        raise ValueError("no portfolio history for " + address)
    return dict(data)


def fetch_candles(coin: str = "BTC", start_ms: int = 1672531200000, end_ms: Optional[int] = None,
                  timeout: float = 30.0) -> List[Dict[str, Any]]:
    """Daily candles from Hyperliquid's public info API (no key), for alpha_vs."""
    end_ms = end_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    body = json.dumps({"type": "candleSnapshot", "req": {"coin": coin, "interval": "1d",
                                                         "startTime": start_ms, "endTime": end_ms}}).encode()
    req = urllib.request.Request(INFO_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def check(address: str, picked_from: Optional[int] = None, pf: Optional[Dict[str, Any]] = None,
          candles: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Score one wallet. Pass ``pf`` to score a portfolio you already have (then nothing is fetched:
    without ``candles``, BTC daily, the BTC-adjusted numbers are None, as when they cannot be fetched)."""
    offline = pf is not None
    pf = pf if offline else fetch_portfolio(address)
    iv, start, end, counted = weekly_returns(pf, with_times=True)
    rets = [(r, w) for r, w, _, _ in iv]
    if candles is None and offline:
        candles = []
    if candles is None:
        try:
            candles = fetch_candles("BTC", start_ms=start or 1672531200000)
        except Exception:
            candles = []
    adj = alpha_vs(iv, bench_returns(candles, iv)) if candles else {"t_btc": None, "beta_btc": None, "n_btc": 0}
    sc = score(rets)
    v = verdict(sc, picked_from)
    months = (months_to_clear(v["bar"], sc["sharpe"]) if sc.get("sharpe") else None)
    have = (sc["weeks"] or 0) / 4.345 if sc.get("t") is not None else 0
    day = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d") if ms is not None else None
    return {
        "address": address,
        **sc,
        "verdict": v["key"],
        "bar": v["bar"],
        # For a caller that gates on the result with a fixed rule rather than reading the prose.
        "clears_bar": sc.get("t") is not None and sc["t"] >= v["bar"],
        "bar_rule": (f"best of {picked_from}: t >= {v['bar']}" if picked_from and picked_from > 1
                     else "picked blind: t >= 2"),
        "picked_from": picked_from,
        "months_more_to_clear": (None if months is None else round(max(months - have, 0), 1)),
        "luck_one_in": (None if sc.get("t") is None else round(1 / luck(sc["t"], picked_from or 1), 1)),
        **adj,
        "flags": flags(pf, rets, counted),
        "drawdown": drawdown(rets),
        "history_from": day(start),
        "history_to": day(end),
    }


def gate(res: Dict[str, Any], min_weeks: Optional[float] = None) -> Dict[str, Any]:
    """A fixed allow/deny rule on a ``check()`` result, for a caller that moves money on it.

    Allows only a record that clears the bar for how it was picked (``clears_bar``), and,
    if ``min_weeks`` is given, has at least that many scored weeks. Everything else is
    denied, including a record too short to score: "cannot tell" is a limit of zero, not
    a pass. The rule and the reason come back with the decision so the caller can log them.
    """
    weeks = res.get("weeks") or 0
    if res.get("t") is None:
        allow, reason = False, "too_short"
    elif min_weeks is not None and weeks < min_weeks:
        allow, reason = False, "below_min_weeks"
    elif res.get("clears_bar"):
        allow, reason = True, res.get("verdict")
    else:
        allow, reason = False, res.get("verdict")
    rule = res.get("bar_rule") or "picked blind: t >= 2"
    if min_weeks is not None:
        rule += f"; at least {min_weeks:g} weeks"
    return {"address": res.get("address"), "allow": allow, "reason": reason, "rule": rule,
            "t": res.get("t"), "bar": res.get("bar"), "weeks": weeks}


def main(argv: Optional[List[str]] = None) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m hl_wallet",
                                 description="Is this Hyperliquid wallet's record skill, or could it be luck?")
    ap.add_argument("address")
    ap.add_argument("--picked-from", type=int, default=None,
                    help="how many wallets it was chosen from (the leaderboard size if found on one)")
    ap.add_argument("--gate", action="store_true",
                    help="print an allow/deny decision instead; exit status 0 allows, 1 denies")
    ap.add_argument("--min-weeks", type=float, default=None, help="with --gate, also require this many scored weeks")
    a = ap.parse_args(argv)
    res = check(a.address.lower(), picked_from=a.picked_from)
    if a.gate:
        g = gate(res, a.min_weeks)
        print(json.dumps(g, indent=2))
        raise SystemExit(0 if g["allow"] else 1)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
