import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

pytest.importorskip("eth_account")

import agent_gate as ag  # noqa: E402
import mandate as md  # noqa: E402

PRICES = {"BTC": 100_000.0, "ETH": 4_000.0, "SOL": 200.0}
T0 = 1_790_000_000.0  # 2026-09-21, a fixed clock so windows are deterministic


@pytest.fixture
def keys(tmp_path):
    owner, gate, other = (str(tmp_path / n) for n in ("owner.key", "gate.key", "other.key"))
    for p in (owner, gate, other):
        md.keygen(p)
    return {"owner": owner, "gate": gate, "other": other}


def signed_mandate(keys, days=30, now=T0, **scope):
    sc = {"allow": ["BTC", "ETH"], "max_order_usd": 500, "max_daily_loss_usd": 200, "max_orders_per_day": 5}
    sc.update(scope)
    m = md.draft(md.address_of(keys["owner"]), md.address_of(keys["gate"]), "sim", "sim", sc, days=days, now=now)
    return md.sign(m, keys["owner"])


def make_gate(tmp_path, keys, signed, clock):
    path = str(tmp_path / "mandate.json")
    md.save(signed, path)
    cfg = dict(ag.DEFAULTS, state_dir=str(tmp_path / "state"), mandate=path, gate_key=keys["gate"],
               allow=["BTC", "ETH", "SOL"], max_order_usd=1_000_000)  # looser config rules must be ignored
    return ag.Gate(cfg, ag.SimBroker(cfg["state_dir"], 10_000, lambda: PRICES), clock=clock)


def test_sign_verify_and_tamper(keys):
    s = signed_mandate(keys)
    assert md.verify(s, now=T0 + 60, agent=md.address_of(keys["gate"])) == []
    loose = json.loads(json.dumps(s))
    loose["mandate"]["scope"]["max_order_usd"] = 1_000_000
    assert any("not by the issuer" in p for p in md.verify(loose))


def test_signed_by_someone_else_is_rejected(keys):
    m = signed_mandate(keys)["mandate"]
    forged = md.sign(m, keys["other"])
    assert any("not by the issuer" in p for p in md.verify(forged))


def test_window_and_agent_binding(keys):
    s = signed_mandate(keys, days=1)
    assert any("not valid before" in p for p in md.verify(s, now=T0 - 10))
    assert any("expired" in p for p in md.verify(s, now=T0 + 2 * 86400))
    assert any("this gate's key" in p for p in md.verify(s, agent=md.address_of(keys["other"])))


def test_gate_refuses_a_mandate_for_another_key(tmp_path, keys):
    s = signed_mandate(keys)
    path = str(tmp_path / "m.json")
    md.save(s, path)
    cfg = dict(ag.DEFAULTS, state_dir=str(tmp_path / "st"), mandate=path, gate_key=keys["other"])
    with pytest.raises(SystemExit):
        ag.Gate(cfg, ag.SimBroker(cfg["state_dir"], 10_000, lambda: PRICES))


def test_mandate_rules_replace_config_rules_and_audit_passes(tmp_path, keys):
    t = [T0 + 3600]
    g = make_gate(tmp_path, keys, signed_mandate(keys), lambda: t[0])
    assert g.place("BTC", "buy", usd=300)["decision"] == "allow"
    sol = g.place("SOL", "buy", usd=100)  # allowed by the config, not by the signed mandate
    assert sol["decision"] == "block" and any("allow list" in r for r in sol["reasons"])
    big = g.place("ETH", "buy", usd=900)
    assert big["decision"] == "block"
    rows = g.ledger.read()
    assert rows[0]["kind"] == "mandate" and all(r.get("gate_sig") for r in rows)
    a = ag.audit(rows)
    assert a["ok"], a["problems"]
    assert a["orders_allowed"] == 1 and a["orders_rechecked"] == 1 and a["mandates"] == 1


def test_rewriting_the_whole_file_without_the_gate_key_is_caught(tmp_path, keys):
    g = make_gate(tmp_path, keys, signed_mandate(keys), lambda: T0 + 3600)
    g.place("ETH", "buy", usd=900)  # blocked
    rows = g.ledger.read()
    # a forger flips the refusal to an allow and recomputes every hash: the chain is consistent again
    rows[1]["decision"], rows[1]["reasons"] = "allow", []
    prev = ag.GENESIS
    for r in rows:
        r["prev"] = prev
        r["hash"] = ag.entry_hash(prev, r)
        prev = r["hash"]
    a = ag.audit(rows)
    assert a["chain_ok"] and not a["ok"]
    assert any("not by the mandate's agent" in p for p in a["problems"])
    assert any("rules say no" in p for p in a["problems"])


