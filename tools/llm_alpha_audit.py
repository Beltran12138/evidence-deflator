"""Audit 018: LLM factor-mining agents (RD-Agent(Q), QuantaAlpha) against the luck bar.

Two steps, both deterministic:

  extract RAW_DIR OUT_JSON   read the saved arXiv HTML and write the reported rows
  score   TABLES_JSON OUT_JSON   turn each reported IR into t = IR * sqrt(years)
                                 and compare with bar(N) from src/hl_wallet.py

Raw HTML is kept outside the repository (arXiv licences); its SHA-256 sums are in
docs/data/llm-alpha/2026-11-19/SHA256SUMS. Rules are fixed in
docs/data/llm-alpha/LLM_ALPHA_PREREG.md.
"""
import html
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hl_wallet import bar  # noqa: E402

NUM = r"(-?\d+\.\d+)"


def text_of(path):
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    t = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", t)


def rows(segment, labels, ncols):
    """For each label, the first ncols numbers that follow it inside segment."""
    out = {}
    for lab in labels:
        i = segment.find(lab)
        if i < 0:
            raise SystemExit(f"label not found: {lab}")
        nums = re.findall(NUM, segment[i + len(lab): i + len(lab) + 400])[:ncols]
        if len(nums) != ncols:
            raise SystemExit(f"short row: {lab} {nums}")
        out[lab] = [float(x) for x in nums]
    return out


def years(start, end):
    """Calendar span, end date inclusive."""
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    return ((d1 - d0).days + 1) / 365.25


def extract(raw_dir, out_json):
    raw = Path(raw_dir)
    res = {}

    # RD-Agent(Q) v2, Table 1: CSI 300, test 2017-01-01 to 2020-08-01.
    t = text_of(raw / "arxiv_2505.15155v2.html")
    s = t[t.find("Table 1: Experimental results of all models on the CSI 300"):]
    s = s[: s.find("Figure")]
    cols = ["IC", "ICIR", "RankIC", "RankICIR", "ARR", "IR", "MDD", "CR"]
    labs = ["R&D-Factor GPT-4o", "R&D-Factor o3-mini", "R&D-Model GPT-4o",
            "R&D-Model o3-mini", "R&D-Agent(Q) GPT-4o", "R&D-Agent(Q) o3-mini"]
    base = ["Alpha 158", "Alpha 360", "TRA"]
    r = rows(s, labs, 8)
    # factor-library rows carry an integer factor count first; NUM skips integers
    b = rows(s, base, 8)
    res["rdagent_table1"] = {
        "source": "arXiv 2505.15155v2 Table 1", "market": "CSI 300",
        "test": ["2017-01-01", "2020-08-01"], "columns": cols,
        "method_rows": r, "baseline_rows": b,
        "backends": {"GPT-4o": "2023-10-01", "o3-mini": "2023-10"},
    }

    # RD-Agent(Q) v2, Table 2: out-of-sample, test 2024-01-01 to 2025-06-30.
    s = t[t.find("Table 2: Out-of-sample experimental results"):]
    s = s[: s.find("Ablation Study")]
    labs2 = ["R&D-Factor (GPT-4o)", "R&D-Factor (o4-mini)", "R&D-Model (GPT-4o)",
             "R&D-Model (o4-mini)", "R&D-Agent(Q) (GPT-4o)", "R&D-Agent(Q) (o4-mini)"]
    r2 = rows(s, labs2, 8)
    res["rdagent_table2"] = {
        "source": "arXiv 2505.15155v2 Table 2", "test": ["2024-01-01", "2025-06-30"],
        "columns": ["CSI500_IC", "CSI500_ICIR", "CSI500_IR", "CSI500_MDD",
                    "NDX100_IC", "NDX100_ICIR", "NDX100_IR", "NDX100_MDD"],
        "method_rows": r2,
        "backends": {"GPT-4o": "2023-10-01", "o4-mini": "2024-06-01"},
    }

    # QuantaAlpha Table 1 in v1, v2 (8 columns) and v3 (7 columns, CR dropped).
    for v, ncol, cols in [
        ("v1", 8, ["IC", "ICIR", "RankIC", "RankICIR", "IR", "CR", "ARR", "MDD"]),
        ("v2", 8, ["IC", "ICIR", "RankIC", "RankICIR", "IR", "CR", "ARR", "MDD"]),
        ("v3", 7, ["IC", "ICIR", "RankIC", "RankICIR", "IR", "ARR", "MDD"]),
    ]:
        t = text_of(raw / f"arxiv_2602.07085{v}.html")
        s = t[t.find("Methods Factor Predictive Power Strategy Performance"):]
        s = s[: re.search(r" 5\.\d [A-Z]", s).start()]
        out = {}
        for block in ["RD-Agent", "AlphaAgent", "QuantaAlpha"]:
            j = s.find(block + " Qwen3-235B")
            seg = s[j:]
            out[block] = rows(seg, ["Qwen3-235B", "Deepseek-V3.2", "Gemini-3-pro-preview",
                                    "Claude-4.5-sonnet", "GPT-5.2"], ncol)
        out["baselines"] = rows(s, ["TRA", "Alpha158 ", "Alpha360"], ncol)
        res[f"quantaalpha_{v}_table1"] = {
            "source": f"arXiv 2602.07085{v} Table 1", "market": "CSI 300",
            "test": ["2022-01-01", "2025-12-26"], "columns": cols, "rows": out,
        }

    Path(out_json).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("wrote", out_json)


