"""Demand-side filter: issues that report something that happened (first person, money moved or failed),
not proposals. Excludes titles that look like proposals/extensions/RFCs."""
import glob, json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "issues")
PROPOSAL = re.compile(r"proposal|extension|rfc|\bspec\b|standard|roadmap|idea|feedback request|integration|\[feature\]|feat\]|design question|discussion|coordination", re.I)
INCIDENT = re.compile(r"\b(i|we) (paid|was charged|were charged|got charged|lost|sent|transferred)|charged twice|double charged|paid twice|"
                      r"funds? (lost|stuck|gone|missing)|money (lost|stuck|gone)|drained|lost (usdc|funds|money)|"
                      r"payment (succeeded|went through|was settled) but|settled but|never received|did ?n[o']t receive|"
                      r"overcharg|wrong amount|unexpected(ly)? (charge|payment)|refund (me|my)|stolen", re.I)
rows = []
for f in glob.glob(os.path.join(D, "*.jsonl")):
    if os.path.basename(f).startswith("c_"): continue
    for line in open(f, encoding="utf-8"):
        x = json.loads(line); x["repo"] = os.path.basename(f)[:-6]; rows.append(x)
hits = [x for x in rows if not PROPOSAL.search(x["t"]) and INCIDENT.search(x["t"] + " " + x["b"])]
hits.sort(key=lambda x: x["d"])
print("incident-like:", len(hits), "of", len(rows))
for x in hits:
    m = INCIDENT.search(x["t"] + " " + x["b"])
    print(f"[{x['repo']}#{x['n']}] {x['d'][:10]} {x['s']} c={x['c']} | {x['t'][:90]}  «{m.group(0)}»")
