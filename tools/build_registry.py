"""Forward registry: wallets registered through GitHub issues, scored only after registration.

Usage:
    python tools/build_registry.py --out docs/data/registry/registry.json [--cache DIR]

An entry is an issue in this repository whose title starts with "[registry]" (the form in
.github/ISSUE_TEMPLATE/register-agent.yml). The registration time is the issue's created_at,
set by GitHub. The same address registered twice keeps its earliest issue. Issues labelled
"invalid" are left out. Each wallet is scored with weekly_returns(since=registered) + score(),
the estimator behind the wallet check; nothing before registration counts.

Reads issues from the public GitHub API (GITHUB_TOKEN or GH_TOKEN, if set, raises the rate limit).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from hl_wallet import MIN_WEEKS, bar, fetch_portfolio, score, weekly_returns  # noqa: E402

REPO = "Beltran12138/evidence-deflator"
ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")
FIELDS = {"Hyperliquid wallet address": "address", "Agent name": "name", "Model and its training cutoff": "model",
          "Strategy commitment (sha256)": "commitment", "Strategies tried before this one": "trials"}


def api(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "evidence-deflator"})
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def issues():
    out, page = [], 1
    while True:
        batch = api(f"https://api.github.com/repos/{REPO}/issues?state=all&per_page=100&page={page}")
        out += [i for i in batch if "pull_request" not in i]
        if len(batch) < 100:
            return out
        page += 1


def parse_form(body):
    """Issue-form bodies are '### Label' followed by the answer; '_No response_' means empty."""
    got, label = {}, None
    for line in (body or "").splitlines():
        m = re.match(r"^###\s+(.*)$", line.strip())
        if m:
            label = FIELDS.get(m.group(1).strip())
            continue
        if label and line.strip() and line.strip() != "_No response_" and label not in got:
            got[label] = line.strip()
    return got


def entries(raw):
    seen, out = set(), []
    for i in sorted(raw, key=lambda i: i["created_at"]):
        if not i["title"].lower().startswith("[registry]"):
            continue
        if any(l["name"] == "invalid" for l in i.get("labels", [])):
            continue
        f = parse_form(i.get("body"))
        addr = (f.get("address") or "").strip()
        if not ADDR.match(addr):
            continue
        addr = addr.lower()
        if addr in seen:
            continue
        seen.add(addr)
        out.append({"address": addr, "name": f.get("name", "")[:80], "model": f.get("model", "")[:120],
                    "commitment": f.get("commitment", "")[:80], "trials_declared": f.get("trials", "")[:20],
                    "registered_at": i["created_at"], "issue": i["html_url"], "registrant": i["user"]["login"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache")
    a = ap.parse_args()
    rows = entries(issues())
    for r in rows:
        since = int(datetime.strptime(r["registered_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)
        try:
            pf = fetch_portfolio(r["address"])
            time.sleep(0.2)
            sc = score(weekly_returns(pf, since=since)[0])
            r.update({"t": sc["t"], "weeks": sc["weeks"], "error": None})
        except Exception as ex:  # an address with no history yet, or the API down for it
            r.update({"t": None, "weeks": 0, "error": str(ex)[:120]})
    per = {}
    for r in rows:
        per[r["registrant"]] = per.get(r["registrant"], 0) + 1
    for r in rows:
        r["registrant_wallets"] = per[r["registrant"]]
    scored = [r for r in rows if r["t"] is not None]
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "min_weeks": MIN_WEEKS,
           "entries": len(rows), "scored": len(scored),
           "bar_best_of_list": round(bar(max(len(rows), 1)), 2), "rows": rows}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}))


if __name__ == "__main__":
    main()
