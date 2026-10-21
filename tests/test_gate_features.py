import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

pytest.importorskip("eth_account")

import agent_gate as ag  # noqa: E402
import mandate as md  # noqa: E402
import mandate_examples as mx  # noqa: E402

PRICES = {"AAPL": 250.0, "SPY": 700.0, "TSLA": 400.0}
T0 = 1_790_000_000.0
SCOPE = {"allow": ["AAPL", "SPY"], "sides": ["buy", "sell"], "max_order_usd": 500, "max_position_usd": 2000,
         "max_daily_loss_usd": 200, "max_orders_per_day": 20}


@pytest.fixture
def keys(tmp_path):
    out = {}
    for n in ("owner", "gate", "other"):
        out[n] = str(tmp_path / f"{n}.key")
        md.keygen(out[n])
    return out


def gate_with_mandate(tmp_path, keys, name="g1"):
    m = md.sign(md.draft(md.address_of(keys["owner"]), md.address_of(keys["gate"]), "sim", "sim", SCOPE,
                         days=14, now=T0), keys["owner"])
    d = tmp_path / name
    d.mkdir()
    md.save(m, str(d / "mandate.json"))
    cfg_path = d / "gate.json"
    cfg_path.write_text(json.dumps({"state_dir": "state", "mandate": "mandate.json", "gate_key": keys["gate"],
                                    "name": name}), encoding="utf-8")
    cfg = ag.load_config(str(cfg_path))
    clock = iter(T0 + 60 * i for i in range(1, 1000))
    g = ag.Gate(cfg, ag.SimBroker(cfg["state_dir"], 10_000, lambda: PRICES), clock=lambda: next(clock))
    return g, str(cfg_path)


# ---------------------------------------------------------------- examples

def test_examples_decisions_for_a_full_scope():
    cases = mx.examples(SCOPE)
    got = [(c["order"]["symbol"], c["order"]["side"], c["decision"]) for c in cases]
    assert got == [("AAPL", "buy", "allow"),    # ordinary
                   ("AAPL", "buy", "block"),    # $501
                   ("TSLA", "buy", "block"),    # off the list
                   ("AAPL", "buy", "block"),    # past the position limit
                   ("AAPL", "buy", "block"),    # new risk after the daily loss is hit
                   ("AAPL", "sell", "allow"),   # cutting the loss stays possible
                   ("AAPL", "buy", "block")]    # order count
    assert cases[1]["order"]["usd"] == 501
    assert "single-order limit" in cases[1]["reasons"][0]
    assert "position limit" in cases[3]["reasons"][0]


def test_examples_buy_only_scope_shows_the_short_refusal_and_skips_absent_rules():
    cases = mx.examples({"allow": ["SPY"], "sides": ["buy"], "max_order_usd": 1000, "max_daily_loss_usd": 300})
    titles = [c["title_en"] for c in cases]
    assert any("going short" in t for t in titles)
    assert not any("position limit" in t for t in titles)
    assert not any("orders already today" in t for t in titles)
    short = next(c for c in cases if "going short" in c["title_en"])
    assert short["decision"] == "block" and "sell orders are not allowed" in short["reasons"][0]


def test_examples_do_not_depend_on_the_price_used():
    a = [c["decision"] for c in mx.examples(SCOPE)]
    b = [c["decision"] for c in mx.examples(SCOPE, price_of=lambda s: 3.7)]
    assert a == b


def test_examples_follow_the_real_rule_check():
    # every example re-checked by hand through ag.check with the same numbers
    for c in mx.examples(SCOPE, price_of=PRICES.get):
        o, s = c["order"], c["situation"]
        p = PRICES[o["symbol"]]
        ctx = {"price": p, "position": s["position_usd"] / p, "loss_today": s["loss_today"],
               "orders_today": s["orders_today"]}
        assert ag.check({"symbol": o["symbol"], "side": o["side"], "qty": o["usd"] / p}, ctx, SCOPE) == c["reasons"]


