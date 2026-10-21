import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mandate_text as mt  # noqa: E402

FULL_ZH = "只做苹果和 SPY，单笔不超过 500 美元，一天最多亏 200 美元，每只股票最多拿 2000 美元，一天最多下 20 笔，有效期两周。"


def test_full_chinese_sentence():
    r = mt.parse(FULL_ZH)
    assert r["scope"] == {"allow": ["AAPL", "SPY"], "max_order_usd": 500, "max_daily_loss_usd": 200,
                          "max_position_usd": 2000, "max_orders_per_day": 20}
    assert r["days"] == 14 and not r["missing"] and not r["unread"]
    words = {c["field"]: c["words"] for c in r["cites"]}
    assert words["max_order_usd"] == "单笔不超过 500" and words["days"] == "有效期两周"


def test_chinese_numerals_units_and_no_short():
    r = mt.parse("只买英伟达和特斯拉，每笔最多两千，日亏不超过五百，每只最多一万五，不做空，一个月有效")
    assert r["scope"]["allow"] == ["NVDA", "TSLA"]
    assert (r["scope"]["max_order_usd"], r["scope"]["max_daily_loss_usd"], r["scope"]["max_position_usd"]) == (2000, 500, 15000)
    assert r["scope"]["sides"] == ["buy"] and r["days"] == 30


@pytest.mark.parametrize("s,v", [("五百", 500), ("两千", 2000), ("一万五", 15000), ("三千五", 3500), ("三千五百", 3500),
                                 ("二十", 20), ("十五", 15), ("一万", 10000)])
def test_cn_number(s, v):
    assert mt.cn_number(s) == v


@pytest.mark.parametrize("tok,v", [("$1,000", 1000), ("1.5千", 1500), ("1万", 10000), ("5k", 5000), ("500", 500)])
def test_to_number(tok, v):
    assert mt.to_number(tok) == v


def test_english_sentence_and_a_comma_inside_a_number():
    r = mt.parse("Only AAPL and QQQ, max $1,000 per order, lose at most $300 a day, 10 trades per day, for 30 days")
    assert r["scope"] == {"allow": ["AAPL", "QQQ"], "max_order_usd": 1000, "max_daily_loss_usd": 300,
                          "max_orders_per_day": 10}
    assert r["days"] == 30 and r["missing"] == ["max_position_usd"] and not r["unread"]


def test_the_day_in_a_daily_rule_is_not_read_as_the_validity():
    r = mt.parse("一天最多亏 200，单笔 500")
    assert r["days"] == 14 and "default_days" in r["notes"]


def test_negated_symbol_is_not_allowed_and_is_reported():
    r = mt.parse("别碰特斯拉，单笔 1万，每天亏不能超过1.5千")
    assert "allow" not in r["scope"] and "allow" in r["missing"]
    assert "denied_symbols:TSLA" in r["notes"]
    assert r["scope"]["max_order_usd"] == 10000 and r["scope"]["max_daily_loss_usd"] == 1500


def test_vague_words_are_reported_not_guessed():
    r = mt.parse("我想稳一点，帮我赚钱")
    assert r["scope"] == {}
    assert r["unread"] == ["我想稳一点", "帮我赚钱"]
    assert set(r["missing"]) == {"allow", "max_order_usd", "max_daily_loss_usd", "max_position_usd"}


def test_parsed_scope_feeds_the_examples():
    import mandate_examples as mx
    cases = mx.examples(mt.parse(FULL_ZH)["scope"])
    assert [c["decision"] for c in cases] == ["allow", "block", "block", "block", "block", "allow", "block"]


PARITY = [
    FULL_ZH,
    "只买英伟达和特斯拉，每笔最多两千，日亏不超过五百，每只最多一万五，不做空，一个月有效",
    "Only AAPL and QQQ, max $1,000 per order, lose at most $300 a day, 10 trades per day, for 30 days",
    "Only AAPL, each order at most $800, daily loss $250, position $3,000, no shorting",
    "别碰特斯拉，单笔 1万，每天亏不能超过1.5千",
    "我想稳一点，帮我赚钱",
    "只做比特币和以太坊，单笔 300，持仓不超过 5千，10 天内有效",
    "标普和纳指，一笔不超过 2k，当天亏损最多 400，每天最多 5 单",
]


def test_browser_parser_matches_python():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    js = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "assets", "mandate_text.js"))
    script = ("const m=require(process.argv[1]);const s=JSON.parse(require('fs').readFileSync(0,'utf8'));"
              "process.stdout.write(JSON.stringify(s.map(x=>m.parse(x))))")
    out = subprocess.run([node, "-e", script, js], input=json.dumps(PARITY), capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    assert json.loads(out) == [mt.parse(t) for t in PARITY]


def test_cli_draft_from_a_sentence(tmp_path, capsys):
    pytest.importorskip("eth_account")
    import agent_gate as ag
    import mandate as md
    md.keygen(str(tmp_path / "gate.key"))
    (tmp_path / "gate.json").write_text('{"broker":"sim","state_dir":".","mandate":"mandate.json","gate_key":"gate.key"}',
                                        encoding="utf-8")
    owner = "0x335c6301674485042D88523CDb16930222f90B41"
    ag.main(["mandate", "draft", "--config", str(tmp_path / "gate.json"), "--issuer", owner, "--text", FULL_ZH])
    d = md.load(str(tmp_path / "mandate.json.unsigned.json"))
    assert d["scope"]["allow"] == ["AAPL", "SPY"] and d["scope"]["max_position_usd"] == 2000
    assert md.parse_iso(d["expires"]) - md.parse_iso(d["not_before"]) == 14 * 86400
    with pytest.raises(SystemExit):
        ag.main(["mandate", "draft", "--config", str(tmp_path / "gate.json"), "--issuer", owner, "--text", "帮我稳稳赚钱"])
