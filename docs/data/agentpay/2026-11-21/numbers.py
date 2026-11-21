"""Recompute every figure in docs/audits/019-x402-issue-tracker.md from the files in this folder.

    python numbers.py
"""
import collections, json, math, os, random, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
M = {"OWNER", "MEMBER", "COLLABORATOR"}

repos = {f[:-6]: [json.loads(l) for l in open(os.path.join(HERE, "issues", f), encoding="utf-8")]
         for f in sorted(os.listdir(os.path.join(HERE, "issues")))}
print("issues per repo:", {k: len(v) for k, v in repos.items()}, "total", sum(map(len, repos.values())))
x402 = {x["n"]: x for x in repos["x402-foundation_x402"]}

# the sample is reproducible from the seed
random.seed(20261121)
ids = [x["n"] for x in random.sample(repos["x402-foundation_x402"], 80)]
assert ids == json.load(open(os.path.join(HERE, "handlabel_sample_ids.json"))), "sample does not reproduce"
labels = [l.split("\t") for l in open(os.path.join(HERE, "handlabel_x402_80.tsv"), encoding="utf-8").read().splitlines()[1:]]
assert [int(n) for _, n, _ in labels] == ids
c = collections.Counter(l for _, _, l in labels)
print("hand labels:", {k: f"{v} ({v/80:.0%})" for k, v in c.items()}, "| rule of three upper:", f"{3/80:.2%}", "->", math.floor(3 / 80 * len(x402)), "of", len(x402))
per = collections.defaultdict(collections.Counter)
for _, n, l in labels:
    d = x402[int(n)]["d"]; per["2025" if d < "2026" else "2026H1" if d < "2026-07" else "2026H2"][l] += 1
for k in sorted(per):
    print(" ", k, "sell side", per[k]["P"] + per[k]["L"], "of", sum(per[k].values()))

roles = collections.defaultdict(list)
for l in open(os.path.join(HERE, "x402_comment_roles.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    if r["login"]: roles[r["n"]].append(r)
for n in (2332, 2887, 2833, 1777, 1195):
    cs = roles[n]; who = collections.Counter(r["login"] for r in cs)
    print(f"#{n}: comments {len(cs)} distinct {len(who)} top {who.most_common(1)[0][1]} maintainer {sum(r['assoc'] in M for r in cs)}")
maint = collections.Counter(r["login"] for v in roles.values() for r in v if r["assoc"] in M)
replied = {n for n, v in roles.items() if any(r["assoc"] in M for r in v)}
print("maintainer accounts:", len(maint), "| issues with a maintainer comment:", len(replied), "of", len(x402), f"({len(replied)/len(x402):.0%})")
g = collections.defaultdict(lambda: [0, 0])
for _, n, l in labels:
    g[l][0] += int(n) in replied; g[l][1] += 1
print("maintainer comment by label:", dict(g))
