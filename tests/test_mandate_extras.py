"""The owner's intent (signed, not enforced), templates, and the ScopeOfAutonomy export."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

pytest.importorskip("eth_account")

import agent_gate as ag  # noqa: E402
import mandate as md  # noqa: E402
import mandate_templates as mt  # noqa: E402
from test_gate_features import PRICES, SCOPE, T0, keys  # noqa: E402,F401

INTENT = {"purpose": "Rebalance my two ETFs monthly; no stock picking.", "horizon": "Until the end of 2026"}


def signed(keys, scope=SCOPE, intent=None):
    m = md.draft(md.address_of(keys["owner"]), md.address_of(keys["gate"]), "sim", "sim", scope,
                 days=14, now=T0, intent=intent)
    return md.sign(m, keys["owner"])


# ---------------------------------------------------------------- intent

def test_intent_is_inside_the_signed_text(keys):
    s = signed(keys, intent=INTENT)
    assert s["mandate"]["intent"] == INTENT
    assert md.verify(s) == []
    s["mandate"]["intent"]["purpose"] = "Anything goes."
    assert md.verify(s), "editing the purpose after signing must break the signature"


def test_intent_changes_no_rule(keys):
    assert md.rules(signed(keys, intent=INTENT)) == md.rules(signed(keys))


def test_intent_keeps_only_its_two_fields_and_drops_empty_ones(keys):
    s = signed(keys, intent={"purpose": "  ", "horizon": "a year", "max_order_usd": 1_000_000})
    assert s["mandate"]["intent"] == {"horizon": "a year"}
    assert "intent" not in signed(keys, intent={"purpose": "", "horizon": None})["mandate"]


def test_a_mandate_without_intent_is_unchanged(keys):
    assert "intent" not in signed(keys)["mandate"]


# ---------------------------------------------------------------- templates

def gate_for(tmp_path, keys, scope, positions=None):
    s = signed(keys, scope=scope)
    md.save(s, str(tmp_path / "mandate.json"))
    broker = ag.SimBroker(str(tmp_path / "state"), 10_000, lambda: PRICES)
    if positions:
        broker._save({"cash": 10_000, "positions": positions})
    clock = iter(T0 + 60 * i for i in range(1, 1000))
    cfg = {"state_dir": str(tmp_path / "state"), "mandate": str(tmp_path / "mandate.json"), "gate_key": keys["gate"]}
    return ag.Gate(cfg, broker, clock=lambda: next(clock))


def test_templates_scale_with_the_account():
    assert mt.scope("trial", 10_000) == {"max_order_usd": 100, "max_position_usd": 500, "max_daily_loss_usd": 100,
                                         "max_orders_per_day": 5}
    assert mt.scope("trial", 50_000)["max_order_usd"] == 500
    assert mt.scope("long-only", 10_000, ["spy", "AAPL"])["allow"] == ["AAPL", "SPY"]
    with pytest.raises(ValueError):
        mt.scope("yolo", 10_000)
    with pytest.raises(ValueError):
        mt.scope("trial", 0)


def test_long_only_template_refuses_a_short(tmp_path, keys):
    g = gate_for(tmp_path, keys, mt.scope("long-only", 10_000, ["AAPL", "SPY"]))
    assert g.place("AAPL", "sell", usd=100)["decision"] == "block"
    assert g.place("AAPL", "buy", usd=200)["decision"] == "allow"
    assert g.place("AAPL", "sell", usd=200)["decision"] == "allow"     # selling what it holds


def test_wind_down_template_only_lets_positions_shrink(tmp_path, keys):
    g = gate_for(tmp_path, keys, mt.scope("wind-down", 10_000, ["AAPL", "SPY"]), positions={"AAPL": 4.0})
    assert g.place("SPY", "buy", usd=100)["decision"] == "block"
    assert g.place("AAPL", "buy", usd=100)["decision"] == "block"
    e = g.place("AAPL", "sell", qty=2.0)                                 # $500, inside the $500 order cap
    assert e["decision"] == "allow"
    assert g.place("AAPL", "sell", qty=2.0)["decision"] == "allow"
    assert g.broker.account()["positions"] == {}


def test_every_template_is_a_valid_mandate_scope(keys):
    for name in mt.TEMPLATES:
        s = signed(keys, scope=mt.scope(name, 10_000, ["AAPL"]))
        assert md.verify(s) == []
        assert md.rules(s)["allow"] == ["AAPL"]


# ---------------------------------------------------------------- ScopeOfAutonomy

def test_scope_of_autonomy_carries_the_limits_and_the_end(keys):
    s = signed(keys, intent=INTENT)
    r = md.scope_of_autonomy(s)
    assert set(r) >= {"allowed_tools", "latest_time", "max_cost", "tool_constraints", "additional_details",
                      "ending_condition"}
    assert r["latest_time"] == s["mandate"]["expires"] == r["ending_condition"]["latest_time"]
    assert r["tool_constraints"]["place_order"] == s["mandate"]["scope"]
    assert r["max_cost"]["usd"] == SCOPE["max_daily_loss_usd"]
    assert "place_order" in r["allowed_tools"]
    assert INTENT["purpose"] in r["additional_details"] and md.mandate_hash(s) in r["additional_details"]
    json.dumps(r)


def test_scope_of_autonomy_lists_exactly_the_gate_servers_tools():
    pytest.importorskip("mcp")
    import asyncio
    import gate_server
    names = sorted(t.name for t in asyncio.run(gate_server.mcp.list_tools()))
    assert names == sorted(md.GATE_TOOLS)