def test_a_gate_that_lies_with_its_own_key_is_caught(tmp_path, keys):
    """The gate key holder logs an over-limit order as allowed: signatures pass, the re-check does not."""
    g = make_gate(tmp_path, keys, signed_mandate(keys), lambda: T0 + 3600)
    g.place("BTC", "buy", usd=300)
    h = md.mandate_hash(g.mandate)
    g._append({"kind": "order", "ts": "x", "ts_unix": T0 + 3700, "mandate_hash": h, "decision": "allow",
               "reasons": [], "request": {"symbol": "BTC", "side": "buy", "qty": 0.05, "usd": 5000, "price": 100000},
               "ctx": {"price": 100000.0, "position": 0.0, "loss_today": 0.0, "orders_today": 1},
               "equity_before": 10000, "equity_after": 10000})
    a = ag.audit(g.ledger.read())
    assert not a["ok"] and any("single-order limit" in p for p in a["problems"])


def test_expired_mandate_blocks_everything(tmp_path, keys):
    t = [T0 + 3600]
    g = make_gate(tmp_path, keys, signed_mandate(keys, days=1), lambda: t[0])
    assert g.place("BTC", "buy", usd=100)["decision"] == "allow"
    t[0] = T0 + 2 * 86400
    e = g.place("BTC", "buy", usd=100)
    assert e["decision"] == "block" and any("expired" in r for r in e["reasons"])
    assert ag.audit(g.ledger.read())["ok"]


def test_revocation_blocks_and_is_recorded(tmp_path, keys):
    t = [T0 + 3600]
    s = signed_mandate(keys)
    g = make_gate(tmp_path, keys, s, lambda: t[0])
    assert g.place("BTC", "buy", usd=100)["decision"] == "allow"
    md.save(md.revoke(s, keys["owner"], now=t[0] + 10), g.cfg["mandate"] + ".revoked")
    t[0] += 60
    e = g.place("BTC", "buy", usd=100)
    assert e["decision"] == "block" and any("revoked" in r for r in e["reasons"])
    rows = g.ledger.read()
    assert any(r["kind"] == "revocation" for r in rows)
    assert ag.audit(rows)["ok"]


def test_revocation_by_someone_else_is_ignored(tmp_path, keys):
    s = signed_mandate(keys)
    g = make_gate(tmp_path, keys, s, lambda: T0 + 3600)
    md.save(md.revoke(s, keys["other"], now=T0 + 3000), g.cfg["mandate"] + ".revoked")
    assert g.place("BTC", "buy", usd=100)["decision"] == "allow"


def test_sides_rule_blocks_shorting_but_not_closing():
    rules = {"allow": ["BTC"], "sides": ["buy"], "max_order_usd": 1e9}
    ctx = {"price": 100.0, "position": 0.0, "loss_today": 0.0, "orders_today": 0}
    assert any("sell orders" in r for r in ag.check({"symbol": "BTC", "side": "sell", "qty": 1}, ctx, rules))
    held = dict(ctx, position=2.0)
    assert ag.check({"symbol": "BTC", "side": "sell", "qty": 1}, held, rules) == []


def test_unlogged_fills_are_reported(monkeypatch):
    import hyperliquid.info

    class FakeInfo:
        def __init__(self, *a, **k):
            pass

        def user_fills_by_time(self, owner, start):
            return [{"oid": 11}, {"oid": 12}, {"oid": 99}]

    monkeypatch.setattr(hyperliquid.info, "Info", FakeInfo)
    rows = [{"ts_unix": T0, "fill": {"oid": 11}}, {"ts_unix": T0 + 1, "fill": {"oid": 12}}]
    out = ag.hl_unlogged_fills(rows, "0xowner")
    assert out["unlogged_order_ids"] == ["99"] and not out["complete"]


def test_old_unsigned_ledgers_still_verify(tmp_path):
    cfg = dict(ag.DEFAULTS, state_dir=str(tmp_path))
    g = ag.Gate(cfg, ag.SimBroker(str(tmp_path), 10_000, lambda: PRICES))
    g.place("BTC", "buy", usd=100)
    rows = g.ledger.read()
    assert "gate_sig" not in rows[0] and ag.verify_chain(rows)["ok"] and ag.audit(rows)["ok"]
