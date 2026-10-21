"""Diff docs/assets/hl.js against tools/build_hl_board.py on cached portfolios.

    python tools/check_hl_parity.py --cache DIR

DIR is the --cache directory of build_hl_board.py (portfolio/*.json). Needs node.
Exits 1 on any mismatch in weeks, Sharpe, t, flags, luck, the BTC-adjusted t (if the cache has
candles-btc.json) or the best-of-N bar.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_hl_board as py  # noqa: E402

JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "assets", "hl.js")
NODE = r"""
const HL = require(process.argv[1]);
const inp = JSON.parse(require('fs').readFileSync(0, 'utf8')), files = inp.files, btc = inp.btc;
const out = {};
for (const f of files) {
  const pf = JSON.parse(require('fs').readFileSync(f, 'utf8'));
  const w = HL.weeklyReturns(pf), sc = HL.score(w.rets);
  out[f] = Object.assign(sc, {flags: HL.flags(pf, w.rets, w.counted)}, btc.length ? HL.alphaVs(w.rets, HL.benchReturns(btc, w.iv)) : {},
                         {luck: sc.t == null ? null : Math.round(HL.luck(sc.t, 47254) * 1e6) / 1e6},
                         {recent_t: HL.score(HL.recentReturns(pf)).t});
}
out.__bars = [1, 41, 47254, 23376].map(n => Math.round(HL.bar(n) * 100) / 100);
console.log(JSON.stringify(out));
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.cache, "portfolio", "*.json")))
    if not files:
        sys.exit("no cached portfolios")
    cp = os.path.join(a.cache, "candles-btc.json")
    btc = json.load(open(cp, encoding="utf-8")) if os.path.exists(cp) else []
    res = subprocess.run(["node", "-e", NODE, os.path.abspath(JS)], input=json.dumps({"files": files, "btc": btc}),
                         capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    bad = 0
    for f in files:
        with open(f, encoding="utf-8") as fh:
            pf = dict(json.load(fh))
        iv, _, _, counted = py.weekly_returns(pf, with_times=True)
        rets = [(r, w) for r, w, _, _ in iv]
        p, j = dict(py.score(rets), flags=py.flags(pf, rets, counted)), js[f]
        p["luck"] = None if p["t"] is None else round(py.luck(p["t"], 47254), 6)
        p["recent_t"] = py.score(py.recent_returns(pf))["t"]
        keys = ["weeks", "sharpe", "t_student", "dof", "t", "flags", "luck", "recent_t"]
        if btc:
            p.update(py.alpha_vs(iv, py.bench_returns(btc, iv)))
            keys += ["t_btc", "beta_btc", "n_btc"]
        for k in keys:
            # luck goes through HL.cdf, a 7-digit approximation that n = 47,254 magnifies; display needs 2 digits
            same = (p[k] is None) == (j.get(k) is None) and (p[k] is None or abs(p[k] - j[k]) <= 0.01 * max(p[k], 1e-4)) if k == "luck" else p.get(k) == j.get(k)
            if not same:
                bad += 1
                print("MISMATCH", os.path.basename(f), k, p.get(k), j.get(k))
                break
    pb = [round(py.bar(n), 2) for n in (1, 41, 47254, 23376)]
    if pb != js["__bars"]:
        bad += 1
        print("MISMATCH bars", pb, js["__bars"])
    print(f"{len(files)} portfolios, bars {pb}: {'OK' if not bad else str(bad) + ' mismatches'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
