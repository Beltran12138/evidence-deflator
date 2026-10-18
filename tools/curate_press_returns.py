"""Pick one reported yearly return per fund and year from the collected press and firm reports.

    python tools/curate_press_returns.py RAW.json docs/data/ranking/hedge_funds_press.json

RAW.json holds every reported figure found, each with its source URL, a verbatim quote and the kind
of source (firm, press, aggregator). Rules, in order:
1. Leave out figures for a different vehicle: SAC Capital before Point72, Tiger Global's long-only
   fund, and D.E. Shaw's "2008: 21.3%" (other sources call 2008 its only down year; read as 2009 mislabelled).
2. Bridgewater: Pure Alpha II (18% volatility) where named, otherwise the unspecified Pure Alpha
   figure, otherwise Pure Alpha 12%. Two Sigma: Spectrum only.
3. Within a year: the firm's own figure, then press, then aggregators; among several of the same
   kind, the median.
The raw file is copied next to the output so every choice can be checked against what was left out.
"""
import json
import shutil
import statistics
import sys

KIND = {"firm": 0, "press": 1, "aggregator": 2}
NAMES = {
    "citadel_wellington": ("Citadel Wellington", "Ken Griffin", "Kensington and Wellington combined to 2014"),
    "millennium": ("Millennium Management", "Izzy Englander", None),
    "bridgewater_pure_alpha": ("Bridgewater Pure Alpha", "Ray Dalio", "Pure Alpha II where named, otherwise the fund the report names"),
    "de_shaw_composite": ("D.E. Shaw Composite", "D.E. Shaw", None),
    "elliott": ("Elliott Associates", "Paul Singer", None),
    "point72": ("Point72", "Steve Cohen", "Point72 years only; SAC Capital left out"),
    "greenlight": ("Greenlight Capital", "David Einhorn", None),
    "third_point": ("Third Point Offshore", "Dan Loeb", None),
    "two_sigma": ("Two Sigma Spectrum", "Two Sigma", None),
    "tiger_global": ("Tiger Global (flagship)", "Chase Coleman", "long-only fund left out"),
}


def keep(fid, y):
    v = (y.get("variant") or "")
    if fid == "point72" and v.startswith("SAC"):
        return False
    if fid == "tiger_global" and "long-only" in v:
        return False
    if fid == "de_shaw_composite" and y["year"] == 2008 and abs(y["net_pct"] - 21.3) < 0.01:
        return False
    if fid == "two_sigma" and v != "Spectrum":
        return False
    return True


def bw_rank(y):
    v = y.get("variant") or ""
    return 0 if "II" in v else 1 if "unspecified" in v else 2


def main():
    raw, out = sys.argv[1], sys.argv[2]
    d = json.load(open(raw, encoding="utf-8"))
    funds = []
    for f in d["funds"]:
        fid = f["id"]
        by = {}
        for y in f["years"]:
            if keep(fid, y):
                by.setdefault(int(y["year"]), []).append(y)
        years = []
        for yr in sorted(by):
            c = by[yr]
            if fid == "bridgewater_pure_alpha":
                best = min(bw_rank(y) for y in c)
                c = [y for y in c if bw_rank(y) == best]
            best = min(KIND.get(y.get("source_kind"), 3) for y in c)
            c = [y for y in c if KIND.get(y.get("source_kind"), 3) == best]
            v = statistics.median(y["net_pct"] for y in c)
            src = min(c, key=lambda y: abs(y["net_pct"] - v))
            years.append({"year": yr, "net_pct": v, "url": src["url"], "quote": src["quote"], "source_kind": src.get("source_kind"),
                          "variant": src.get("variant"), "candidates": len(by[yr])})
        name, who, note = NAMES.get(fid, (f.get("name"), f.get("manager"), None))
        funds.append({"id": fid, "name": name, "manager": who, "note": note, "years": years})
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"rules": __doc__.strip().split("\n\n", 1)[1], "funds": funds}, indent=1, ensure_ascii=False))
    shutil.copyfile(raw, out.replace(".json", "_raw.json"))
    for f in funds:
        print(f["id"], len(f["years"]), [y["year"] for y in f["years"]][:1], "…", [y["year"] for y in f["years"]][-1:])


if __name__ == "__main__":
    main()
