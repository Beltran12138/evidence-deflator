"""Recompute every data-dependent number on the Macau deck (docs/macau.html) and
flag the ones the deck no longer shows. Run before the talk:

    python tools/check_macau.py            # uses docs/data/hl/latest.json + a live portfolio fetch
    python tools/check_macau.py --data F   # another snapshot (e.g. git show <sha>:docs/data/hl/latest.json)
    python tools/check_macau.py --write-strip [--data F]   # rewrite the slide-02 animation data, then exit

Prints each fact, the string the deck should contain, and OK / MISSING.
"""
import json, os, re, sys
from datetime import datetime, timezone

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import hl_wallet as hw  # noqa: E402

STORY = "0x4ec8fe22a531a96c8a846aaf5cbef73202649a80"  # the slide-01 wallet


def money(x, zh=False):
    if zh:
        return f"${x / 1e8:.2f} 亿" if abs(x) >= 1e8 else f"${x / 1e4:.0f} 万"
    sign = "−" if x < 0 else ""
    return sign + (f"${abs(x) / 1e9:.2f}B" if abs(x) >= 1e9 else f"${abs(x) / 1e6:.0f}M")


def strip_line(hl):
    """The slide-02 rank-to-evidence animation: PnL top 100 as [rank, PnL in $M, t]."""
    pnl = hl["boards"]["pnl"]
    rows = [[r["rank"], round(r["pnl_all_time"] / 1e6), None if r["t"] is None else round(r["t"], 2)] for r in pnl["rows"]]
    data = {"day": hl["fetched"][:10], "n": pnl["ranked_from"], "bar": pnl["t_bar_best_of_n"], "rows": rows}
    return "const STRIP=" + json.dumps(data, separators=(",", ":")) + ";"


def main():
    args = sys.argv[1:]
    src = args[args.index("--data") + 1] if "--data" in args else os.path.join(ROOT, "docs", "data", "hl", "latest.json")
    hl = json.load(open(src, encoding="utf-8"))
    deck_path = os.path.join(ROOT, "docs", "macau.html")
    deck = open(deck_path, encoding="utf-8").read()
    if "--write-strip" in args:
        new, k = re.subn(r"const STRIP=.*?;\n", lambda m: strip_line(hl) + "\n", deck, count=1)
        if not k:
            sys.exit("no 'const STRIP=' line in the deck")
        open(deck_path, "w", encoding="utf-8", newline="").write(new)
        print("wrote STRIP from", hl["fetched"])
        return
    pnl, roi = hl["boards"]["pnl"], hl["boards"]["roi30"]
    N, day = pnl["ranked_from"], hl["fetched"][:10]
    rank = next((r["rank"] for r in pnl["rows"] if r["address"] == STORY), None)
    top_t = max((r for r in pnl["rows"] if r["t"] is not None), key=lambda r: r["t"])

    pf = hw.fetch_portfolio(STORY)
    rets, start, end, counted = hw.weekly_returns(pf)
    sc = hw.score(rets)
    losing = sum(r < 0 for r, _ in rets)
    hist = pf["allTime"]["pnlHistory"]
    av = dict((t, float(v)) for t, v in pf["allTime"]["accountValueHistory"])
    jump = max(zip(hist, hist[1:]), key=lambda p: float(p[1][1]) - float(p[0][1]))
    jump_amt = float(jump[1][1]) - float(jump[0][1])
    jump_av = av.get(jump[0][0])
    pnl_now = float(hist[-1][1])
    jday = datetime.fromtimestamp(jump[1][0] / 1000, timezone.utc).strftime("%Y-%m-%d")

    facts = [
        ("data date", day, day),
        ("board size", f"{N:,}", f"{N:,}"),
        ("best-of-N bar", f"{pnl['t_bar_best_of_n']:.2f}", f"{pnl['t_bar_best_of_n']:.2f}"),
        ("PnL top 100 at bar", f"{pnl['n_t_ge_bar']} / {pnl['scored']}", f"{pnl['n_t_ge_bar']}<small> / {pnl['scored']}"),
        ("PnL top 100 t>=2", f"{pnl['n_t_ge_2']} / {pnl['scored']}", f"{pnl['n_t_ge_2']} / {pnl['scored']}"),
        ("ROI top 100 t>=2", f"{roi['n_t_ge_2']} / {roi['scored']}", f"{roi['n_t_ge_2']} / {roi['scored']}"),
        ("ROI top 100 at bar", f"{roi['n_t_ge_bar']} / {roi['scored']}", f"{roi['n_t_ge_bar']} / {roi['scored']}"),
        ("story wallet PnL rank", str(rank), None),
        ("story wallet t", f"{sc['t']:.2f}", f"{sc['t']:.2f}".replace("-", "−")),
        ("story losing / measured", f"{losing} / {len(rets)}", f"{losing} / {len(rets)}"),
        ("story PnL in measured weeks", money(counted), money(counted)),
        ("story current PnL", money(pnl_now, zh=True), None),
        ("story jump", f"{money(jump_amt)} on {jday}", None),
        ("story account before jump", f"${jump_av:,.0f}" if jump_av is not None else "?", None),
        ("highest t in PnL top 100", f"{top_t['address']} t {top_t['t']:.2f}", top_t["address"]),
        ("ROI #1", roi["rows"][0]["address"], roi["rows"][0]["address"]),
        ("slide-02 animation data", f"{len(pnl['rows'])} rows, {day}", strip_line(hl)),
    ]
    for name, value, needle in facts:
        state = "" if needle is None else ("OK" if needle in deck else "MISSING")
        print(f"{name:30} {value:52} {state}")


if __name__ == "__main__":
    main()
