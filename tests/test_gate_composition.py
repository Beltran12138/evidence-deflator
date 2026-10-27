"""Orders that each pass the gate must not add up to something the owner's rules forbid.

The per-order tests (test_gate_features, test_gate_escalation) check one request at a time. The failure
these tests look for is the one iFixAi's Business Policy Lab is built around: every step is allowed on
its own, and the sequence reaches a state the rules were meant to rule out (in their example, one agent
files, approves and pays its own refund). Here the steps are orders, price moves and day changes; the
search is breadth-first over every sequence up to a fixed depth, run through the real ``Gate.place``
with an in-memory ledger and broker, so the check under test is the gate's own code, not a model of it.

The invariants are stated from the owner's side and computed from the broker's account, not from the
gate's ``ctx``, so a mistake in how the gate builds its context cannot hide itself:

  allow     no position is ever opened or grown in a symbol off the allow list
  sides     with sides ["buy"], no position ever goes below zero
  position  after an allowed order that grows a position, |position| x price <= max_position_usd
  loss      once the day's equity is down by max_daily_loss_usd, no allowed order grows any position
  count     allowed orders that grow a position in one UTC day <= max_orders_per_day

and one property in the other direction (iFixAi's "the legitimate path must stay open"):

  flatten   from every reachable state, a sequence of allowed orders closes every position

The search is bounded (a depth and a cap on distinct states, as Policy Lab's is). A clean run says no
visited sequence breaks a rule; it does not say no sequence can. The two negative controls plant a hole
and check that the search finds it.
"""
import copy
import os
import sys
from collections import deque

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent_gate as ag  # noqa: E402

DAY0 = 1_790_035_200.0          # a UTC midnight
EPS = 1e-6


class MemLedger(ag.Ledger):
    def __init__(self):
        super().__init__(os.devnull)
        self.rows = []

    def read(self):
        return list(self.rows)

    def append(self, entry, signer=None):
        prev = self.rows[-1]["hash"] if self.rows else ag.GENESIS
        entry = dict(entry, seq=len(self.rows), prev=prev)
        entry["hash"] = ag.entry_hash(prev, entry)
        self.rows.append(entry)
        return entry


class MemBroker(ag.SimBroker):
    def __init__(self, prices, cash=10_000.0, positions=None):
        super().__init__(os.devnull, cash, lambda: self.px)
        self.px = dict(prices)
        self.s = {"cash": cash, "positions": dict(positions or {})}

    def prices(self):
        return self.px

    def _state(self):
        return self.s

    def _save(self, s):
        self.s = s


