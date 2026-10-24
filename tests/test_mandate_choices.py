"""Rules from choices (docs/assets/mandate_choices.js), checked against the Python rule check.

A simulated owner with hidden limits answers each question "allow" or "block" the way the gate would under
those hidden limits. The dialog must end, and under the rules it produces, the Python check
(agent_gate.check, not the JS port) must give every answered order the owner's own decision.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import agent_gate as ag  # noqa: E402

JS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "assets", "mandate_choices.js"))
PRICE = 100.0

# The owner answers with the gate's own check under their hidden limits, so "the answer" and "the rule
# produced" are compared through the Python check from two independent scopes.
DRIVER = r"""
const C=require(process.argv[1]);const fs=require('fs');
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
function decide(q,h){ // the simulated owner: allow iff the order passes their hidden limits
  const o=q.order,s=q.situation;
  if(h.max_order_usd!=null && o.usd>h.max_order_usd) return false;
  if(h.max_daily_loss_usd!=null && s.loss_today>=h.max_daily_loss_usd) return false;
  if(h.max_position_usd!=null && s.position_usd+o.usd>h.max_position_usd) return false;
  return true;}
const out=cases.map(h=>{let st=C.start('AAPL',['AAPL','SPY']);const asked=[];let n;let guard=0;
  while((n=C.next(st))&&guard++<50){const a=decide(n.q,h);asked.push({field:n.field,amount:n.amount,q:n.q,allow:a});C.answer(st,n.field,n.amount,a);}
  return {asked,result:C.result(st)};});
process.stdout.write(JSON.stringify(out));
"""

HIDDEN = [
    {"max_order_usd": 700, "max_daily_loss_usd": 300, "max_position_usd": 3000},
    {"max_order_usd": 100, "max_daily_loss_usd": 50, "max_position_usd": 500},
    {"max_order_usd": 9999, "max_daily_loss_usd": 9999, "max_position_usd": 99999},
    {"max_order_usd": 50, "max_daily_loss_usd": 200, "max_position_usd": 2000},
    {"max_order_usd": 1200, "max_daily_loss_usd": 160, "max_position_usd": 12000},
]
# HIDDEN[4] has limits between ladder levels: the order limit rounds down (1,000), the loss limit rounds
# up to the first level the owner stops at (200), and every answer still holds.


def run(cases):
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    out = subprocess.run([node, "-e", DRIVER, JS], input=json.dumps(cases), capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    return json.loads(out)


def py_decision(q, scope):
    o, s = q["order"], q["situation"]
    order = {"symbol": o["symbol"], "side": o["side"], "qty": o["usd"] / PRICE}
    ctx = {"price": PRICE, "position": s["position_usd"] / PRICE, "loss_today": s["loss_today"],
           "orders_today": s["orders_today"]}
    return not ag.check(order, ctx, dict(scope))


def test_every_answer_is_kept_by_the_rules_produced():
    for hidden, r in zip(HIDDEN, run(HIDDEN)):
        scope = r["result"]["scope"]
        if "order_all_blocked" in r["result"]["notes"]:  # no order size passes: nothing to sign, see the last test
            assert "max_order_usd" not in scope
            continue
        for a in r["asked"]:
            assert py_decision(a["q"], scope) == a["allow"], (hidden, a, scope)


def test_few_questions_and_limits_within_one_step():
    r = run([HIDDEN[0]])[0]
    assert len(r["asked"]) <= 12
    sc = r["result"]["scope"]
    assert sc["max_order_usd"] == 500                # largest ladder amount under 700
    assert sc["max_daily_loss_usd"] == 300           # owner stops at a loss of 300, a ladder level
    assert sc["max_position_usd"] == 3000            # holding 3,000 + 100 is stopped, 2,000 + 100 passes
    assert sc["allow"] == ["AAPL", "SPY"]
    words = {c["field"]: c["words"] for c in r["result"]["cites"]}
    assert "放行" in words["max_order_usd"] and "拦下" in words["max_order_usd"]


def test_an_owner_who_allows_everything_is_told_so():
    r = run([HIDDEN[2]])[0]
    assert "order_all_allowed" in r["result"]["notes"]
    assert "max_daily_loss_usd_all_allowed" in r["result"]["notes"]
    assert "max_daily_loss_usd" not in r["result"]["scope"]


def test_an_owner_who_blocks_every_order_size_gets_no_order_limit_and_no_further_questions():
    r = run([HIDDEN[3]])[0]
    assert "order_all_blocked" in r["result"]["notes"]
    assert {a["field"] for a in r["asked"]} == {"max_order_usd"}
