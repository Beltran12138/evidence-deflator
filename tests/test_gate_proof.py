"""Proofs, not samples: the gate's rule check, for every input.

test_gate_composition searches sequences of orders breadth-first, and says so: a clean run covers the
sequences it visited, to depth 4 and 4,000 states, with a handful of order sizes. This file asks an SMT
solver (z3) the same questions about ``agent_gate.check`` for every real-valued quantity, price,
position, loss, order count and limit at once. Each property is stated as "there is an input where the
gate allows the order and the owner's rule is broken"; z3 answering *unsat* means no such input exists.

Five of the owner-side invariants hold at every step, whatever came before, so a step-wise proof covers
sequences of any length:

  order     an allowed order is never above max_order_usd
  position  an allowed order that grows a position never leaves it above max_position_usd
  allow     an allowed order in a symbol off the list only shrinks an existing position
  loss      once the day is down by max_daily_loss_usd, an allowed order only shrinks a position
  count     once orders_today reaches max_orders_per_day, an allowed order only shrinks a position

One is inductive: with sides ["buy"], an allowed order never takes a position from >= 0 to < 0. Price
moves and day changes do not change positions, so a long-only account that starts flat or long stays so.
The count property becomes "position-growing orders per day <= max_orders_per_day" given that the gate's
orders_today counts the day's allowed orders (Gate._today does; test_gate_composition checks it against
the broker's account).

And one in the other direction (iFixAi's "the legitimate path must stay open"):

  flatten   from every state, an order of min(|position|, max_order_usd / price) on the closing side
            is allowed, whatever the allow list, sides, loss or count say

What this does not prove, stated so nobody reads more into a green run:
  - z3 reasons about a transcription of check() (``model`` below), not the Python source. The fidelity
    test runs both on thousands of inputs and requires identical decisions; it is a test, not a proof.
  - Real arithmetic, not IEEE doubles. The one place rounding mattered (an order sized exactly at the
    limit) has its own check in doubles, below.
  - That Gate.place builds ctx truthfully, that the mandate is valid and unrevoked (a revoked mandate
    refuses everything, closing orders included, by design), that the broker does what it is told, and
    that the agent has no other way to the money. The gate controls the channel it sits on.
  - Limits are taken as finite and non-negative; they come from the owner's signed mandate.
"""
import itertools
import os
import random
import sys
from fractions import Fraction

import pytest

z3 = pytest.importorskip("z3")   # pip install z3-solver

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent_gate as ag  # noqa: E402

SLACK = z3.RealVal(Fraction(ag.LIMIT_SLACK).limit_denominator(10**12))


class V:
    """Symbolic inputs: one order, its context and a rule set. Optional limits carry a has_ flag."""

    def __init__(self):
        R, B = z3.Real, z3.Bool
        self.qty, self.price, self.pos, self.loss, self.cnt = R("qty"), R("price"), R("pos"), R("loss"), R("cnt")
        self.buy = B("buy")                                   # side: buy if true, sell if false
        self.listed = B("listed")                             # symbol is on the allow list
        self.has_allow, self.has_sides = B("has_allow"), B("has_sides")
        self.sides_buy, self.sides_sell = B("sides_buy"), B("sides_sell")
        self.mo, self.mp, self.ml, self.mn = R("mo"), R("mp"), R("ml"), R("mn")
        self.has_mo, self.has_mp, self.has_ml, self.has_mn = B("has_mo"), B("has_mp"), B("has_ml"), B("has_mn")

    def limits_sane(self):
        return z3.And(self.mo >= 0, self.mp >= 0, self.ml >= 0, self.mn >= 0)


def zabs(x):
    return z3.If(x >= 0, x, -x)


def over(amount, limit):
    return amount > limit * (1 + SLACK)


