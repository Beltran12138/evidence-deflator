"""docs/assets/journal.js under Node: parsing, weekly returns with quiet weeks, and the best-slice penalty.

The score itself is anchored on src/hl_wallet.py (an independent implementation), not on hl.js."""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import hl_wallet  # noqa: E402

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")


def js(code):
    src = "const J = require(%s);\n" % json.dumps(os.path.join(ROOT, "docs", "assets", "journal.js").replace("\\", "/")) + code
    out = subprocess.run([NODE, "-e", src], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_money_and_dates_from_common_exports():
    r = js("""console.log(JSON.stringify({
      m: ['$1,234.50', '(12.30)', '-7', '1.234,50 €', '', 'abc', '+3.5'].map(J.money),
      d: ['2026-03-02', '03/02/2026 4:05 PM', '02.03.2026', '2026-03-02T09:30:00'].map(J.when)}))""")
    assert r["m"] == [1234.5, -12.3, -7, 1234.5, None, None, 3.5]
    day = 1772409600000  # 2026-03-02 00:00 UTC
    assert r["d"][0] == day and r["d"][2] == day
    assert r["d"][1] == day + (16 * 60 + 5) * 60000
    assert r["d"][3] == day + (9 * 60 + 30) * 60000


def test_csv_quotes_and_column_guess():
    r = js(r"""const csv = 'Symbol,"Close Date",Setup,"Net P&L"\nAAPL,2026-03-02,"Gap, long","$1,000.00"\nMSFT,2026-03-09,Breakout,(250)\n';
      const p = J.parseCSV(csv); console.log(JSON.stringify({p, g: J.guessColumns(p.header, p.rows)}))""")
    assert r["p"]["header"] == ["Symbol", "Close Date", "Setup", "Net P&L"]
    assert r["p"]["rows"][0] == ["AAPL", "2026-03-02", "Gap, long", "$1,000.00"]
    assert r["g"] == {"pnl": 3, "date": 1}


def test_quiet_weeks_count_as_zero_and_score_matches_python():
    # Trades in weeks 0, 1 and 5 of a 10-week span (2026-01-05 is a Monday).
    pnl = [300, -100, 0, 0, 0, 250, 0, 0, 0, -50]
    weeks = [(i, p) for i, p in enumerate(pnl) if p]
    trades = [{"t": 1767571200000 + i * 7 * 86400000 + 3600000, "pnl": p} for i, p in weeks]
    trades.append({"t": 1767571200000 + 9 * 7 * 86400000, "pnl": 0})  # extends the span to week 9
    r = js("const L = %s; const w = J.weekly(L, 10000); console.log(JSON.stringify({w, c: J.check(L, 10000)}))" % json.dumps(trades))
    assert [x[0] for x in r["w"]] == [p / 10000 for p in pnl]
    assert r["c"]["score"]["t"] == hl_wallet.score([(p / 10000, 1.0) for p in pnl])["t"]


def test_best_of_many_noise_slices_is_held_to_the_pool_bar():
    # 40 setups of pure noise over 60 weeks: the best one usually looks good alone, never against 40.
    r = js("""let s = 7; const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648 - 0.5;
      const L = [];
      for (let k = 0; k < 40; k++) for (let w = 0; w < 60; w++)
        L.push({t: 1767571200000 + w * 7 * 86400000 + k * 1000, pnl: rnd() * 200, row: {0: 'setup' + k}});
      L.sort((a, b) => a.t - b.t);
      const sl = J.slices(L, 100000, 0, 1);
      console.log(JSON.stringify({n: sl.scoredCount, pool: sl.pool, bar: sl.bar, bestT: sl.best.t, v: sl.verdictBest.key,
                                  blind: sl.luckBestBlind, picked: sl.luckBestPicked}))""")
    assert r["n"] == 40 and r["pool"] == 40
    assert r["bar"] == pytest.approx(hl_wallet.bar(40), abs=0.01)
    assert r["v"] in ("clears_single", "luck")  # never clears_board on noise here
    assert r["picked"] > r["blind"]