def test_propose_mandate_writes_a_draft_and_a_record(tmp_path, keys, monkeypatch):
    pytest.importorskip("mcp")
    import gate_server
    g, cfg_path = gate_with_mandate(tmp_path, keys)
    monkeypatch.setattr(gate_server, "_GATE", g)
    out = gate_server.propose_mandate("只买苹果和SPY，单笔不超过500，一天最多亏200", ["aapl", "spy"], 500, 200,
                                      issuer=md.address_of(keys["owner"]))
    assert out["status"].startswith("draft")
    assert out["scope"]["allow"] == ["AAPL", "SPY"]
    assert out["text_to_sign"].startswith(md.HEADER)
    import base64
    frag = out["sign_url"].split("#m=")[1]
    assert base64.urlsafe_b64decode(frag + "=" * (-len(frag) % 4)).decode() == out["text_to_sign"]
    assert os.path.exists(g.cfg["mandate"] + ".unsigned.json")
    assert md.load(g.cfg["mandate"])["mandate"]["scope"] == SCOPE  # the signed mandate is untouched
    recs = os.listdir(os.path.join(g.cfg["state_dir"], "proposals"))
    assert len(recs) == 1


# ---------------------------------------------------------------- attestation

def run_orders(g):
    g.place("AAPL", "buy", usd=300)
    g.place("SPY", "buy", usd=5000)
    g.place("TSLA", "buy", usd=100)


def test_attestation_verifies_and_survives_a_grown_ledger(tmp_path, keys):
    g, _ = gate_with_mandate(tmp_path, keys)
    run_orders(g)
    att = ag.attest(g.ledger.read(), md.load_key(keys["gate"]), now=T0 + 3600)
    st = att["statement"]
    assert st["orders"] == {"allowed": 1, "blocked": 2, "errors": 0, "rechecked": 1}
    assert st["audit_ok"] and st["ledger"]["lines"] == 4  # mandate line + 3 orders
    assert ag.verify_attestation(att, g.ledger.read())["ok"]
    g.place("AAPL", "sell", usd=100)
    v = ag.verify_attestation(att, g.ledger.read())
    assert v["ok"] and v["covers_lines"] == 4 and v["ledger_lines_now"] == 5


def test_attestation_catches_an_edited_statement(tmp_path, keys):
    g, _ = gate_with_mandate(tmp_path, keys)
    run_orders(g)
    att = ag.attest(g.ledger.read(), md.load_key(keys["gate"]), now=T0)
    att["statement"]["orders"]["blocked"] = 0
    v = ag.verify_attestation(att, g.ledger.read())
    assert not v["ok"]
    assert any("signature recovers" in p for p in v["problems"])


def test_attestation_catches_a_rewritten_ledger(tmp_path, keys):
    g, _ = gate_with_mandate(tmp_path, keys)
    run_orders(g)
    att = ag.attest(g.ledger.read(), md.load_key(keys["gate"]), now=T0)
    rows = g.ledger.read()
    rows[2]["decision"] = "allow"
    v = ag.verify_attestation(att, rows)
    assert not v["ok"]
    assert any(p.startswith("ledger does not match") or p.startswith("orders does not match") for p in v["problems"])


def test_attestation_signed_by_another_key_is_refused(tmp_path, keys):
    g, _ = gate_with_mandate(tmp_path, keys)
    run_orders(g)
    att = ag.attest(g.ledger.read(), md.load_key(keys["other"]), now=T0)
    v = ag.verify_attestation(att, g.ledger.read())
    assert not v["ok"]
    assert any("not the gate key any recorded mandate names" in p for p in v["problems"])


def test_attestation_reports_a_failing_audit_honestly(tmp_path, keys):
    g, _ = gate_with_mandate(tmp_path, keys)
    run_orders(g)
    rows = g.ledger.read()
    del rows[-1]["gate_sig"]  # an unsigned line: the audit fails, and the attestation must say so
    att = ag.attest(rows, md.load_key(keys["gate"]), now=T0)
    assert att["statement"]["audit_ok"] is False and att["statement"]["problems"]
    assert ag.verify_attestation(att, rows)["ok"]  # a true statement of a failing audit still verifies


# ---------------------------------------------------------------- panel