def model(v, drop=()):
    """check() as formulas. ``drop`` removes one guard, for the negative controls."""
    valid = z3.And(v.qty > 0, v.price > 0) if "valid" not in drop else z3.BoolVal(True)
    reducing = z3.Or(z3.And(z3.Not(v.buy), 0 < v.qty, v.qty <= v.pos), z3.And(v.buy, 0 < v.qty, v.qty <= -v.pos))
    if "reducing" in drop:
        reducing = z3.BoolVal(False)
    after = v.pos + z3.If(v.buy, v.qty, -v.qty)
    grows = z3.Or(zabs(after) > zabs(v.pos), after * v.pos < 0)
    side_ok = z3.If(v.buy, v.sides_buy, v.sides_sell)
    refuse = {
        "allow": z3.And(v.has_allow, z3.Not(v.listed), z3.Not(reducing)),
        "sides": z3.And(v.has_sides, z3.Not(side_ok), z3.Not(reducing)),
        "position": z3.And(v.has_mp, z3.Not(reducing), over(zabs(after) * v.price, v.mp), grows),
        "order": z3.And(v.has_mo, over(v.qty * v.price, v.mo)),
        "loss": z3.And(v.has_ml, z3.Not(reducing), v.loss >= v.ml),
        "count": z3.And(v.has_mn, z3.Not(reducing), v.cnt >= v.mn),
    }
    allowed = z3.And(valid, z3.Not(z3.Or([c for k, c in refuse.items() if k not in drop])))
    return allowed, reducing, after, grows


def counterexample(claim_broken, v):
    """None if no input breaks the claim (unsat); otherwise the model z3 found."""
    s = z3.Solver()
    s.set("timeout", 60_000)
    s.add(v.limits_sane(), claim_broken)
    r = s.check()
    assert r != z3.unknown, "z3 gave up; the property is neither proved nor refuted"
    return None if r == z3.unsat else s.model()


def properties(v, drop=()):
    allowed, reducing, after, grows = model(v, drop)
    shrinks_only = z3.And(zabs(after) < zabs(v.pos), after * v.pos >= 0)
    return {
        "order": z3.And(allowed, v.has_mo, v.qty * v.price > v.mo * (1 + SLACK)),
        "position": z3.And(allowed, v.has_mp, grows, zabs(after) * v.price > v.mp * (1 + SLACK)),
        "allow": z3.And(allowed, v.has_allow, z3.Not(v.listed), z3.Not(shrinks_only)),
        "loss": z3.And(allowed, v.has_ml, v.loss >= v.ml, z3.Not(shrinks_only)),
        "count": z3.And(allowed, v.has_mn, v.cnt >= v.mn, z3.Not(shrinks_only)),
        "long_only": z3.And(allowed, v.has_sides, v.sides_buy, z3.Not(v.sides_sell), v.pos >= 0, after < 0),
    }


@pytest.mark.parametrize("name", ["order", "position", "allow", "loss", "count", "long_only"])
def test_no_input_breaks_the_rule(name):
    v = V()
    cex = counterexample(properties(v)[name], v)
    assert cex is None, f"{name}: z3 found an input the gate allows that breaks the rule: {cex}"


def test_flatten_is_always_allowed():
    """The closing order min(|pos|, mo / price) passes for every position, price, loss, count and list."""
    v = V()
    piece = z3.If(v.has_mo, z3.If(zabs(v.pos) * v.price <= v.mo, zabs(v.pos), v.mo / v.price), zabs(v.pos))
    s = z3.Solver()
    s.set("timeout", 60_000)
    s.add(v.limits_sane(), v.mo > 0, v.price > 0, v.pos != 0, v.qty == piece, v.buy == (v.pos < 0))
    allowed, reducing, after, grows = model(v)
    s.add(z3.Not(z3.And(allowed, reducing)))
    assert s.check() == z3.unsat, f"a closing order is refused: {s.model()}"


# ---------------------------------------------------------------- negative controls