def tstat(ir, start, end):
    return ir * math.sqrt(years(start, end))


def score(tables_json, out_json):
    T = json.loads(Path(tables_json).read_text(encoding="utf-8"))
    out = {}

    a = T["rdagent_table1"]
    i = a["columns"].index("IR")
    out["P1_rdagent_table1"] = {
        "t": {k: round(tstat(v[i], *a["test"]), 2) for k, v in a["method_rows"].items()},
        "baseline_t": {k: round(tstat(v[i], *a["test"]), 2) for k, v in a["baseline_rows"].items()},
        "window_end": a["test"][1],
        "backend_cutoffs": a["backends"],
    }

    a = T["rdagent_table2"]
    cells = {}
    for k, v in a["method_rows"].items():
        cells[k + " CSI500"] = round(tstat(v[2], *a["test"]), 2)
        cells[k + " NDX100"] = round(tstat(v[6], *a["test"]), 2)
    n = len(cells)
    out["P2_rdagent_table2"] = {
        "t": cells, "N_reported": n, "bar": round(bar(n), 2),
        "clear": sorted(k for k, x in cells.items() if x >= bar(n)),
        "max_t": max(cells.values()),
    }

    a = T["quantaalpha_v3_table1"]
    i = a["columns"].index("IR")
    qa = {k: round(tstat(v[i], *a["test"]), 2) for k, v in a["rows"]["QuantaAlpha"].items()}
    n = len(qa)
    out["P3_quantaalpha_v3"] = {
        "t": qa, "N_reported": n, "bar": round(bar(n), 2),
        "clear": sorted(k for k, x in qa.items() if x >= bar(n)),
        "clear_single_test_2": sorted(k for k, x in qa.items() if x >= 2),
        "max_t": max(qa.values()),
        "baseline_t": {k: round(tstat(v[i], *a["test"]), 2) for k, v in a["rows"]["baselines"].items()},
    }

    diff = {}
    for block in ["RD-Agent", "AlphaAgent", "QuantaAlpha", "baselines"]:
        r1 = T["quantaalpha_v2_table1"]["rows"][block]
        r3 = T["quantaalpha_v3_table1"]["rows"][block]
        diff[block] = {k: {"IR_v2": r1[k][4], "IR_v3": r3[k][4],
                           "ARR_v2": r1[k][6], "ARR_v3": r3[k][5]} for k in r1}
    out["versions_quantaalpha"] = {
        "v1_equals_v2": T["quantaalpha_v1_table1"]["rows"] == T["quantaalpha_v2_table1"]["rows"],
        "v2_to_v3": diff,
    }

    # Cutoffs from the developers' pages, saved under RAW_DIR/cutoffs (results day).
    # A month-only cutoff counts the whole month as read.
    cut = {
        "GPT-4o": "2023-10-01", "o3-mini": "2023-10-01", "o4-mini": "2024-06-01",
        "GPT-5.2": "2025-08-31", "Claude-4.5-sonnet": "2025-01-31",
        "Gemini-3-pro-preview": "2025-01-31",
        "Deepseek-V3.2": None, "Qwen3-235B": None,
    }

    def share(start, end, c):
        if c is None:
            return None
        d0, d1, dc = (date.fromisoformat(x) for x in (start, end, c))
        if dc < d0:
            return 0.0
        return round(min((dc - d0).days + 1, (d1 - d0).days + 1) / ((d1 - d0).days + 1), 3)

    out["cutoffs"] = {
        "used": cut,
        "rdagent_table1": {b: share("2017-01-01", "2020-08-01", cut[b]) for b in ["GPT-4o", "o3-mini"]},
        "rdagent_table2": {b: share("2024-01-01", "2025-06-30", cut[b]) for b in ["GPT-4o", "o4-mini"]},
        "quantaalpha": {b: share("2022-01-01", "2025-12-26", cut[b]) for b in
                        ["Qwen3-235B", "Deepseek-V3.2", "Gemini-3-pro-preview", "Claude-4.5-sonnet", "GPT-5.2"]},
    }

    # Wider counts of N, by name from the paper text (see Results in the prereg).
    wider = {
        "rdagent_table1_N_paper": 12,  # Table 1: 6; Table 3: +2 (random, LLM); Fig. 9: 6 backends, >= 4 not in Table 1
        "rdagent_table1_N_loop": 6 * 30 + 33 + 33 + 44,  # Fig. 9 and Table 3 loop counts
        "quantaalpha_N_paper": 14,  # 5 backbones, 3 component ablations, 3 control ablations, 3 seed sets
    }
    out["wider_N"] = {k: {"N": n, "bar": round(bar(n), 2)} for k, n in wider.items()}

    Path(out_json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote", out_json)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "extract":
        extract(sys.argv[2], sys.argv[3])
    elif cmd == "score":
        score(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
