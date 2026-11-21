"""For every x402-foundation/x402 issue with comments, record each comment's author and author_association.
Output: x402_comment_roles.jsonl  {n, login, assoc, created}. Resumable (skips issues already fetched)."""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "issues", "x402-foundation_x402.jsonl")
OUT = os.path.join(HERE, "x402_comment_roles.jsonl")
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        done.add(json.loads(l)["n"])
issues = [json.loads(l) for l in open(SRC, encoding="utf-8")]
todo = [x for x in issues if x["c"] > 0 and x["n"] not in done]
print("issues with comments:", sum(1 for x in issues if x["c"] > 0), "todo:", len(todo), flush=True)
with open(OUT, "a", encoding="utf-8") as f:
    for i, x in enumerate(todo):
        r = subprocess.run(["gh", "api", f"repos/x402-foundation/x402/issues/{x['n']}/comments?per_page=100", "--paginate",
                            "--jq", '.[] | [.user.login, .author_association, .created_at] | @tsv'],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print("fail", x["n"], r.stderr[:200], flush=True); continue
        rows = [l.split("\t") for l in r.stdout.splitlines() if l]
        if not rows:
            f.write(json.dumps({"n": x["n"], "login": None, "assoc": None, "created": None}) + "\n")
        for login, assoc, created in rows:
            f.write(json.dumps({"n": x["n"], "login": login, "assoc": assoc, "created": created}) + "\n")
        f.flush()
        if i % 50 == 0: print(i, flush=True)
print("done", flush=True)