@pytest.mark.parametrize("name,drop", [
    ("order", "order"), ("position", "position"), ("allow", "allow"), ("loss", "loss"),
    ("count", "count"), ("long_only", "sides"),
    ("long_only", "valid"),      # the hole fixed 2026-10-30: buy with a negative quantity went short
])
def test_negative_control_each_proof_fails_without_its_guard(name, drop):
    v = V()
    assert counterexample(properties(v, drop=(drop,))[name], v) is not None, \
        f"{name} still 'proved' with the {drop} guard removed: the property does not test that guard"


def test_negative_control_flatten_fails_without_the_reducing_exemption():
    v = V()
    allowed, reducing, after, grows = model(v, drop=("reducing",))
    s = z3.Solver()
    s.add(v.limits_sane(), v.price > 0, v.pos > 0, v.qty == v.pos, z3.Not(v.buy), v.has_ml, v.loss >= v.ml)
    s.add(z3.Not(allowed))
    assert s.check() == z3.sat


# ---------------------------------------------------------------- fidelity: the model is check()

def concrete(v, order, ctx, cfg):
    allow, sides = cfg.get("allow"), cfg.get("sides")
    vals = {
        v.qty: order["qty"], v.price: ctx["price"], v.pos: ctx["position"], v.loss: ctx["loss_today"],
        v.cnt: ctx["orders_today"], v.buy: order["side"] == "buy", v.listed: bool(allow) and order["symbol"] in allow,
        v.has_allow: bool(allow), v.has_sides: bool(sides), v.sides_buy: bool(sides) and "buy" in sides,
        v.sides_sell: bool(sides) and "sell" in sides,
    }
    for key, var, flag in (("max_order_usd", v.mo, v.has_mo), ("max_position_usd", v.mp, v.has_mp),
                           ("max_daily_loss_usd", v.ml, v.has_ml), ("max_orders_per_day", v.mn, v.has_mn)):
        vals[flag] = cfg.get(key) is not None
        vals[var] = cfg.get(key) if cfg.get(key) is not None else 0
    subs = []
    for var, x in vals.items():
        subs.append((var, z3.BoolVal(x) if isinstance(x, bool) else z3.RealVal(Fraction(x))))
    return subs


def model_allows(v, order, ctx, cfg):
    allowed = model(v)[0]
    return z3.is_true(z3.simplify(z3.substitute(allowed, *concrete(v, order, ctx, cfg))))


def cases():
    """Every combination on a grid of exactly representable values (so float and real arithmetic agree),
    plus random inputs kept away from the boundaries where the two would round differently."""
    grid_q, grid_p, grid_pos = [0.5, 1.0, 2.0, 5.0], [10.0, 40.0, 100.0], [-5.0, -1.0, 0.0, 1.0, 5.0]
    cfgs = [
        {"allow": ["BTC"], "max_order_usd": 100, "max_position_usd": 200, "max_daily_loss_usd": 50,
         "max_orders_per_day": 3},
        {"allow": ["BTC"], "sides": ["buy"], "max_order_usd": 400, "max_position_usd": 400},
        {"sides": ["sell"], "max_daily_loss_usd": 0, "max_orders_per_day": 0},
        {},
    ]
    for q, p, pos, side, sym, (loss, cnt), cfg in itertools.product(
            grid_q, grid_p, grid_pos, ["buy", "sell"], ["BTC", "ETH"], [(0.0, 0), (60.0, 5)], cfgs):
        yield {"symbol": sym, "side": side, "qty": q}, {"price": p, "position": pos, "loss_today": loss,
                                                         "orders_today": cnt}, cfg
    rng = random.Random(20261030)
    n = 0
    while n < 1500:
        cfg = rng.choice(cfgs)
        o = {"symbol": rng.choice(["BTC", "ETH"]), "side": rng.choice(["buy", "sell"]), "qty": rng.uniform(0.01, 10)}
        c = {"price": rng.uniform(1, 200), "position": rng.uniform(-10, 10), "loss_today": rng.uniform(0, 100),
             "orders_today": rng.randint(0, 6)}
        q, p, pos = o["qty"], c["price"], c["position"]
        near = [abs(q - abs(pos))]
        after = pos + (q if o["side"] == "buy" else -q)
        for key, x in (("max_order_usd", q * p), ("max_position_usd", abs(after) * p)):
            if cfg.get(key):
                near.append(abs(x - cfg[key]) / cfg[key])
        if min(near) < 1e-6:
            continue
        n += 1
        yield o, c, cfg