class World:
    """One state of the search: the gate's ledger, the broker's account, prices and the clock."""

    def __init__(self, rules, prices, positions=None, template=None):
        self.rules = rules
        self.ledger = MemLedger()
        self.broker = MemBroker(prices, positions=positions)
        self.now = DAY0 + 3600
        self.day_start_equity = self.broker.account()["equity"]
        self.grown_today = 0
        self.template = template      # a Gate holding a signed mandate; None means rules from the config

    def __deepcopy__(self, memo):
        w = copy.copy(self)
        w.ledger = copy.deepcopy(self.ledger, memo)
        w.broker = copy.deepcopy(self.broker, memo)
        return w

    def gate(self):
        if self.template is not None:
            g = copy.copy(self.template)
            g.broker, g.clock = self.broker, (lambda: self.now)
        else:
            cfg = dict(rules_cfg(self.rules), state_dir=os.devnull)
            g = ag.Gate(cfg, broker=self.broker, clock=lambda: self.now)
        g.ledger = self.ledger
        return g

    def key(self):
        pos = tuple(sorted((s, round(q, 9)) for s, q in self.broker.s["positions"].items()))
        return (pos, round(self.broker.s["cash"], 6), tuple(sorted(self.broker.px.items())),
                int((self.now - DAY0) // ag.DAY_S), self._allowed_today())

    def _allowed_today(self):
        start = self.now - self.now % ag.DAY_S
        return sum(1 for r in self.ledger.rows if r["ts_unix"] >= start and r.get("kind") == "order"
                   and r.get("decision") == "allow")


def rules_cfg(rules):
    base = {k: None for k in ("max_order_usd", "max_position_usd", "max_daily_loss_usd", "allow",
                              "max_orders_per_day")}
    return dict(base, **rules)


def violations(w, sym, before_pos, before_equity, entry):
    """Owner-side invariants for one allowed order, from the account before and after."""
    out = []
    r = w.rules
    after_pos = w.broker.s["positions"].get(sym, 0.0)
    price = w.broker.px[sym]
    grew = abs(after_pos) > abs(before_pos) + EPS or after_pos * before_pos < -EPS
    if not grew:
        return out
    if r.get("allow") and sym not in r["allow"]:
        out.append(f"allow: grew {sym}, which is off the list")
    if r.get("sides") == ["buy"] and after_pos < -EPS:
        out.append(f"sides: {sym} went short to {after_pos:.6f}")
    if r.get("max_position_usd") is not None and abs(after_pos) * price > r["max_position_usd"] + EPS:
        out.append(f"position: {sym} is ${abs(after_pos) * price:,.2f} after the order")
    if (r.get("max_daily_loss_usd") is not None
            and w.day_start_equity - before_equity >= r["max_daily_loss_usd"] - EPS):
        out.append(f"loss: grew {sym} while down ${w.day_start_equity - before_equity:,.2f} today")
    w.grown_today += 1
    if r.get("max_orders_per_day") is not None and w.grown_today > r["max_orders_per_day"]:
        out.append(f"count: {w.grown_today} position-growing orders today")
    return out


def apply(w, action):
    """Run one step on world ``w`` in place. Returns the list of invariant violations it caused."""
    kind = action[0]
    if kind == "order":
        _, sym, side, size = action
        before_pos = w.broker.s["positions"].get(sym, 0.0)
        before_equity = w.broker.account()["equity"]
        w.now += 1
        if size == "close":
            if before_pos == 0:
                return []
            side = "sell" if before_pos > 0 else "buy"
            e = w.gate().place(sym, side, qty=abs(before_pos))
        else:
            e = w.gate().place(sym, side, usd=size)
        return violations(w, sym, before_pos, before_equity, e) if e["decision"] == "allow" else []
    if kind == "move":
        _, sym, factor = action
        w.broker.px[sym] = round(w.broker.px[sym] * factor, 6)
        return []
    if kind == "day":
        w.now = w.now - w.now % ag.DAY_S + ag.DAY_S + 3600
        w.day_start_equity = w.broker.account()["equity"]
        w.grown_today = 0
        return []
    raise ValueError(action)


def actions(symbols, sizes, moves=(0.8, 1.25), days=True):
    out = []
    for s in symbols:
        for side in ("buy", "sell"):
            for size in sizes:
                out.append(("order", s, side, size))
        out.append(("order", s, "sell", "close"))
        for f in moves:
            out.append(("move", s, f))
    if days:
        out.append(("day",))
    return out


def can_flatten(w, max_steps=40):
    """Close every position with allowed orders only, in pieces no larger than the single-order limit."""
    w = copy.deepcopy(w)
    for _ in range(max_steps):
        held = {s: q for s, q in w.broker.s["positions"].items() if abs(q) > EPS}
        if not held:
            return True, None
        sym, q = next(iter(held.items()))
        cap = w.rules.get("max_order_usd")
        piece = abs(q) if cap is None else min(abs(q), cap / w.broker.px[sym])
        w.now += 1
        e = w.gate().place(sym, "sell" if q > 0 else "buy", qty=piece)
        if e["decision"] != "allow":
            return False, (sym, q, e["reasons"])
    return False, ("steps", max_steps)


def search(rules, prices, acts, depth, positions=None, max_states=4000, check_flatten=True, template=None):
    """Breadth-first over sequences of ``acts`` up to ``depth``; every state is visited once."""
    root = World(rules, prices, positions, template)
    seen = {root.key()}
    queue = deque([(root, [])])
    found, stuck = [], []
    while queue:
        w, path = queue.popleft()
        if check_flatten:
            ok, why = can_flatten(w)
            if not ok:
                stuck.append((path, why))
        if len(path) == depth:
            continue
        for a in acts:
            nw = copy.deepcopy(w)
            bad = apply(nw, a)
            if bad:
                found.append((path + [a], bad))
            k = nw.key()
            if k not in seen and len(seen) < max_states:
                seen.add(k)
                queue.append((nw, path + [a]))
    return {"violations": found, "stuck": stuck, "states": len(seen)}


PRICES = {"BTC": 100.0, "ETH": 40.0}
RULES = {"allow": ["BTC", "ETH"], "max_order_usd": 500, "max_position_usd": 1000,
         "max_daily_loss_usd": 200, "max_orders_per_day": 4}


def test_no_sequence_of_allowed_orders_breaks_a_rule():
    r = search(RULES, PRICES, actions(["BTC", "ETH"], [250, 500, 501]), depth=4)
    # Two symbols reach the 4,000-state bound before depth 4 is exhausted: this is a bounded search,
    # and passing it is evidence about the sequences it visited, not a proof about all of them.
    assert r["states"] == 4000, r["states"]
    assert r["violations"] == [], r["violations"][:3]
    assert r["stuck"] == [], r["stuck"][:3]


def mandate_gate(tmp_path, scope):
    """A Gate whose rules come from a mandate signed by a fresh owner key (the path that carries ``sides``)."""
    pytest.importorskip("eth_account")
    import mandate as md
    keys = {}
    for n in ("owner", "gate"):
        keys[n] = str(tmp_path / f"{n}.key")
        md.keygen(keys[n])
    m = md.sign(md.draft(md.address_of(keys["owner"]), md.address_of(keys["gate"]), "sim", "sim", scope,
                         days=14, now=DAY0), keys["owner"])
    md.save(m, str(tmp_path / "mandate.json"))
    cfg = {"state_dir": str(tmp_path / "state"), "mandate": str(tmp_path / "mandate.json"),
           "gate_key": keys["gate"]}
    return ag.Gate(cfg, broker=MemBroker(PRICES), clock=lambda: DAY0 + 3600)


def test_long_only_never_reaches_a_short(tmp_path, monkeypatch):
    rules = dict(RULES, sides=["buy"])
    g = mandate_gate(tmp_path, rules)
    import functools
    import mandate as md
    # The gate re-verifies the signature on every order; recovery is a pure function, so cache it.
    monkeypatch.setattr(md, "recover", functools.lru_cache(maxsize=None)(md.recover))
    assert g._rules()["sides"] == ["buy"]
    r = search(rules, PRICES, actions(["BTC"], [250, 500, 600]), depth=5, template=g)
    assert r["states"] > 100, r["states"]
    assert r["violations"] == [], r["violations"][:3]
    assert r["stuck"] == [], r["stuck"][:3]


def test_sides_in_the_config_file_is_read_too():
    """Fixed 2026-10-27: ``sides`` in gate.json used to be dropped without a word (Gate._rules copied five
    keys), so a config-only gate with sides ["buy"] went short. Now the config path reads it as well."""
    rules = dict(RULES, sides=["buy"])
    assert World(rules, PRICES).gate()._rules()["sides"] == ["buy"]
    r = search(rules, PRICES, actions(["BTC"], [250, 500, 600]), depth=4)
    assert r["violations"] == [], r["violations"][:3]
    assert r["stuck"] == [], r["stuck"][:3]


def test_negative_control_the_search_finds_a_planted_hole(monkeypatch):
    """Drop the position rule from ``check`` and the search must find the split-order path past it."""
    real = ag.check

    def leaky(order, ctx, cfg):
        return real(order, ctx, dict(cfg, max_position_usd=None))

    monkeypatch.setattr(ag, "check", leaky)
    r = search(RULES, PRICES, actions(["BTC"], [500]), depth=3, check_flatten=False)
    paths = [p for p, bad in r["violations"] if any(b.startswith("position:") for b in bad)]
    assert paths and min(len(p) for p in paths) == 3     # 500 + 500 is the limit, the third order breaks it


def test_negative_control_flatten_notices_a_gate_that_refuses_to_reduce(monkeypatch):
    real = ag.check

    def no_exit(order, ctx, cfg):
        return real(order, ctx, cfg) or (["no sells"] if order["side"] == "sell" else [])

    monkeypatch.setattr(ag, "check", no_exit)
    r = search(RULES, PRICES, actions(["BTC"], [250], moves=(), days=False), depth=1)
    assert r["stuck"], "flatten check passed a gate that blocks every sell"


def test_a_position_left_off_a_narrowed_allow_list_can_still_be_closed():
    """Fixed 2026-10-27: the allow list used to be checked before the reducing exemption, so a position
    opened under an earlier mandate in a symbol the new one drops could not be closed through the gate.
    Now it can be shrunk and closed, and still never grown or reopened (the search tries both)."""
    rules = dict(RULES, allow=["BTC"])
    r = search(rules, PRICES, actions(["BTC", "ETH"], [100, 250], moves=(), days=False), depth=3,
               positions={"ETH": 5.0})
    assert r["violations"] == [], r["violations"][:3]
    assert r["stuck"] == [], r["stuck"][:3]
    w = World(rules, PRICES, positions={"ETH": 5.0})
    assert w.gate().place("ETH", "buy", usd=40)["decision"] == "block"
    assert w.gate().place("ETH", "sell", qty=5.0)["decision"] == "allow"
    assert w.gate().place("ETH", "sell", qty=1.0)["decision"] == "block"     # flat now: a sell would open a short


def test_the_browser_check_agrees_with_python_on_off_list_and_side_cases():
    import itertools
    import json as _json
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    js = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "assets", "mandate_examples.js"))
    cfgs = [dict(RULES, allow=["BTC"]), dict(RULES, sides=["buy"]), dict(RULES, allow=["BTC"], sides=["sell"])]
    cases = []
    for cfg, sym, side, qty, pos in itertools.product(cfgs, ["BTC", "ETH"], ["buy", "sell"], [1.0, 5.0, 6.0],
                                                      [-5.0, 0.0, 5.0]):
        ctx = {"price": 40.0, "position": pos, "loss_today": 0.0, "orders_today": 0}
        cases.append({"order": {"symbol": sym, "side": side, "qty": qty}, "ctx": ctx, "cfg": cfg})
    script = ("const m=require(process.argv[1]);const s=JSON.parse(require('fs').readFileSync(0,'utf8'));"
              "process.stdout.write(JSON.stringify(s.map(c=>m.check(c.order,c.ctx,c.cfg).length===0)))")
    got = _json.loads(subprocess.run([node, "-e", script, js], input=_json.dumps(cases), capture_output=True,
                                     text=True, check=True).stdout)
    want = [not ag.check(c["order"], c["ctx"], c["cfg"]) for c in cases]
    assert got == want
    assert sum(want) and not all(want)
