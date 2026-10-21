import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent_gate as ag  # noqa: E402
import hl_wallet  # noqa: E402

RULES = dict(ag.DEFAULTS)


def ctx(**kw):
    c = {"price": 100.0, "position": 0.0, "loss_today": 0.0, "orders_today": 0}
    c.update(kw)
    return c


def test_check_passes_inside_every_rule():
    assert ag.check({"symbol": "BTC", "side": "buy", "qty": 4.0}, ctx(), RULES) == []


def test_check_single_order_limit():
    r = ag.check({"symbol": "BTC", "side": "buy", "qty": 6.0}, ctx(), RULES)
    assert len(r) == 1 and "single-order limit" in r[0]


def test_check_allow_list():
    r = ag.check({"symbol": "DOGE", "side": "buy", "qty": 1.0}, ctx(), RULES)
    assert len(r) == 1 and "allow list" in r[0]


def test_daily_loss_blocks_new_risk_but_not_closing():
    hit = ctx(loss_today=250.0, position=3.0)
    assert any("daily-loss" in x for x in ag.check({"symbol": "BTC", "side": "buy", "qty": 1.0}, hit, RULES))
    # selling part of a long only reduces risk: must still pass after the loss limit
    assert ag.check({"symbol": "BTC", "side": "sell", "qty": 2.0}, hit, RULES) == []
    # selling more than held opens a short: blocked
    assert ag.check({"symbol": "BTC", "side": "sell", "qty": 4.0}, hit, RULES) != []


def test_order_count_limit_skips_reducing_orders():
    full = ctx(orders_today=20, position=-2.0)
    assert ag.check({"symbol": "ETH", "side": "sell", "qty": 1.0}, full, RULES) != []
    assert ag.check({"symbol": "ETH", "side": "buy", "qty": 1.0}, full, RULES) == []


def test_ledger_chain_detects_edit_and_deletion(tmp_path):
    led = ag.Ledger(str(tmp_path / "l.jsonl"))
    for i in range(4):
        led.append({"kind": "snapshot", "ts_unix": i, "equity_before": 1, "equity_after": 1})
    assert led.verify()["ok"]
    lines = open(led.path).readlines()
    edited = lines[:]
    edited[2] = edited[2].replace('"equity_after":1', '"equity_after":2')
    open(led.path, "w").writelines(edited)
    assert led.verify() == {"ok": False, "lines": 4, "broken_at": 2}
    open(led.path, "w").writelines(lines[:1] + lines[2:])  # delete line 1
    assert led.verify()["broken_at"] == 1


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def make(tmp_path, prices, t=1_760_000_000.0, **rules):
    cfg = dict(ag.DEFAULTS, state_dir=str(tmp_path), **rules)
    clock = Clock(t)
    return ag.Gate(cfg, ag.SimBroker(str(tmp_path), cfg["starting_cash"], lambda: prices), clock), clock


def test_gate_fills_blocks_and_logs(tmp_path):
    px = {"BTC": 100.0, "ETH": 10.0}
    g, _ = make(tmp_path, px)
    a = g.place("btc", "buy", usd=300)
    b = g.place("ETH", "buy", usd=5000)
    c = g.place("DOGE", "buy", usd=10)
    assert (a["decision"], b["decision"], c["decision"]) == ("allow", "block", "block")
    assert g.broker.account()["positions"] == {"BTC": 3.0}
    assert "no price" in c["reasons"][-1] and "allow list" in c["reasons"][0]
    assert g.ledger.verify() == {"ok": True, "lines": 3, "head": g.ledger.read()[-1]["hash"]}


def test_gate_daily_loss_from_ledger(tmp_path):
    px = {"BTC": 100.0}
    g, clock = make(tmp_path, px, max_order_usd=10_000)
    g.place("BTC", "buy", usd=5000)          # 50 BTC, equity 10,000
    px["BTC"] = 95.0                          # equity 9,750: down 250 today
    clock.t += 60
    blocked = g.place("BTC", "buy", usd=100)
    trim = g.place("BTC", "sell", qty=10)
    assert blocked["decision"] == "block" and "daily-loss" in blocked["reasons"][0]
    assert trim["decision"] == "allow"
    clock.t += ag.DAY_S                       # next UTC day: the day's starting equity resets
    assert g.place("BTC", "buy", usd=100)["decision"] == "allow"


def test_scorecard_too_short_then_scored(tmp_path):
    px = {"BTC": 100.0}
    g, clock = make(tmp_path, px)
    g.snapshot()
    assert g.scorecard()["verdict"] == "too_short"
    eq = [10000 * (1.01 ** k) * (1 + (0.02 if k % 2 else -0.02)) for k in range(12)]
    rows = [{"ts_unix": 1_760_000_000 + k * ag.WEEK_S, "equity_after": e} for k, e in enumerate(eq)]
    sc = ag.scorecard(rows)
    rets = [((eq[k + 1] - eq[k]) / eq[k], 1.0) for k in range(11)]
    assert sc["t"] == hl_wallet.score(rets)["t"] and sc["weeks"] == 11
    assert sc["verdict"] == hl_wallet.verdict(hl_wallet.score(rets))["key"]


def test_demo_shows_block_and_broken_chain():
    out = ag.demo(lambda: {"BTC": 60000.0, "ETH": 3000.0, "SOL": 150.0})
    assert out.count("ALLOWED") == 2 and out.count("BLOCKED") == 2
    assert "chain ok = True" in out and "broken at line #1" in out


def test_mcp_surface_has_no_rule_or_ledger_writer():
    gs = pytest.importorskip("gate_server")
    names = {t.name for t in gs.mcp._tool_manager.list_tools()}
    assert names == {"place_order", "account", "recent_log", "scorecard"}
