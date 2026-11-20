"""Share of winning weeks and skew of weekly returns, and the short_vol_shape flag built on them
(docs/data/hl/ALERT_LIST_PREREG.md, council 2026-11-19: t can rate a short-volatility record as
strong until its large loss). Checked on hand-built records and against the browser copy.
"""
import json
import os
import random
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import hl_wallet as hw  # noqa: E402

PF = {"allTime": {"accountValueHistory": [], "pnlHistory": []}}


def test_short_vol_record_is_flagged_and_t_still_likes_it():
    # 50 weeks: +1% most weeks, -6% every tenth: mostly winning, negatively skewed, still positive
    rets = [(-0.06 if i % 10 == 9 else 0.01, 1.0) for i in range(50)]
    sh = hw.shape(rets)
    assert sh["up"] == 0.9 and sh["skew"] < -1
    assert "short_vol_shape" in hw.flags(PF, rets, 0.0)


def test_mirror_image_is_not_flagged():
    rets = [(0.06 if i % 10 == 9 else -0.01, 1.0) for i in range(50)]
    sh = hw.shape(rets)
    assert sh["skew"] > 1 and sh["up"] == 0.1
    assert "short_vol_shape" not in hw.flags(PF, rets, 0.0)


def test_negative_skew_without_mostly_winning_weeks_is_not_flagged():
    rng = random.Random(1)
    rets = [(rng.gauss(0, 0.01) - (0.08 if i % 12 == 0 else 0), 1.0) for i in range(60)]
    sh = hw.shape(rets)
    assert sh["skew"] < -1 and sh["up"] < 0.7
    assert "short_vol_shape" not in hw.flags(PF, rets, 0.0)


def test_long_intervals_are_scaled_not_counted_as_outliers():
    # the same weekly drift and noise, but one 4-week interval carrying 4 weeks of drift
    base = [(0.01 + (0.002 if i % 2 else -0.002), 1.0) for i in range(30)]
    sh_a = hw.shape(base)
    sh_b = hw.shape(base + [(0.04, 4.0)])
    assert abs(sh_b["skew"] - sh_a["skew"]) < 0.5


def test_too_short_and_flat():
    assert hw.shape([(0.01, 1.0)] * 7) is None
    assert hw.shape([(0.01, 1.0)] * 10)["skew"] is None


JS = r"""
const HL = require(process.argv[2]);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const pf = [['allTime', {accountValueHistory: [], pnlHistory: []}]];
process.stdout.write(JSON.stringify(cases.map(c => [HL.shape(c), HL.flags(pf, c, 0)])));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_copy_agrees(tmp_path):
    script = tmp_path / "run.js"
    script.write_text(JS)
    cases = [[[-0.06 if i % 10 == 9 else 0.01, 1.0] for i in range(50)]]
    for seed in range(30):
        rng = random.Random(seed)
        n = rng.randint(5, 120)
        crash = rng.random() < 0.5
        cases.append([[rng.gauss(0.01, 0.005) - (0.1 if crash and rng.random() < 0.08 else 0), rng.choice([1.0, 1.0, 2.0, 3.5])]
                      for _ in range(n)])
    res = subprocess.run(["node", str(script), os.path.abspath(os.path.join(ROOT, "docs", "assets", "hl.js"))],
                         input=json.dumps(cases), capture_output=True, text=True, check=True)
    flagged = 0
    for c, (j, jf) in zip(cases, json.loads(res.stdout)):
        rets = [tuple(x) for x in c]
        p = hw.shape(rets)
        assert (p is None) == (j is None)
        if p:
            assert abs(p["up"] - j["up"]) <= 1e-4
            assert (p["skew"] is None) == (j["skew"] is None)
            if p["skew"] is not None:
                assert abs(p["skew"] - j["skew"]) <= 1e-3
        assert hw.flags(PF, rets, 0.0) == jf
        flagged += "short_vol_shape" in jf
    assert flagged >= 2  # the cases exercise the flag, not only its absence