def test_the_model_decides_exactly_like_check():
    v = V()
    total = disagree = 0
    for order, ctx, cfg in cases():
        total += 1
        if model_allows(v, order, ctx, cfg) != (not ag.check(order, ctx, cfg)):
            disagree += 1
            assert False, (order, ctx, cfg, ag.check(order, ctx, cfg))
    assert total > 3000 and disagree == 0
    decided = [not ag.check(o, c, g) for o, c, g in itertools.islice(cases(), 2000)]
    assert any(decided) and not all(decided)     # both outcomes occur, or the comparison says nothing


# ---------------------------------------------------------------- the one place rounding matters

def test_an_order_sized_at_the_limit_passes_under_ieee_rounding():
    """usd = limit, qty = usd / price, notional = qty * price, then the comparison limit * (1 + slack).
    IEEE 754 guarantees each operation with a normal result is exact up to a relative error of at most
    u = 2**-53 (Higham, Accuracy and Stability of Numerical Algorithms, ch. 2). Under that model, for every
    positive limit and price, the gate never refuses such an order on size. Bit-level Float64 was tried
    first and z3 did not finish in two minutes, so this is the standard rounding model, not bit-blasting.
    Before 2026-10-30 the comparison was exact; the control shows the same model finds that hole."""
    u = z3.RealVal(Fraction(1, 2**53))
    limit, price, e1, e2, e3, e4 = z3.Reals("limit price e1 e2 e3 e4")
    qty = limit / price * (1 + e1)                     # fl(limit / price)
    notional = qty * price * (1 + e2)                  # fl(qty * price)
    bound = limit * ((1 + SLACK) * (1 + e3)) * (1 + e4)   # fl(limit * fl(1 + slack))
    errs = z3.And([z3.And(-u <= e, e <= u) for e in (e1, e2, e3, e4)])
    s = z3.Solver()
    s.set("timeout", 60_000)
    s.add(limit > 0, price > 0, errs, notional > bound)
    assert s.check() == z3.unsat, f"an order at the limit can be refused: {s.model()}"
    old = z3.Solver()
    old.add(limit > 0, price > 0, errs, notional > limit)
    assert old.check() == z3.sat, "the exact comparison should have a counterexample"


def test_orders_at_the_limit_in_actual_doubles():
    rng = random.Random(7)
    refused = 0
    for _ in range(200_000):
        limit = rng.choice([1, 50, 100, 250, 500, 1000, 2500, 1e4, 1e6]) * rng.choice([1, 1.0, 0.37, 3.3])
        price = 10 ** rng.uniform(-6, 7)
        if ag._over((limit / price) * price, limit):
            refused += 1
    assert refused == 0


def test_the_two_holes_closed_2026_10_30_stay_closed():
    base = {"price": 100.0, "position": 0.0, "loss_today": 0.0, "orders_today": 0}
    long_only = {"allow": ["BTC"], "sides": ["buy"], "max_order_usd": 500, "max_position_usd": 1000}
    assert ag.check({"symbol": "BTC", "side": "buy", "qty": -5.0}, base, long_only)
    for bad in ({"qty": float("nan")}, {"qty": float("inf")}):
        assert ag.check(dict({"symbol": "BTC", "side": "buy"}, **bad), base, long_only)
    for key in ("price", "position", "loss_today"):
        assert ag.check({"symbol": "BTC", "side": "buy", "qty": 1.0}, dict(base, **{key: float("nan")}), long_only)
    price = 56920.39179018248                       # usd / price * price lands one step above 250 here
    assert ag.check({"symbol": "BTC", "side": "buy", "qty": 250 / price}, dict(base, price=price),
                    {"max_order_usd": 250}) == []