def test_panel_reads_every_gate_from_its_ledger(tmp_path, keys):
    g1, p1 = gate_with_mandate(tmp_path, keys, "alpha")
    g2, p2 = gate_with_mandate(tmp_path, keys, "beta")
    run_orders(g1)
    g2.place("SPY", "buy", usd=200)
    rows = ag.panel([p1, p2], now=T0 + 3600)
    assert [r["name"] for r in rows] == ["alpha", "beta"]
    assert (rows[0]["allowed"], rows[0]["blocked"]) == (1, 2)
    assert (rows[1]["allowed"], rows[1]["blocked"]) == (1, 0)
    assert rows[0]["rules"].startswith("mandate ") and rows[0]["audit_ok"]
    assert rows[0]["allowed_today"] == 1
    html = ag.panel_html(rows, "now")
    assert "alpha" in html and "beta" in html and "audit ok" in html


def test_panel_flags_a_tampered_ledger(tmp_path, keys):
    g, p = gate_with_mandate(tmp_path, keys)
    run_orders(g)
    path = g.ledger.path
    raw = open(path, encoding="utf-8").read().replace('"decision":"block"', '"decision":"allow"', 1)
    open(path, "w", encoding="utf-8").write(raw)
    r = ag.panel([p], now=T0)[0]
    assert not r["audit_ok"] and not r["chain_ok"]


# ---------------------------------------------------------------- browser parity

PARITY_SCOPES = [
    SCOPE,
    {"allow": ["SPY"], "sides": ["buy"], "max_order_usd": 1000, "max_daily_loss_usd": 300},
    {"allow": ["BTC", "ETH"], "max_order_usd": 500, "max_daily_loss_usd": 200, "max_orders_per_day": 5},
    {"allow": [], "sides": ["sell"], "max_order_usd": 250, "max_position_usd": 900, "max_daily_loss_usd": 50},
    {"allow": ["TSLA", "NVDA", "DOGE"], "max_order_usd": 2000, "max_position_usd": 5000, "max_daily_loss_usd": 400},
]


def test_browser_examples_match_python():
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    js = os.path.join(os.path.dirname(__file__), "..", "docs", "assets", "mandate_examples.js")
    script = ("const m=require(process.argv[1]);const s=JSON.parse(require('fs').readFileSync(0,'utf8'));"
              "process.stdout.write(JSON.stringify(s.map(x=>m.examples(x).map(c=>[c.order,c.situation,c.decision]))))")
    out = subprocess.run([node, "-e", script, os.path.abspath(js)], input=json.dumps(PARITY_SCOPES),
                         capture_output=True, text=True, check=True).stdout
    js_cases = json.loads(out)
    py_cases = [[[c["order"], c["situation"], c["decision"]] for c in mx.examples(s)] for s in PARITY_SCOPES]
    assert js_cases == py_cases


def test_gate_with_an_unsigned_mandate_refuses_everything(tmp_path, keys):
    cfg = dict(ag.DEFAULTS, state_dir=str(tmp_path / "s"), mandate=str(tmp_path / "mandate.json"),
               gate_key=keys["gate"])
    g = ag.Gate(cfg, ag.SimBroker(cfg["state_dir"], 10_000, lambda: {"BTC": 100.0}), clock=lambda: T0)
    e = g.place("BTC", "buy", usd=10)
    assert e["decision"] == "block" and "none signed yet" in e["reasons"][0]


def test_sim_broker_fixed_prices_from_config(tmp_path):
    cfg = dict(ag.DEFAULTS, state_dir=str(tmp_path / "s"), prices={"aapl": 339.66})
    b = ag.make_broker(cfg)
    assert b.price("AAPL") == 339.66


def test_account_tool_says_no_rules_before_the_mandate_is_signed(tmp_path, keys, monkeypatch):
    pytest.importorskip("mcp")
    import gate_server
    cfg = dict(ag.DEFAULTS, state_dir=str(tmp_path / "s"), mandate=str(tmp_path / "mandate.json"),
               gate_key=keys["gate"])
    g = ag.Gate(cfg, ag.SimBroker(cfg["state_dir"], 10_000, lambda: {"BTC": 100.0}), clock=lambda: T0)
    monkeypatch.setattr(gate_server, "_GATE", g)
    assert "every order is refused" in gate_server.account()["rules"]
