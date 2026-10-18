"""Build the static site in docs/ from one template.

    python tools/build_site.py

Writes: index.html (home), wallet/index.html (from data/hl/latest.json), leaderboard/index.html, method/index.html,
audits/index.html + one page per audits/NNN-*.md, api/index.html, 404.html.
Hand-maintained pages (HAND_PAGES: the calculator, which carries a JS port of
the library that tools/check_js_parity.py diffs, and three older pages) only get
their marked head, header and footer blocks refreshed.
Needs the `markdown` package for the audit pages; nothing at runtime.
"""
import hashlib, html, json, math, os, re
from statistics import NormalDist

import markdown

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DOCS = os.path.join(ROOT, "docs")
SITE = "https://evidencedeflator.com"
REPO = "https://github.com/Beltran12138/evidence-deflator"
TG_BOT = "https://t.me/SkillOrLuckBot"
EXT_URL = "https://chromewebstore.google.com/detail/evidence-deflator/fbhanjlioldbpgmncefioidcpkdhjbhn"
ELSEWHERE_EN = (f'<p class="muted small elsewhere">Also on <a href="{TG_BOT}" rel="noopener">Telegram, @SkillOrLuckBot</a> (send an address, get the verdict), '
                f'and as a <a href="{EXT_URL}" rel="noopener">Chrome extension</a> that shows it on Hyperliquid, Binance and OKX copy-trading pages.</p>')
ISSUE_AUDIT = REPO + "/issues/new?title=Audit%20request%3A%20&body=Link%20to%20the%20backtest%2C%20deck%20or%20claim%3A%0A%0AModel%20(if%20known)%3A%0ATest%20window%3A%0AHow%20many%20variants%20were%20tried%3A%0A"
VERSION = "0.2.0"
# Cloudflare Web Analytics site token (public, cookie-less page counts). Empty = no beacon.
CF_BEACON = "e38b718917cf4c2891f9038a6a597a88"
# Baidu Search Resource Platform site verification (public token; keep it, or the site unverifies).
BAIDU_META = '<meta name="baidu-site-verification" content="codeva-Dwaytu2snb" />\n'
PRIVACY = ("The address is never sent to us. We count page views without cookies (Cloudflare Web Analytics), and each check as one tally with the page language and nothing else."
           if CF_BEACON else "Nothing is sent to us.")
BEACON = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
          f'data-cf-beacon=\'{{"token": "{CF_BEACON}", "spa": true}}\'></script>\n') if CF_BEACON else ""

MARK = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="3" width="20" height="2.2" fill="var(--accent)"/>'
        '<rect x="3.5" y="13" width="3.2" height="8" fill="currentColor"/><rect x="8.6" y="9" width="3.2" height="12" fill="currentColor"/>'
        '<rect x="13.7" y="15" width="3.2" height="6" fill="currentColor"/><rect x="18.8" y="7.5" width="3.2" height="13.5" fill="currentColor" opacity=".55"/></svg>')
GH = ('<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>')
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='4' fill='%2315171C'/%3E"
           "%3Crect x='3' y='4' width='18' height='2' fill='%23E66A4B'/%3E%3Crect x='4.5' y='13' width='3' height='7' fill='%23FAF9F6'/%3E"
           "%3Crect x='9.5' y='9.5' width='3' height='10.5' fill='%23FAF9F6'/%3E%3Crect x='14.5' y='15' width='3' height='5' fill='%23FAF9F6'/%3E%3C/svg%3E")

NAV = [("wallet", "Check", "/wallet/"), ("audits", "Audits", "/audits/"), ("method", "Method", "/method/"), ("api", "For agents", "/api/")]

COPY_ICON = '<span class="cp">copy</span><span class="ok">copied</span>'


def ld(obj):
    """schema.org JSON-LD block for head(extra=...)."""
    data = json.dumps({"@context": "https://schema.org", **obj}, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{data}</script>\n'


APP_LD = {"@type": "SoftwareApplication", "name": "Evidence Deflator", "url": SITE + "/",
          "applicationCategory": "FinanceApplication", "operatingSystem": "Web, Python, MCP",
          "description": "Checks whether a trading record, such as a Hyperliquid wallet or a leaderboard winner, can be told apart from luck once you allow for how it was picked.",
          "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
          "license": "https://opensource.org/licenses/MIT", "codeRepository": REPO, "sameAs": [REPO]}


def hreflang(alt):
    """<link rel=alternate> for each language version; alt maps hreflang -> path."""
    if not alt:
        return ""
    links = [*alt.items(), ("x-default", alt["en"])]
    return "".join(f'<link rel="alternate" hreflang="{k}" href="{SITE}{v}">\n' for k, v in links)


def head(title, desc, path, og=f"{SITE}/leaderboard/og-2026-10.png", extra="", lang="en", alt=None):
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{SITE}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Evidence Deflator">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:image" content="{og}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<script>try{{if(localStorage.getItem('ed_theme')==='dark')document.documentElement.dataset.theme='dark'}}catch(e){{}}
function edTheme(){{var d=document.documentElement,on=d.dataset.theme!=='dark';if(on)d.dataset.theme='dark';else delete d.dataset.theme;try{{on?localStorage.setItem('ed_theme','dark'):localStorage.removeItem('ed_theme')}}catch(e){{}}}}</script>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&family=Newsreader:opsz,wght@6..72,500;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<link rel="stylesheet" href="{asset("chrome.css")}">
<link rel="stylesheet" href="{asset("site.css")}">
{hreflang(alt)}{extra}{BEACON}</head>
<body>
"""


# Light is the default; the toggle switches to dark and remembers it (localStorage, set before paint in head()).
THEME_TOGGLE = ('<button class="theme-toggle" type="button" aria-label="Switch light or dark" title="Light or dark" onclick="edTheme()">'
                '<svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
                '<svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg></button>')


def header(active, alt=None):
    cur = ' aria-current="page"'
    links = "".join(f'<a href="{u}"{cur if k == active else ""}>{t}</a>' for k, t, u in NAV)
    zh = (alt or {}).get("zh-Hans", "/zh-hans/")
    return f"""<header class="site-header"><div class="container">
<a class="brand" href="/">{MARK}Evidence Deflator</a>
<nav class="nav" aria-label="Main">{links}</nav>
<div class="header-cta">{THEME_TOGGLE}<a class="gh" href="{zh}" hreflang="zh-Hans" lang="zh-Hans">中文</a><a class="gh" href="{REPO}">{GH}<span>GitHub</span></a></div>
</div></header>
"""


def footer(scripts=""):
    return f"""<footer class="site-footer"><div class="container">
<div class="foot-grid">
 <div><a class="brand" href="/">{MARK}Evidence Deflator</a>
  <p style="margin-top:14px;max-width:340px">Whether a trading record can be told apart from luck, once you allow for how it was picked. Open source.</p></div>
 <div><h4>Product</h4><ul><li><a href="/wallet/">Hyperliquid check</a></li><li><a href="/polymarket/">Polymarket check</a></li><li><a href="{TG_BOT}">Telegram bot</a></li><li><a href="{EXT_URL}">Chrome extension</a></li><li><a href="/audits/">Audits</a></li><li><a href="/leaderboard/">AI trading leaderboard</a></li><li><a href="/check/">Check a backtest</a></li><li><a href="/api/">API and MCP</a></li></ul></div>
 <div><h4>Method</h4><ul><li><a href="/method/">How it works</a></li><li><a href="/method/#principles">Principles</a></li><li><a href="/q/hyperliquid-trader-skill-or-luck/">Skill or luck?</a></li><li><a href="/q/how-many-months-of-backtest/">How many months?</a></li><li><a href="/q/why-leaderboard-winner-is-not-evidence/">Why #1 is not evidence</a></li><li><a href="/leaderboard/2026-10.json">Data (JSON)</a></li></ul></div>
 <div><h4>Project</h4><ul><li><a href="{REPO}">GitHub</a></li><li><a href="https://pypi.org/project/evidence-deflator/">PyPI</a></li><li><a href="/record/">Our record</a></li><li><a href="/memo/sample/">Sample memo</a></li><li><a href="{ISSUE_AUDIT}">Request an audit</a></li><li><a href="/privacy/">Privacy</a></li><li><a href="/terms/">Terms</a></li></ul></div>
</div>
<div class="foot-note"><span>Open source · MIT · v{VERSION}</span><span>“Cannot be ruled out as seen” is the strongest claim we make about a model’s training data.</span></div>
</div></footer>
<script src="/assets/site.js"></script>
{scripts}</body>
</html>
"""


def ic(text):
    """Escape, then render `inline code` from the markdown sources."""
    return re.sub(r"`([^`]+)`", lambda m: "<code>" + m.group(1) + "</code>", html.escape(text))


def write(rel, text):
    p = os.path.join(DOCS, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", rel, len(text))


# ---------------------------------------------------------------- audits

AUDIT_TAGS = {  # short status shown in lists; the finding text comes from audits/README.md
    "001": ("Cannot assess", "grey"), "002": ("Narrowed comparison", "amber"),
    "003": ("0 of 41 reach t = 2", "red"), "004": ("88% open-book", "red"), "005": ("Cannot assess", "grey"),
    "006": ("0 of 6 reach |t| = 2", "red"),
    "007": ("0 of 180 clear the bar", "red"),
    "008": ("0 of 38 clear the bar", "red"),
    "009": ("Cannot assess", "grey"),
    "010": ("Frozen, readings 10-23 / 10-30", "grey"),
    "011": ("0 of 149 clear the bar", "red"),
}


def audits():
    with open(os.path.join(DOCS, "audits", "README.md"), encoding="utf-8") as f:
        readme = f.read()
    rows = []
    for m in re.finditer(r"^\| \[(\d{3})\]\(([^)]+)\.md\) \| (.+?) \| (\d{4}-\d{2}-\d{2}) \| (.+?) \|$", readme, re.M):
        num, slug, subject, date, finding = m.groups()
        rows.append(dict(num=num, slug=slug, subject=subject, date=date, finding=finding))
    return rows


def md_to_html(text):
    text = re.sub(r"\]\((\d{3}-[a-z0-9-]+)\.md\)", r"](/audits/\1.html)", text)
    text = text.replace("](../../README.md)", f"]({REPO})").replace("](../leaderboard/2026-10.md)", "](/leaderboard/)")
    return markdown.markdown(text, extensions=["tables", "fenced_code"])


def build_audits():
    rows = audits()
    for i, a in enumerate(rows):
        with open(os.path.join(DOCS, "audits", a["slug"] + ".md"), encoding="utf-8") as f:
            src = f.read()
        title_line = src.splitlines()[0].lstrip("# ").strip()
        body = md_to_html("\n".join(src.splitlines()[1:]))
        tag, colour = AUDIT_TAGS.get(a["num"], ("", "grey"))
        prev = rows[i - 1] if i > 0 else None
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        nav = ""
        if prev: nav += f'<li><a href="/audits/{prev["slug"]}.html">← {prev["num"]} · {html.escape(prev["subject"])}</a></li>'
        if nxt: nav += f'<li><a href="/audits/{nxt["slug"]}.html">{nxt["num"]} · {html.escape(nxt["subject"])} →</a></li>'
        page = head(f"Audit {a['num']} · {a['subject'].replace('`', '')} · Evidence Deflator", a["finding"].replace('`', ''), f"/audits/{a['slug']}.html") + header("audits") + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><a href="/audits/" style="text-decoration:none">Audits</a> / {a['num']}</div>
<h1 style="margin-top:16px">{ic(a['subject'])}</h1>
<div class="meta"><span class="tag tag-{colour}">{html.escape(tag)}</span><span class="mono">{a['date']}</span><span>Sources public, fetched on the stated date</span></div>
<div class="callout" style="margin-top:0"><div class="eyebrow" style="margin-bottom:10px">Finding</div>{ic(a['finding'])}</div>
{body}
</article>
<aside class="aside">
 <div class="box"><h4>Three inputs</h4><ul><li>The model’s knowledge cutoff</li><li>The test window</li><li>How many attempts the result was picked from</li></ul></div>
 <div class="box"><h4>Rules</h4><ul><li>Numbers recomputed, not copied</li><li>A missing input is a finding, not a verdict</li><li>No judgement of intent</li></ul></div>
 <div class="box"><h4>More audits</h4><ul>{nav}<li><a href="/audits/">All audits</a></li></ul></div>
 <a class="btn btn-secondary" href="{ISSUE_AUDIT}">Request an audit</a>
</aside>
</div></main>
""" + footer()
        write(f"audits/{a['slug']}.html", page)

    items = "".join(f"""<a class="row" href="/audits/{a['slug']}.html"><span class="row-date">{a['num']} · {a['date']}</span>
<span><span class="row-title">{ic(a['subject'])}</span><span class="row-sub" style="display:block">{ic(a['finding'])}</span></span>
<span class="tag tag-{AUDIT_TAGS.get(a['num'], ('', 'grey'))[1]}">{html.escape(AUDIT_TAGS.get(a['num'], ('', ''))[0])}</span></a>""" for a in rows)
    page = head("Audits · Evidence Deflator", "One-page evidence audits of public AI trading claims: how much of the evidence behind each claim actually counts.", "/audits/") + header("audits") + f"""
<main>
<div class="container page-head">
 <div class="eyebrow"><span class="dot"></span>Audits</div>
 <h1>One page per claim. How much of the evidence counts?</h1>
 <p class="lede">Each audit takes a public AI trading claim and asks for three inputs: the model’s knowledge cutoff, the test window, and how many attempts the result was picked from. Where a project does not publish them, the audit says so.</p>
 <div class="btns" style="margin-top:26px"><a class="btn btn-primary" href="{ISSUE_AUDIT}">Request an audit <span class="arr">→</span></a><span class="muted small">Free, public, usually within 48 hours.</span></div>
</div>
<div class="container" style="padding-bottom:72px">
 <div class="rows">{items}
 <a class="row" href="/case-nuclear.html"><span class="row-date">Case audit · 2026-10-06</span><span><span class="row-title">A “22% chance of a nuclear detonation” on Polymarket</span><span class="row-sub" style="display:block">Five discounts on one prediction-market price: about 16 effective wallets, and a contract that also counts tests.</span></span><span class="tag tag-amber">Wrong question</span></a>
 <a class="row" href="/audit.html"><span class="row-date">Paper audit · 2026-10-05</span><span><span class="row-title">17 published LLM trading papers</span><span class="row-sub" style="display:block">Of the 9 with a documented cutoff, none reaches 48 clean months.</span></span><span class="tag tag-red">0 of 9 reach 48 months</span></a>
 </div>
 <div class="callout" style="margin-top:40px"><h3 style="margin-bottom:8px">Rules every audit follows</h3>
 <p class="muted" style="margin:0">Sources are public and fetched on the stated date; numbers are recomputed, not copied. “Cannot be ruled out as seen” is the strongest claim made about a model’s training data, never “contaminated”. Findings state what the numbers can and cannot support, with no judgement of intent. Short is not the same as wrong: an underpowered result has not been shown to fail, only not shown to work.</p></div>
</div>
</main>
""" + footer()
    write("audits/index.html", page)
    return rows


# ---------------------------------------------------------------- home

def grades(rows, bar):
    """Counts per verdict grade for board rows (t None = too short): the same cut-offs as HL.verdict."""
    ts = [r["t"] for r in rows if r["t"] is not None]
    return {"strong": sum(t >= bar for t in ts), "promising": sum(2 <= t < bar for t in ts),
            "luck": sum(-2 < t < 2 for t in ts), "losing": sum(t <= -2 for t in ts), "scored": len(ts)}


def power(bar, rows=None, sharpes=(2, 3, 4, 5), years=(1, 2, 3, 5)):
    """The positive control. Chance that a trader whose true Sharpe is S clears `bar` after Y years,
    using t ~ S x sqrt(Y) + N(0, 1) (Lo 2002; ignores the noise in the estimated sigma, so roughly).
    With board rows, also the median record length and how many of those records would be expected
    to clear by now if every one had a true Sharpe of 3."""
    cdf = NormalDist().cdf
    table = [(S, [cdf(S * math.sqrt(Y) - bar) for Y in years]) for S in sharpes]
    out = {"years": years, "table": table, "even_odds": {S: (bar / S) ** 2 for S in sharpes}}
    if rows:
        ys = sorted(r["weeks"] / 52 for r in rows if r["t"] is not None)
        out["median_years"] = ys[len(ys) // 2] if len(ys) % 2 else (ys[len(ys) // 2 - 1] + ys[len(ys) // 2]) / 2
        out["expect_s3"] = sum(cdf(3 * math.sqrt(y) - bar) for y in ys)
    return out


def power_table_html(pw, bar, lang="en"):
    pct = lambda p: "<1%" if p < 0.01 else (">99%" if p > 0.99 else f"{100 * p:.0f}%")
    if lang == "en":
        head = "".join(f'<th class="r">{y} yr</th>' for y in pw["years"])
        rows = "".join(f'<tr><td>Sharpe {S}</td>' + "".join(f'<td class="r">{pct(p)}</td>' for p in ps) + "</tr>" for S, ps in pw["table"])
        return f'<div class="table-wrap"><table class="data compact"><thead><tr><th>True Sharpe</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
    head = "".join(f'<th class="r">{y} 年</th>' for y in pw["years"])
    rows = "".join(f'<tr><td>夏普 {S}</td>' + "".join(f'<td class="r">{pct(p)}</td>' for p in ps) + "</tr>" for S, ps in pw["table"])
    return f'<div class="table-wrap"><table class="data compact"><thead><tr><th>真实夏普</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>'


def boards_html(hl):
    """One row of dots per public board we have rescored: each dot is one record's t, the red tick is the
    bar for being picked from that board. Static SVG, built here; the counts are the same as the audits'."""
    def load(*parts):
        try:
            with open(os.path.join(DOCS, "data", *parts), encoding="utf-8") as f:
                return json.load(f)
        except OSError:
            return None
    hp, hr = hl["boards"]["pnl"], hl["boards"].get("roi30") or {}
    bn, ok, pm = load("cex", "binance-2026-10-15.json"), load("cex", "okx-2026-10-15.json"), load("cex", "polymarket-2026-10-15.json")
    rc, pt = load("recall", "recall-2026-10-17.json"), load("papertrade", "frozen-2026-10-16.json")
    rows = []  # (venue, what, t values, bar or (lo, hi), link)
    rows.append(("Hyperliquid", f"all-time PnL top 100, from {hp['ranked_from']:,}", [r["t"] for r in hp["rows"] if r["t"] is not None], hp["t_bar_best_of_n"], "/wallet/"))
    if hr:
        rows.append(("Hyperliquid", "30-day ROI top 100", [r["t"] for r in hr["rows"] if r["t"] is not None], hr["t_bar_best_of_n"], "/wallet/"))
    if bn:
        rows.append(("Binance", "copy trading, 90-day PnL top 100", [r["t"] for r in bn["rows"] if r.get("t") is not None], bn["bar_best_of_n"], "/audits/007-cex-copy-trading.html"))
    if ok:
        rows.append(("OKX", "copy trading, PnL top 100", [r["t_daily365"] for r in ok["rows"] if r.get("t_daily365") is not None], ok["bar_best_of_n"], "/audits/007-cex-copy-trading.html"))
    if pm:
        pb = pm.get("bar_best_of_n_floor_revised", pm["bar_best_of_n_floor"])
        rows.append(("Polymarket", "all-time profit top 50, complete records", [r["z_cluster"] for r in pm["rows"] if r.get("complete") and r.get("z_cluster") is not None], pb, "/polymarket/"))
    if rc:
        ts = [a["t"] for c in rc["competitions"] for a in c["agents_detail"] if a["t"] is not None]
        bars = [c["bar_best_of_n"] for c in rc["competitions"]]
        rows.append(("Recall", "AI agent perps competitions, 10 of them", ts, (min(bars), max(bars)), "/audits/011-recall-perps-competitions.html"))
    # Alpha Arena season 1: the six t values in audit 006's table
    rows.append(("Alpha Arena", "season 1, 6 AI models", [0.54, 0.41, -0.43, -0.70, -0.59, -0.83], 2.67, "/audits/006-alpha-arena-season-1.html"))
    lo_x, hi_x, W, H = -4.0, 6.0, 600, 30
    X = lambda v: 6 + (min(max(v, lo_x), hi_x) - lo_x) / (hi_x - lo_x) * (W - 12)
    def strip(ts, bar):
        g = "".join(f'<line class="ax" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="4" y2="{H - 4}"/>' for v in (0, 2, 4))
        if isinstance(bar, tuple):
            g += f'<rect class="zone" x="{X(bar[0]):.1f}" y="3" width="{X(bar[1]) - X(bar[0]):.1f}" height="{H - 6}"/>'
            g += f'<line class="bar" x1="{X(bar[0]):.1f}" x2="{X(bar[0]):.1f}" y1="3" y2="{H - 3}"/>'
        else:
            g += f'<line class="bar" x1="{X(bar):.1f}" x2="{X(bar):.1f}" y1="3" y2="{H - 3}"/>'
        g += "".join(f'<circle class="pt" cx="{X(v):.1f}" cy="{H / 2 + ((i * 7) % 11) - 5:.1f}" r="2.6"/>' for i, v in enumerate(ts))
        return f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" aria-hidden="true">{g}</svg>'
    axis = "".join(f'<span style="left:{X(v) / W * 100:.2f}%">{v:g}</span>' for v in (-4, -2, 0, 2, 4, 6))
    body = ""
    for venue, what, ts, bar, link in rows:
        b0 = bar[0] if isinstance(bar, tuple) else bar
        n_bar, n2 = sum(t >= b0 for t in ts), sum(t >= 2 for t in ts)
        btxt = f"{bar[0]:.2f}–{bar[1]:.2f}" if isinstance(bar, tuple) else f"{bar:.2f}"
        body += (f'<a class="brow" href="{link}"><span class="bname"><b>{venue}</b><span>{what}</span></span>'
                 f'<span class="bstrip">{strip(ts, bar)}</span>'
                 f'<span class="bcount"><b class="c-accent">{n_bar} / {len(ts)}</b><span>strong (≥ {btxt})</span><span>{n2 - n_bar} promising (t ≥ 2)</span></span></a>')
    pt_note = ""
    if pt:
        pt_note = f' Papertrade’s board ({pt["board_rows"]:,} accounts) has no return series yet; three groups were frozen {pt["frozen_at"][:10]} for <a href="/audits/010-papertrade-leaderboard.html">readings on 10-23 and 10-30</a>.'
    return f"""
<section id="boards"><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Every board we have rescored</div><h2 style="margin-top:12px">Ranked by profit. On every board we have rescored, no one has strong evidence yet.</h2>
 <p>Each dot is one record’s t on a public leaderboard; the red line is the bar for being picked from that board. Dots past t = 2 are promising; none is past the red line. <a href="/method/#yes">Why that is not the method saying no to everything</a>.</p></div><a class="more" href="/audits/">All audits →</a></div>
 <div class="boards-dots"><div class="baxis"><span class="bname"></span><span class="bstrip">{axis}</span><span class="bcount"></span></div>{body}</div>
 <p class="muted small" style="margin-top:12px">Hyperliquid rows are rebuilt daily; the others are as of their audit dates. Values beyond the axis are drawn at its edge.{pt_note}</p>
</div></section>"""


def luck_odds(t, n, lang="en"):
    """Luck as odds and as a percentage, the way docs/assets/wallet.js shows it: ("1 in 6", "16%")."""
    p = None if t is None else -math.expm1(n * math.log1p(-(1 - NormalDist().cdf(t))))
    if p is None:
        return "—", ""
    pct = f"{100 * p:.0f}%" if p >= 0.1 else f"{100 * p:.1f}%" if p >= 0.01 else f"{100 * p:.2g}%" if p >= 1e-6 else "< 0.0001%"
    if p >= 0.99:
        return ("almost certain" if lang == "en" else "几乎必然"), pct
    if p >= 0.5:
        return ("more likely than not" if lang == "en" else "多半能"), pct
    x = 1 / p
    r = round(x) if x < 100 else float(f"{x:.2g}")
    if lang == "en":
        return f"1 in {r / 1e6:.2g} million" if r >= 1e6 else f"1 in {int(r):,}", pct
    return (f"{r / 1e4:.2g} 万次里 1 次" if r >= 1e5 else f"{int(r):,} 次里 1 次"), pct


def coin_line(n, lang="en"):
    """Among n accounts each calling ten coin flips, how many call all ten: n / 1024."""
    k = round(n / 1024)
    return (f"Have {n:,} people call ten coin flips each, and about {k} will get all ten right. On a leaderboard, they would be at the top."
            if lang == "en" else f"让 {n:,} 个人各猜 10 次抛硬币，平均约有 {k} 个人 10 次全对。放到排行榜上，他们就排在最前面。")


def evidence_rank_html(hl, lang="en", P="/", k=6):
    """The strongest records on Hyperliquid's two top-100 boards, ranked by t instead of profit."""
    seen, rows = set(), []
    for key in ("pnl", "roi30"):
        b = hl["boards"].get(key) or {}
        for r in b.get("rows", []):
            if r["t"] is None or r["address"] in seen:
                continue
            seen.add(r["address"])
            rows.append((key, r))
    rows.sort(key=lambda kr: -kr[1]["t"])
    pnl = hl["boards"]["pnl"]
    N, bar = pnl["ranked_from"], pnl["t_bar_best_of_n"]
    zh = lang != "en"
    out = ""
    for i, (key, r) in enumerate(rows[:k], 1):
        a = r["address"]
        name = (r.get("vault") or r.get("display") or a[:6] + "…" + a[-4:])
        found = ((f"#{r['rank']} by all-time PnL" if key == "pnl" else f"#{r['rank']} by 30-day ROI") if not zh else
                 (f"全期 PnL 第 {r['rank']}" if key == "pnl" else f"30 日 ROI 第 {r['rank']}"))
        yrs = r["weeks"] / 52
        o, pc = luck_odds(r["t"], N, lang)
        notes = []
        if "no_losing_week" in r["flags"]:
            notes.append("no losing week: check for market making or selling tail risk" if not zh else "一周都没亏过：先查是不是做市或卖尾部风险")
        if (r.get("vault") or "").startswith("Hyperliquidity Provider"):
            notes.append("Hyperliquid’s own market-making vault" if not zh else "Hyperliquid 自己的做市金库")
        elif r.get("vault"):
            notes.append("a vault" if not zh else "金库")
        if "one_week_majority" in r["flags"]:
            notes.append("one week made most of it" if not zh else "一周贡献了大部分收益")
        if "pnl_outside_record" in r["flags"]:
            notes.append("most PnL outside the measurable weeks" if not zh else "大部分盈亏不在可测的周里")
        tb = r.get("t_btc")
        w = max(0.0, min(r["t"] / bar, 1)) * 100
        href = (f"/wallet/?a={a}" if not zh else f"{P}?a={a}")
        out += (f'<tr><td class="r">{i}</td><td><a href="{href}">{html.escape(name)}</a><span class="muted small" style="display:block">{found}</span></td>'
                f'<td class="r">{yrs:.1f}{" yr" if not zh else " 年"}</td>'
                f'<td><span class="mbar"><span class="track"><span class="fill" style="width:{w:.1f}%"></span><span class="t2" style="left:{2 / bar * 100:.1f}%"></span></span><span class="mono">{r["t"]:.2f}</span></span></td>'
                f'<td class="r mono">{"—" if tb is None else f"{tb:.2f}"}</td>'
                f'<td class="r">{o}<span class="muted small" style="display:block">{pc}</span></td>'
                f'<td class="small">{"; ".join(notes)}</td></tr>')
    if not zh:
        head_ = ('<th class="r">#</th><th>Record</th><th class="r">Length</th><th>t (bar {bar:.2f})</th><th class="r">t after BTC</th>'
                 f'<th class="r">Luck alone, among {N:,}</th><th>Notes</th>').replace("{bar:.2f}", f"{bar:.2f}")
    else:
        head_ = (f'<th class="r">#</th><th>记录</th><th class="r">长度</th><th>t（门槛 {bar:.2f}）</th><th class="r">扣掉 BTC 后的 t</th>'
                 f'<th class="r">{N:,} 人里单靠运气</th><th>备注</th>')
    return f'<div class="table-wrap"><table class="data compact rank"><thead><tr>{head_}</tr></thead><tbody>{out}</tbody></table></div>'


def build_home(rows, lb):
    with open(os.path.join(DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        hl = json.load(f)
    hp, hc = hl["boards"]["pnl"], hl.get("cohort") or {}
    with open(os.path.join(DOCS, "data", "papertrade", "frozen-2026-10-16.json"), encoding="utf-8") as f:
        pt = json.load(f)
    scored_rows = [r for r in hp["rows"] if r["t"] is not None]
    best = max(scored_rows, key=lambda r: r["t"])
    n_corr = sum(r["t"] >= 2.6 for r in scored_rows)
    g, pw = grades(hp["rows"], hp["t_bar_best_of_n"]), power(hp["t_bar_best_of_n"], hp["rows"])
    lead = ("None of the top 100 has strong evidence yet." if g["strong"] == 0 else
            f"{g['strong']} of the top 100 {'has' if g['strong'] == 1 else 'have'} strong evidence.")
    lead_rest = f"{g['promising']} are promising, not proven; {g['luck']} look like luck" + (f"; {g['losing']} {'is' if g['losing'] == 1 else 'are'} losing, not by chance" if g["losing"] else "") + "."
    bname = best.get("vault") or best.get("display") or (best["address"][:6] + "…" + best["address"][-4:])
    if best["t"] >= hp["t_bar_best_of_n"]:
        bpill, bsay = ("tag-green", "Strong evidence"), "Strong enough even after allowing for being the best of {:,}.".format(hp["ranked_from"])
    elif best["t"] >= 2:
        bpill, bsay = ("tag-amber", "Promising, not proven"), "Strong enough if you had picked it blind. Not once you remember it is the best of {:,}.".format(hp["ranked_from"])
    else:
        bpill, bsay = ("tag-red", "Looks like luck"), "Even the strongest record on the board is within what luck produces."
    if (best.get("vault") or "").startswith("Hyperliquidity Provider"):
        bsay += " And it is not a trader: it is Hyperliquid’s own market-making and liquidation vault."
    elif best.get("vault"):
        bsay += " It is a vault, not a single trader."
    example_html = (f'<a class="example-result" href="/wallet/?a={best["address"]}"><span class="eyebrow">Example · the strongest record on the all-time PnL board</span>'
                    f'<span class="ex-head"><b>{html.escape(bname)}</b><span class="tag {bpill[0]}">{bpill[1]}</span></span>'
                    f'<span class="ex-say">{bsay}</span>'
                    f'<span class="ex-num mono">t = {best["t"]:.2f} · {best["weeks"]:.0f} weeks · bar {hp["t_bar_best_of_n"]:.2f} · rank #{best["rank"]} by PnL</span>'
                    f'<span class="ex-more">See the full check →</span></a>')
    la, ai = lb["boards"]
    feed = [
        ("2026-10-14", "Hyperliquid leaderboard, rescored", f"Of the all-time PnL top 100, {hp['n_t_ge_bar']} of {hp['scored']} clear the bar for being picked from {hp['ranked_from']:,} accounts. 200 wallets frozen for a forward record.", "/wallet/", "Wallets"),
        ("2026-10-13", "Leaderboard No. 1", "Liquidity Arena and HKUDS AI-Trader, rescored by evidence instead of return.", "/leaderboard/", "Leaderboard"),
    ] + [(a["date"], f"Audit {a['num']} · {a['subject']}", a["finding"], f"/audits/{a['slug']}.html", "Audit") for a in reversed(rows)][:4] + [
        ("2026-10-05", "17 published LLM trading papers", "Of the 9 with a documented cutoff, none reaches 48 clean months.", "/audit.html", "Paper audit"),
    ]
    feed.sort(key=lambda r: r[0], reverse=True)
    feed = feed[:3]
    feed_html = "".join(f'<a class="row" href="{u}"><span class="row-date">{d}</span><span><span class="row-title">{ic(t)}</span><span class="row-sub" style="display:block">{ic(s)}</span></span><span class="row-tag">{k}</span></a>' for d, t, s, u, k in feed)
    py = ('<span class="k">from</span> evidence_deflator <span class="k">import</span> effective_window\n\n'
          'w = effective_window(cutoff=<span class="s">"2024-10"</span>, start=<span class="s">"2020-01"</span>,\n'
          '                     end=<span class="s">"2025-06"</span>, trials=<span class="o">41</span>)\n'
          'print(w.open_book_months, w.effective_months, w.months_required, w.verdict)\n'
          '<span class="c"># 58 8 128 underpowered</span>')
    cli = ('<span class="c"># from a clone of the repository</span>\n'
           'python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06\n'
           '<span class="c"># 66 months, 58 cannot be ruled out as seen, 8 clean; Sharpe 1 needs ~48</span>')
    mcp = ('pip install <span class="s">"evidence-deflator[mcp]"</span>\n\n'
           '<span class="c"># claude_desktop_config.json, Cursor, Claude Code …</span>\n'
           '{ <span class="s">"mcpServers"</span>: { <span class="s">"evidence-deflator"</span>: { <span class="s">"command"</span>: <span class="s">"evidence-deflator-mcp"</span> } } }')
    page = head("Evidence Deflator · Is that trading record skill, or could it be luck?",
                "Paste any Hyperliquid address and see whether its record can be told apart from luck. Open-source evidence checks for trading records, leaderboards and AI backtests.", "/",
                extra=ld(APP_LD) + BAIDU_META) + header("home") + f"""
<main>
<div class="container hero">
 <div class="eyebrow"><span class="dot"></span>Evidence for trading records</div>
 <h1 class="display">Is that trading record skill, or could it be luck?</h1>
 <p class="lede">{coin_line(hp['ranked_from'])} Leaderboards rank by profit. We rank by how hard a record is to explain by luck. Paste a Hyperliquid address or a Polymarket wallet to check one.</p>
 <div class="tabs hero-tabs" role="tablist" aria-label="Which venue" style="margin-top:26px;max-width:640px"><button type="button" role="tab" aria-selected="true" data-act="/wallet/" data-ph="0x… Hyperliquid address">Hyperliquid</button><button type="button" role="tab" aria-selected="false" data-act="/polymarket/" data-ph="0x… address or Polymarket username">Polymarket</button></div>
 <form class="wcheck" id="hcheck" action="/wallet/" method="get" autocomplete="off" style="margin-top:14px">
  <input name="a" placeholder="0x… Hyperliquid address" spellcheck="false" aria-label="Hyperliquid address">
  <button class="btn btn-primary" type="submit">Check <span class="arr">→</span></button>
 </form>
 {ELSEWHERE_EN}
 <div class="rankbox">
  <div class="eyebrow" style="margin-top:34px">Hyperliquid, ranked by evidence instead of profit · {hl['fetched'][:10]}</div>
  <h2 style="margin-top:10px">The records hardest to explain by luck, among {hp['ranked_from']:,} accounts</h2>
  <p class="muted">None clears {hp['t_bar_best_of_n']:.2f}, the bar for the best of {hp['ranked_from']:,}, yet. “Luck alone” is the chance that, with no skill anywhere on the board, someone would still post a record this strong.</p>
  {evidence_rank_html(hl)}
  <p class="muted small" style="margin-top:8px">From the all-time PnL and 30-day ROI top 100s. The verdict uses t; the BTC-adjusted t is shown alongside until a dated method change. <a href="/ranking/">Famous records, same ruler →</a></p>
 </div>
 <div class="instrument">
  <div class="instrument-head"><span class="t"><b style="color:var(--ink);font-weight:550">Hyperliquid, all-time PnL top 100</b> · each dot is one wallet’s t-statistic · {hl['fetched'][:10]}</span><a class="small" href="/wallet/">Rescored board →</a></div>
  <p class="iverdict"><b>{lead}</b> {lead_rest}</p>
  <div class="instrument-body chart" style="border:0;border-radius:0" id="hero-chart"></div>
  <div class="instrument-foot">
   <div><b class="c-accent">{g['strong']} / {g['scored']}</b><span>strong evidence: clear {hp['t_bar_best_of_n']:.2f}, the bar for the best of {hp['ranked_from']:,}</span></div>
   <div><b>{g['promising']} / {g['scored']}</b><span>promising, not proven: t ≥ 2, enough for a wallet picked blind</span></div>
   <div><b>{pw['median_years']:.1f} yr</b><span>median record here; a true Sharpe of 3 needs {pw['even_odds'][3]:.1f} yr for even odds</span></div>
   <div><b>{hc.get('members', 0)}</b><span>wallets frozen {hc.get('frozen_at', '')[:10]}, scored from then on</span></div>
  </div>
 </div>
 <details class="why"><summary>Why does no one clear it? Can it ever say yes?</summary>
  <p><b>Zero is what a board with no proven skill looks like.</b> If none of the {hp['ranked_from']:,} accounts had any skill, luck would carry anyone at all past {hp['t_bar_best_of_n']:.2f} only about 2% of the time: that is how the bar is set.</p>
  <p><b>It can say yes; the records are short.</b> The chance that a trader whose true Sharpe is S clears {hp['t_bar_best_of_n']:.2f} after a given length of record:</p>
  {power_table_html(pw, hp['t_bar_best_of_n'])}
  <p>The median record in this top 100 is {pw['median_years']:.1f} years. If every one of these {g['scored']} had a true Sharpe of 3, about {pw['expect_s3']:.0f} would clear the bar by now, given their record lengths. {g['strong']} do.</p>
  <p>How high the bar sits also depends on how independent the accounts are: {hp['t_bar_best_of_n']:.2f} if each is a separate bet, about 2.6 by our rough estimate if many trade alike ({n_corr} clear that). <a href="/method/#yes">Can it say yes</a> · <a href="/method/#wallets">how the bar is set</a>.</p>
 </details>
</div>

{boards_html(hl)}
<section id="forward"><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Forward record</div><h2 style="margin-top:12px">Every record found by looking back was picked. So we froze some, and score only what happens next.</h2>
 <p><b>{hc.get('members', 0)} Hyperliquid wallets</b> from today’s two top-100 boards, frozen {hc.get('frozen_at', '')[:10]}: first reading <b>{hc.get('first_readings', '')}</b>. <b>Papertrade</b>, three groups of 100 including a random control, frozen {pt['frozen_at'][:10]}: readings <b>10-23</b> and <b>10-30</b>. Each list is published with its hash when frozen, and every reading is published whatever it shows.</p></div><a class="more" href="/record/">Our record, scored in public →</a></div>
</div></section>

<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Latest</div><h2 style="margin-top:12px">Published checks</h2><p>Every number recomputed from public sources, dated, with the raw data kept.</p></div><a class="more" href="/audits/">All audits →</a></div>
 <div class="rows">{feed_html}</div>
</div></section>


</main>
""" + footer("""<script src="/assets/lb.js"></script>
<script>document.querySelectorAll('.hero-tabs button').forEach(b=>b.addEventListener('click',()=>{const f=document.getElementById('hcheck'),i=f.querySelector('input');
 document.querySelectorAll('.hero-tabs button').forEach(x=>x.setAttribute('aria-selected',x===b));f.action=b.dataset.act;i.placeholder=b.dataset.ph;i.setAttribute('aria-label',b.dataset.ph);i.focus();}));</script>
<script>LB.load('/data/hl/latest.json').then(d=>{const p=d.boards.pnl,rows=p.rows.filter(r=>r.t!=null).map(r=>({t:r.t,rank:r.rank,name:r.vault?((r.vault.match(/\(([^)]+)\)/)||[0,r.vault])[1]+' vault'):r.address.slice(0,6)+'…'+r.address.slice(-4),pnl:r.pnl_all_time}));
 const best=rows.reduce((a,r)=>r.t>a.t?r:a,rows[0]);
 document.getElementById('hero-chart').innerHTML=LB.strip({board:p.board,rows,entries:p.ranked_from,t_bar_best_of_n:p.t_bar_best_of_n,max_t_rank:best.rank},{h:170,flip:true});LB.play(document.getElementById('hero-chart'));});</script>
""")
    write("index.html", page)


# ---------------------------------------------------------------- leaderboard

def build_leaderboard(lb):
    la, ai = lb["boards"]
    extra = {
        la["id"]: f"""<p class="muted">Live sandbox trading, so the model could not have seen the test period: closed-book by construction. The gap is length and selection. <a href="/audits/003-liquidity-arena-phase-1.html">Audit 003</a>.</p>
<div class="stats" style="margin:22px 0 26px">
 <div><b class="c-accent">0 / {la['entries']}</b><span>teams reach t = 2</span></div>
 <div><b>{la['max_t']:.2f}</b><span>closest: {html.escape(la['max_t_name'])}, rank {la['max_t_rank']} by return. At its observed Sharpe, about {la['months_to_winner']['closest_at_observed_sharpe']} months of forward record would clear the bar.</span></div>
 <div><b>11 · 7 · 17</b><span>return ranks of the top three by evidence. The return leader is fifth by t.</span></div>
</div>""",
        ai["id"]: f"""<div class="stats" style="margin:22px 0 26px">
 <div><b class="c-accent">{ai['frozen']['moved_under_1pp_since_jul24']} / {ai['frozen']['with_any_history']}</b><span>agents with history moved under 1 point between 24 July and 12 October. A third-party report (<a href="https://github.com/HKUDS/AI-Trader/issues/311">#311</a>, unconfirmed) finds the price feed stuck at about 24 July.</span></div>
 <div><b>+271.6%</b><span>the #1 agent, with no history published. So is #2 (+145.4%): no Sharpe or drawdown can be computed.</span></div>
 <div><b>10 / 100</b><span>of the top 100 are one parameter grid (<code>OC-rot-lb126-rb30-…</code>), ranked as separate winners.</span></div>
</div>
<p class="muted small">History is July only, then one live snapshot, so annualisation is rough. {ai['frozen']['had_90pct_of_return_at_first_record']} of {ai['frozen']['with_any_history']} already had ≥ 90% of their return when the history begins. 46 of the top 100 show zero trades alongside non-zero returns; reported as published.</p>""",
    }
    boards = ""
    for b in lb["boards"]:
        boards += f"""
<section id="{b['id']}"><div class="container">
 <div class="sec-head"><div><div class="eyebrow">{b['entries']:,} entries · ranked by {html.escape(b['ranked_by'])}</div><h2 style="margin-top:12px">{html.escape(b['board'])}</h2></div>
 <span class="muted small mono">{html.escape(b['window'])}</span></div>
 {extra[b['id']]}
 <div class="chart" data-strip="{b['id']}"></div>
 <p class="muted small" style="margin-top:8px">Source: <code>{html.escape(b['source'])}</code>, fetched {lb['fetched']}.</p>
 <div class="toolbar"><div class="seg" data-b="{b['id']}"><button data-by="rank" class="on">Rank by return</button><button data-by="t">Rank by evidence</button></div>
 <button class="linkbtn" data-more="{b['id']}">Show all {len(b['rows'])} rows</button></div>
 <div class="table-wrap"><table class="data" id="t-{b['id']}"></table></div>
</div></section>"""
    summary = "".join(f"""<tr><td><a href="#{b['id']}">{html.escape(b['board'])}</a></td><td class="r">{b['entries']:,}</td><td class="wrap">{html.escape(b['window'])}</td><td class="r c-accent">{b['reaching_t2']}</td><td class="r">{b['max_t']:.2f}</td><td class="r">{b['t_bar_best_of_n']:.2f}</td><td class="wrap">{"%.0f months" % b['months_to_winner']['sharpe_5'] if b['months_to_winner']['sharpe_5'] < 24 else "%.1f years" % (b['months_to_winner']['sharpe_5']/12)} at Sharpe 5 · {"%.0f months" % b['months_to_winner']['sharpe_2'] if b['months_to_winner']['sharpe_2'] < 24 else "%.1f years" % (b['months_to_winner']['sharpe_2']/12)} at Sharpe 2</td></tr>""" for b in lb["boards"])
    page = head("Evidence-adjusted leaderboard · AI trading · October 2026",
                "Public AI trading leaderboards rank by return. We rescore them by how much each ranking can tell: 0 of 41 competition teams and 0 of 32 public agents reach even t = 2.",
                "/leaderboard/") + header("leaderboard") + f"""
<main>
<div class="container page-head">
 <div class="eyebrow"><span class="dot"></span>Evidence-adjusted leaderboard · No. 1 · October 2026</div>
 <h1>Public AI trading leaderboards rank by return. None of them can yet name a winner.</h1>
 <p class="lede">We take the equity history each board publishes and ask a different question of the same data: how much can the ranking tell you, and how long until it could show that the top entry is skilled rather than lucky?</p>
 <div class="stats" style="margin-top:36px">
  <div><b class="c-accent">0 / {la['entries']}</b><span>competition teams reach t = 2 (Liquidity Arena)</span></div>
  <div><b class="c-accent">0 / {ai['with_series']}</b><span>top public agents with history reach t = 2 (AI-Trader)</span></div>
  <div><b>~{round(la['months_to_winner']['sharpe_5'])} mo</b><span>earliest the arena could name a winner, if the best team’s true Sharpe were 5</span></div>
  <div><b>{ai['months_to_winner']['sharpe_2']/12:.1f} yr</b><span>for AI-Trader at a true Sharpe of 2, against 23,376 entries</span></div>
 </div>
 <p class="muted small" style="margin-top:14px">t = annualised Sharpe × √years. One result needs t ≥ 2; the best of N needs more. <a href="/method/#leaderboards">How this is computed</a>.</p>
</div>
<div class="container" style="padding-bottom:56px">
 <div class="table-wrap"><table class="data"><thead><tr><th>Board</th><th class="r">Entries</th><th>Window</th><th class="r">t ≥ 2</th><th class="r">Highest t</th><th class="r">Best-of-N bar</th><th>Earliest winner*</th></tr></thead><tbody>{summary}</tbody></table></div>
 <p class="muted small" style="margin-top:10px">* Months of clean, forward history the top entry would need to clear the best-of-N bar, if its true Sharpe were the value shown. Counting every entry as independent overstates the charge when entries are correlated; the true Sharpe is unknown. The two cut in opposite directions.</p>
</div>
{boards}
<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">For operators</div><h2 style="margin-top:12px">What would bring the date forward</h2></div></div>
 <div class="triad">
  <div><span class="k">LONGER WINDOWS</span><h3>Carry records across phases</h3><p>A month of live trading is too short for any realistic Sharpe. Carrying Phase I into Phase II doubles each team’s evidence at no cost.</p></div>
  <div><span class="k">PUBLISH THE HISTORY</span><h3>Rank only full equity curves</h3><p>A single snapshot supports no Sharpe, no drawdown and no test. An entry with no history should not sit at the top.</p></div>
  <div><span class="k">GROUP THE VARIANTS</span><h3>One owner, one family</h3><p>Parameter sweeps are one attempt with many tries. Show them as a family against one bar, not as separate winners.</p></div>
 </div>
</div></section>
<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Data</div><h2 style="margin-top:12px">Use the numbers</h2>
 <p>Per-entry return, days, Sharpe and t, built by <a href="{REPO}/blob/main/tools/build_leaderboard.py"><code>tools/build_leaderboard.py</code></a> from each board’s public endpoint. CC BY 4.0.</p></div></div>
 <div class="btns"><a class="btn btn-primary" href="/leaderboard/2026-10.json">Download 2026-10.json</a><a class="btn btn-secondary" href="{REPO}/issues/new?title=Leaderboard%20to%20rescore%3A%20">Suggest a board to rescore</a><a class="btn btn-secondary" href="{REPO}/blob/main/docs/leaderboard/2026-10.md">Text version</a></div>
 <p class="muted small" style="margin-top:18px">Operate one of these boards and think a number is wrong? Open an issue; corrections are published in the next edition. Next: TradeRank seasons 1–6 and Liquidity Arena Phase II.</p>
</div></section>
</main>
""" + footer("""<script src="/assets/lb.js"></script>
<script>
LB.load('/leaderboard/2026-10.json').then(d=>{
  const st={};
  d.boards.forEach(b=>{st[b.id]={by:'rank',all:false};
    document.querySelector(`[data-strip="${b.id}"]`).innerHTML=LB.strip(b);
    document.getElementById('t-'+b.id).innerHTML=LB.table(b,'rank',false);});
  const redraw=id=>{const b=d.boards.find(x=>x.id===id);document.getElementById('t-'+id).innerHTML=LB.table(b,st[id].by,st[id].all);};
  document.querySelectorAll('.seg[data-b]').forEach(g=>g.addEventListener('click',e=>{const by=e.target.dataset.by;if(!by)return;
    g.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===e.target));st[g.dataset.b].by=by;redraw(g.dataset.b);}));
  document.querySelectorAll('[data-more]').forEach(btn=>btn.addEventListener('click',()=>{const id=btn.dataset.more,b=d.boards.find(x=>x.id===id);
    st[id].all=!st[id].all;redraw(id);btn.textContent=st[id].all?'Show top 15':`Show all ${b.rows.length} rows`;}));
});
</script>
""")
    write("leaderboard/index.html", page)
    redirect = f'<!DOCTYPE html><meta charset="utf-8"><title>Moved</title><link rel="canonical" href="{SITE}/method/"><meta http-equiv="refresh" content="0; url=/method/#leaderboards"><a href="/method/#leaderboards">Method</a>\n'
    write("leaderboard/methodology.html", redirect)


# ---------------------------------------------------------------- method

METHOD_ALT = {"en": "/method/", "zh-Hans": "/zh-hans/method/", "zh-Hant": "/zh-hant/method/"}
API_ALT = {"en": "/api/", "zh-Hans": "/zh-hans/api/", "zh-Hant": "/zh-hant/api/"}


# Famous records on the wallet ruler (tools/masters_calibration.py): yearly returns regressed on the
# S&P 500 with dividends, t of alpha put on the normal scale. Berkshire: per-share market value, 2025
# shareholder letter table. Medallion: net of fees, Cornell (2019) Table 1, from Zuckerman (2019).
MASTERS = [  # (key, years, z of alpha vs S&P 500, beta)
    ("medallion", "1988–2018", 7.05, -0.58),
    ("brk", "1965–2025", 2.77, 0.90),
    ("brk2001", "2001–2025", 1.79, 0.59),
]
SP500_RAW_Z = 4.94  # the index's own yearly returns 1965–2025, tested against zero instead of against the market


def method_numbers():
    """Numbers for the "Can it say yes?" section (English and Chinese method pages), from today's board."""
    with open(os.path.join(DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        hp = json.load(f)["boards"]["pnl"]
    bar, pw = hp["t_bar_best_of_n"], power(hp["t_bar_best_of_n"], hp["rows"])
    alpha, inv = 1 - NormalDist().cdf(2), NormalDist().inv_cdf
    return dict(hl_bar=bar, pw=pw, s3=pw["even_odds"][3], s2=pw["even_odds"][2], med=pw["median_years"], e3=pw["expect_s3"],
                strong=grades(hp["rows"], bar)["strong"], b10=inv(1 - alpha / 10), b100=inv(1 - alpha / 100))


def build_method():
    m = method_numbers()
    hl_bar, s3, s2, med, e3, strong, b10, b100 = (m[k] for k in ("hl_bar", "s3", "s2", "med", "e3", "strong", "b10", "b100"))
    hl_power = power_table_html(m["pw"], hl_bar)
    page = head("Method · Evidence Deflator", "How Evidence Deflator computes open-book months, clean months needed, the bar after selection, and the earliest date a leaderboard could name a winner.", "/method/", alt=METHOD_ALT) + header("method", METHOD_ALT) + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>Method</div>
<h1 style="margin-top:16px">Plain arithmetic on inputs anyone can state</h1>
<p class="lede" style="margin-top:14px">Every number on this site can be recomputed from public data with the scripts in the repository. Nothing depends on a model of ours, and nothing needs the strategy’s code.</p>

<h2 id="open-book">1 · Open-book months</h2>
<p>Split the test window at the model’s published training cutoff. Months on or before the cutoff cannot be ruled out as seen: the model may already know what happened. Months after it are clean.</p>
<div class="eq">window 2020-01 → 2025-06, cutoff 2024-10
66 months  =  58 open-book  +  8 clean</div>
<p>Cutoffs come only from the provider’s own documentation. Where none is published, we say so and do not estimate one. An earlier cutoff always makes a result look better, so it is the input that most needs a source.</p>

<h2 id="clean-months">2 · Clean months needed</h2>
<p>A result of annualised Sharpe S reaches t = 2 after T years, where t ≈ S × √T (Lo, 2002):</p>
<div class="eq">months needed = (t / S)² × 12
Sharpe 2 → 12    Sharpe 1 → 48    Sharpe 0.5 → 192</div>
<p>If the clean segment is shorter than this, the backtest is <em>underpowered</em>: it has not been shown to fail, only not shown to work. The i.i.d. assumption makes this a floor; autocorrelated returns need longer.</p>

<h2 id="selection">3 · The bar after selection</h2>
<p>A result picked as the best of N attempts is the maximum of N draws. We raise the bar with a one-sided Bonferroni correction that keeps a single attempt at exactly t = 2:</p>
<div class="eq">α      = 1 − Φ(2)          ≈ 2.3%, one-sided
bar(N) = Φ⁻¹(1 − α / N)
N = 1 → 2.00    N = 41 → 3.26    N = 23,376 → 4.76</div>
<p>Bonferroni assumes independent attempts. Correlated variants (one owner’s parameter grid, teams on the same model) make it conservative. We say so rather than switch to a correction whose assumptions a reader cannot check; the library accepts a measured effective number of trials when one exists.</p>

<h2 id="leaderboards">4 · Leaderboards</h2>
<p>For each entry we take the published equity history, keep the last value of each day, and compute daily returns. Crypto boards annualise with 365 days, equity calendars with 252.</p>
<div class="eq">Sharpe = mean(daily return) / sd(daily return) × √(days per year)
t      = Sharpe × √(years of data)</div>
<p>“Nobody is significant” says little on its own, so each board also gets a date: how many months of clean, forward history the top entry would need to clear the best-of-N bar, if its true Sharpe were S.</p>
<div class="eq">months to a winner = (bar(N) / S)² × 12</div>
<p>We report it at S = 5 and S = 2, and at the closest entry’s observed Sharpe. These are conditional statements, not forecasts.</p>

<h2 id="wallets">5 · Wallets: returns, deposits and the bar</h2>
<p>A wallet’s weekly return is the change in the PnL Hyperliquid records for the account over the week, divided by the account value at the start of that week. Hyperliquid’s PnL history excludes deposits and withdrawals, so money moving in or out changes the account value but is never counted as a gain or a loss. It does change the denominator for the weeks after it: a return is always measured against the money that was in the account when the week began. Weeks that start with under $1,000 in the account are skipped, because a small base turns ordinary dollar swings into extreme returns; when most of a wallet’s PnL falls in skipped weeks, the page says so.</p>
<p>t is computed from those weekly returns with a Student’s t correction for the record’s effective length, then put on the normal scale. A wallet found on a leaderboard of N accounts needs bar(N) from section 3. That bar treats the N accounts as independent; accounts that trade alike are fewer independent bets, which would lower it (about 2.6 for Hyperliquid by our rough estimate, an order of magnitude rather than a measurement). We show both.</p>
<p><strong>Not the Deflated Sharpe Ratio.</strong> Bailey &amp; López de Prado’s DSR deflates a Sharpe ratio for the number of trials using the spread of Sharpe ratios across those trials, and adjusts for skew and fat tails. We do something simpler: a small-sample t and a Bonferroni bar for best-of-N, which needs only N and is conservative when the trials are correlated. The name is about deflating evidence, not a claim to implement DSR.</p>
<p>What a wallet check counts: perps and the spot account, including HIP-4 outcome contracts; not HyperEVM. Vaults are scored on the vault’s own PnL, before the leader’s profit share, and labelled as vaults on the boards.</p>
<p><strong>Drawdown reading.</strong> Next to t, the wallet page shows how far the record is below its own peak, as the sum of the weekly returns since the peak, and the share of time a record with the same measured weekly mean m and variance s² would spend at least that far down: exp(−2m(d + 0.5826 s)/s²) for a drawdown d. That is the stationary drawdown of a random walk with drift, with Siegmund’s correction for sampling once a week; without it the share is up to 1.6 times too high at a Sharpe of 3. The edge is measured on the same record, so the reading leans toward calling a drawdown unusual.</p>

<h2 id="yes">6 · Can it say yes?</h2>
<p>A check that never says yes would be broken, so here is what each verdict means against luck, and what a real edge needs to clear it.</p>
<p><strong>What luck alone produces.</strong> For one wallet picked blind, with no skill behind it, t ≥ 2 turns up about 1 time in 44 (2.3%): that is “promising, not proven”. For a pool of N records with no skill in any of them, the chance that anyone at all clears bar(N) is about the same 2.3%: that is “strong evidence”. On a board ranked by profit, many more records than 1 in 44 can reach t = 2 by luck, because ranking by profit favours lucky streaks; how many is a simulation we have not published yet, so “promising” on a board is a weak signal.</p>
<p><strong>What a real edge needs.</strong> With t ≈ S × √years plus noise, the chance that a trader whose true annualised Sharpe is S clears the Hyperliquid board bar of {hl_bar:.2f}:</p>
{hl_power}
<p>So a Sharpe of 3, which few funds sustain, needs about {s3:.1f} years of record for even odds, and a Sharpe of 2 about {s2:.1f}. The median record in the Hyperliquid PnL top 100 is {med:.1f} years. If every one of those records had a true Sharpe of 3, about {e3:.0f} would clear the bar by now; {strong} do. A board where nobody clears the bar is what short records and no proven skill look like, not a sign that the bar can never be met.</p>
<p><strong>Luck as odds.</strong> The pages show luck as odds and as a percentage: for a record with normal score t picked from a pool of N with no skill in it, the chance that anyone in the pool gets at least that far is 1 − (1 − (1 − Φ(t)))^N. With N = 1 that is the plain one-sided tail, 1 in 44 at t = 2. {coin_line(47248)}</p>
<p><strong>Your pool, your bar.</strong> The wallet page asks how you found the wallet: picked blind (bar 2.00), from a short list of about 10 ({b10:.2f}), from a top 100 ({b100:.2f}), or from the whole board ({hl_bar:.2f}). The answer only you know sets the bar; the default is the whole board, because that is how most wallets are found.</p>

<h2 id="masters">7 · Calibrated on famous records</h2>
<p>The same ruler, on records nobody calls luck. Yearly returns are regressed on the S&amp;P 500 with dividends; the t of the alpha is put on the same normal scale as a wallet’s t.</p>
<div class="table-wrap"><table class="data compact"><thead><tr><th>Record</th><th>Years</th><th class="r">z of alpha</th><th class="r">Beta</th><th>Verdict at the Hyperliquid bar ({hl_bar:.2f})</th></tr></thead><tbody>
<tr><td>Renaissance Medallion, net of fees</td><td>1988–2018</td><td class="r">7.05</td><td class="r">−0.58</td><td>Strong evidence</td></tr>
<tr><td>Berkshire Hathaway (Buffett), per-share market value</td><td>1965–2025</td><td class="r">2.77</td><td class="r">0.90</td><td>Promising, not proven</td></tr>
<tr><td>Berkshire Hathaway, 2001 onward</td><td>2001–2025</td><td class="r">1.79</td><td class="r">0.59</td><td>Looks like luck</td></tr>
</tbody></table></div>
<p>So the ruler says yes when the record is extraordinary and long: Medallion clears the bar for the best of 47,000 with room to spare. Buffett needed six decades to reach “promising”, and his last 25 years alone are within what luck produces against the index. Being proven takes a long record; the oldest record on Hyperliquid starts in May 2023.</p>
<p><strong>Why against the market.</strong> Tested against zero instead, the S&amp;P 500 index itself reaches {SP500_RAW_Z:.2f} over 1965–2025, enough to clear the bar: a raw-return test credits a record for the market rising. Sources: Berkshire’s 2025 shareholder letter (yearly table); Cornell (2019), Table 1, from Zuckerman (2019), estimates rather than audited figures. Script: <a href="{REPO}/blob/main/tools/masters_calibration.py"><code>tools/masters_calibration.py</code></a>.</p>

<h2 id="btc">8 · Wallets against BTC</h2>
<p>For the same reason, the wallet page also shows t after taking out BTC’s moves: each weekly return is fit as alpha × weeks + beta × BTC’s return over the same dates, weighted by interval length, and the t of the alpha is reported with its beta. BTC prices are Hyperliquid’s daily candles. The verdict still uses the unadjusted t, because the frozen cohort’s readings were pre-registered on it; switching will be a dated method change announced on this page. The Evidence Ranking of famous records uses the market-adjusted version throughout.</p>

<h2 id="trackers">How this differs from smart-money trackers</h2>
<p>Hyperdash’s Copy Score, HyprSwarm’s ELO, Hashdive’s Smart Score and Nansen’s labels answer “who is making money, and what are they holding?”. None of them reports how much of a score luck could explain, or allows for the score being the best of tens of thousands. Hyperdash’s own guide shows a wallet with a Copy Score of 96/100 on a 30-day record; under eight weeks, this site does not score a record at all. They tell you who is making money; this tells you whether it could be repeated. Copy-trading venues earn on copied volume, so a score that says the top of the board is luck runs against their business; we are not paid by the rated.</p>

<h2 id="principles">Principles</h2>
<ul>
 <li>Sources are public and fetched on a stated date. Numbers are recomputed, not copied.</li>
 <li>“Cannot be ruled out as seen” is the strongest claim made about a model’s training data. Never “contaminated”.</li>
 <li>A missing input is a finding, not a verdict on the project.</li>
 <li>Findings state what the numbers can and cannot support. No judgement of intent, no investment advice.</li>
 <li>The same rule for every board and every claim. No grading on a curve.</li>
 <li>Corrections are published. If you think a number is wrong, <a href="{REPO}/issues">open an issue</a>.</li>
</ul>

<h2 id="limits">What this does not do</h2>
<ul>
 <li>It does not say any strategy or model is unskilled. It says the evidence cannot yet tell skill from luck.</li>
 <li>It does not detect leakage inside a model; it bounds where leakage cannot be excluded.</li>
 <li>It uses only what a project or board publishes.</li>
 <li>The Hyperliquid wallet check counts what Hyperliquid records for the account: perps and spot, including HIP-4 outcome contracts. Activity on HyperEVM is not included.</li>
 <li>A wallet check measures the evidence in a record, not what copying it would return. A copier trades later and at another size; the shorter the holding period, the more the delay costs (one manager’s example: a strategy that loses 20% of its PnL when delayed by 15 minutes, <a href="https://www.toptradersunplugged.com/podcast/why-investors-keep-getting-trend-following-wrong-ft-patrick-welton/" rel="noopener">source</a>).</li>
 <li>The tail notes read the shape of past weeks. A strategy that sells tail risk and scales its positions to recent volatility can keep that shape ordinary until a large loss and, scaled down, around it.</li>
</ul>

<h2 id="reading">Further reading</h2>
<p class="small">Lo, “The Statistics of Sharpe Ratios” (2002). Bailey &amp; López de Prado, “The Deflated Sharpe Ratio” (2014). Zhang &amp; Stadie, “Temporal Leakage in LLM Backtesting” (arXiv 2608.02985).</p>
</article>
<aside class="aside">
 <div class="box"><h4>On this page</h4><ul><li><a href="#open-book">Open-book months</a></li><li><a href="#clean-months">Clean months needed</a></li><li><a href="#selection">The bar after selection</a></li><li><a href="#leaderboards">Leaderboards</a></li><li><a href="#wallets">Wallets</a></li><li><a href="#yes">Can it say yes?</a></li><li><a href="#masters">Famous records</a></li><li><a href="#btc">Against BTC</a></li><li><a href="#trackers">Vs smart-money trackers</a></li><li><a href="#principles">Principles</a></li><li><a href="#limits">Limits</a></li></ul></div>
 <div class="box"><h4>Try it</h4><ul><li><a href="/check/">Check a backtest in the browser</a></li><li><a href="/api/">Python, CLI and MCP</a></li></ul></div>
</aside>
</div></main>
""" + footer()
    write("method/index.html", page)


# ---------------------------------------------------------------- api

def build_api():
    page = head("API · Evidence Deflator", "Use Evidence Deflator from Python, the command line, or any MCP client. Pure standard library, no keys, no network.", "/api/", alt=API_ALT) + header("api", API_ALT) + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>API</div>
<h1 style="margin-top:16px">Python, CLI and MCP</h1>
<p class="lede" style="margin-top:14px">The engine is pure Python standard library: no keys, no network, no execution. Fetching data is the caller’s job.</p>
<div class="btns" style="margin:22px 0 8px"><button class="copy" data-copy="pip install evidence-deflator">$ pip install evidence-deflator {COPY_ICON}</button><span class="muted small">Python ≥ 3.8 · MIT</span></div>

<h2 id="remote">Hosted: wallet check over HTTP and MCP</h2>
<p>For a Hyperliquid wallet there is nothing to install. The hosted endpoint fetches the public history and scores it with the same code the <a href="/wallet/">wallet page</a> runs in your browser.</p>
<pre class="code solo">curl <span class="s">"https://api.evidencedeflator.com/api/wallet?a=0xADDRESS&amp;picked_from=47153"</span></pre>
<p>Remote MCP (Streamable HTTP, no key): add <code>https://api.evidencedeflator.com/mcp</code> as a connector in Claude, ChatGPT, Cursor or any MCP client. It exposes one tool, <code>hyperliquid_wallet(address, picked_from)</code>. In Claude Code:</p>
<pre class="code solo">claude mcp add --transport http evidence-deflator https://api.evidencedeflator.com/mcp</pre>
<p>Or install the Claude Code plugin, which adds the same tool, a skill that tells the agent how to report the verdict, and a hook that counts every backtest it runs:</p>
<pre class="code solo">/plugin marketplace add Beltran12138/evidence-deflator
/plugin install evidence-deflator@evidence-deflator</pre>

<h2 id="python">Python</h2>
<pre class="code solo"><span class="k">from</span> evidence_deflator <span class="k">import</span> effective_window, selection_penalty, months_for_power

w = effective_window(cutoff=<span class="s">"2024-10"</span>, start=<span class="s">"2020-01"</span>, end=<span class="s">"2025-06"</span>, trials=<span class="o">41</span>)
w.open_book_months   <span class="c"># 58  months on or before the cutoff</span>
w.effective_months   <span class="c"># 8   clean months</span>
w.months_required    <span class="c"># 128 clean months a Sharpe-1 result needs, best of 41</span>
w.verdict            <span class="c"># 'underpowered'</span>
w.to_dict()          <span class="c"># everything, with the reasoning as plain text</span>

selection_penalty(<span class="o">41</span>).t_adjusted   <span class="c"># 3.26</span>
months_for_power(<span class="o">2.0</span>)               <span class="c"># 12</span></pre>
<p class="small muted">Pass <code>cutoff_source=</code> with the provider’s documentation URL; without one the result says the cutoff is unverified. Pass <code>effective_trials=</code> when you have measured how correlated the attempts are.</p>

<h2 id="cli">Command line</h2>
<pre class="code solo">git clone {REPO}
cd evidence-deflator
python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06
python tools/record.py --start 2026-03 --end 2026-08 --sharpe 3 --trials 4800</pre>

<h2 id="mcp">MCP server</h2>
<p>For Claude, Cursor and any other MCP client. Tools include <code>knowledge_window</code>, <code>track_record</code>, <code>counterfactual_audit</code> and <code>trace_audit</code>.</p>
<pre class="code solo">pip install <span class="s">"evidence-deflator[mcp]"</span>

{{
  <span class="s">"mcpServers"</span>: {{
    <span class="s">"evidence-deflator"</span>: {{ <span class="s">"command"</span>: <span class="s">"evidence-deflator-mcp"</span> }}
  }}
}}</pre>

<h2 id="data">Data</h2>
<p>Each leaderboard edition is published as JSON under CC BY 4.0: <a href="/leaderboard/2026-10.json"><code>/leaderboard/2026-10.json</code></a>. Fields per entry: rank, name, return_pct, days, sharpe, t.</p>

<h2 id="hosted">Hosted evidence score</h2>
<p>A hosted endpoint that returns an evidence score for a strategy, agent or leaderboard entry is planned. If you run a framework, a competition or an allocation process and would use one, <a href="{REPO}/issues/new?title=Hosted%20API%3A%20use%20case">tell us the use case</a>.</p>
</article>
<aside class="aside">
 <div class="box"><h4>On this page</h4><ul><li><a href="#python">Python</a></li><li><a href="#cli">Command line</a></li><li><a href="#mcp">MCP server</a></li><li><a href="#data">Data</a></li><li><a href="#hosted">Hosted evidence score</a></li></ul></div>
 <div class="box"><h4>Links</h4><ul><li><a href="https://pypi.org/project/evidence-deflator/">PyPI</a></li><li><a href="{REPO}">GitHub</a></li><li><a href="/method/">Method</a></li></ul></div>
</aside>
</div></main>
""" + footer()
    write("api/index.html", page)


# ---------------------------------------------------------------- wallet check

WALLET_ALT = {"en": "/wallet/", "zh-Hans": "/zh-hans/", "zh-Hant": "/zh-hant/"}

WALLET_T_EN = {
    "say": {
        "loses": ["Losing, and not by chance", "tag-red", "t is −2 or lower: over the weeks that can be measured, this wallet lost money too consistently for luck to explain."],
        "luck": ["Looks like luck", "tag-red", "t is below 2: records like this turn up by chance often, so this one says little about skill either way."],
        "clears_single": ["Promising, not proven", "tag-amber", "Strong enough for a wallet picked blind: luck alone gets that far about 1 time in 44. For one found {FROM}, the bar is t ≥ {BAR}, and this record is not there yet."],
        "clears_board": ["Strong evidence", "tag-green", "Clears t ≥ {BAR}, the bar for a wallet found {FROM}. If none of them had any skill, luck would carry anyone at all past this bar only about 2% of the time."],
        "too_short": ["Too early to tell", "tag-grey", "Fewer than 8 weeks of history with at least $1,000 in the account. Not a verdict on the trader, only on how much record there is."],
    },
    "tag": {"loses": "losing", "luck": "looks like luck", "clears_single": "promising", "clears_board": "strong", "too_short": "too early"},
    "found": {"q": "How did you find this wallet?",
              "opts": [[1, "Picked blind, or recommended", "blind, without looking at any ranking"],
                       [10, "From a short list of ~10", "on a short list of about 10"],
                       [100, "From a top 100", "in the top 100 of a board"],
                       [0, "Anywhere among {N} {U}", "anywhere among {N} {U}"]],
              "hint": "The pool you picked from sets the bar. If you saw it on a leaderboard, the whole board was the pool.",
              "blindStrong": "Clears t ≥ 2.00, the bar for a wallet picked blind. With no skill behind it, a record gets this far by luck about 1 time in 44."},
    "luck": {"label": "chance that luck alone gets a record this strong, for a wallet found {FROM}", "most": "more likely than not", "certain": "almost certain",
             "one": "1 in {X}", "million": "{M} million"},
    "tLabel": "Sharpe {S}",
    "btc": "After taking out BTC’s moves: t = {T}, with a beta of {B} to BTC over {N} weeks. The verdict above still uses the t without this adjustment; switching is planned as a dated method change.",
    "meterAria": "t against the two bars", "meterT2": "t = 2 · one test", "meterBest": "best of {N} · {bar}",
    "notAddr": ["That is not a Hyperliquid address", "Expected 0x followed by 40 hex characters."],
    "reading": "Reading the public record…", "noReach": "Could not reach Hyperliquid", "noHist": "No history for this address",
    "months": {"noSharpe": "needs 8 weeks of record before this can be estimated",
               "never": ["never", "at a Sharpe of zero or below, no length of record clears the bar"],
               "done": "more months needed: the record already clears the bar",
               "more": "more record needed to clear the bar, if the Sharpe held", "yr": " yr", "mo": " mo"},
    "notes": {"no_losing_week": "No losing week in the record. Consistent with market making, funding carry or selling tail risk; t measures consistency, not the size of a loss that has not happened yet.",
              "one_week_majority": "One week produced more than half of all the gains. The record rests mostly on that week.",
              "pnl_outside_record": "Most of the all-time PnL was booked in periods that started with under $1,000 in the account, so it cannot be turned into a return. The verdict covers only the weeks that can be measured."},
    "wnote": "History from {start}. Read {now} UTC from api.hyperliquid.xyz.",
    "dd": {"peak": "At its peak now. Deepest drawdown so far: weekly returns adding up to −{deep}%.",
           "below": "Below its peak: since then, its weekly returns add up to −{now}%, over {wk} weeks. Deepest so far, measured the same way: −{deep}%.",
           "share": " If the edge is what the record shows, a record like this spends {share}% of its time at least this far down: {read}",
           "ordinary": "an ordinary drawdown for it.",
           "unusual": "unusual, though not out of line.",
           "rare": "rare. Either bad luck, or the edge is smaller than the record shows.",
           "noEdge": " The record shows no positive edge, so no drawdown is ordinary for it."},
    "charts": {"curveCap": "The record: weekly returns added up since the start. Shaded: the current drawdown from the peak.",
               "curveAria": "Cumulative weekly returns of the record", "frozen": "frozen",
               "projCap": "If the Sharpe of {S} held: how t grows with more record, and when it would reach each bar.",
               "projNone": "No positive edge measured, so more of the same record would not raise t.",
               "projAria": "Projected t against record length", "now": "now", "over30": "more than 30 years",
               "nextMore": "More record: about {m} more at a steady Sharpe of {S} to reach the bar of {BAR}.",
               "nextNoEdge": "A positive edge: at a Sharpe of zero or below, no length of record clears any bar.",
               "nextCohort": "The forward record: this wallet is one of the 200 frozen on 2026-10-14; its record after that day is scored separately, first reading 2026-12-09.",
               "nextNotCohort": "A forward record: only results after the day you picked this wallet test the pick. Note today's date and check again.",
               "nextDd": "A drawdown much deeper than the ones above, which would mean the edge is smaller than the record shows."},
    "unitAcct": "accounts", "unitVault": "vaults",
    "vault": "This is a vault: {name}. The leader holds {lf}% of it and takes {c}% of depositors' profits; the score is on the vault's PnL before that cut.",
    "vaultBar": " Its bar assumes it was picked from the {NV} vaults Hyperliquid lists, open and closed.",
    "selfPath": "/wallet/", "countUrl": "https://api.evidencedeflator.com/api/count?k=web&l=en",
}


def asset(name):
    """/assets/<name>?v=<content hash>: the Cloudflare edge caches assets, so a changed file needs a new URL."""
    with open(os.path.join(DOCS, "assets", name), "rb") as f:
        return f"/assets/{name}?v={hashlib.sha256(f.read()).hexdigest()[:8]}"


def wallet_scripts(n_accounts, strings, n_vaults=None):
    data = json.dumps({"N": n_accounts, "NV": n_vaults, "T": strings}, ensure_ascii=False).replace("</", "<\\/")
    return (f'<script src="/assets/site.js"></script><script src="{asset("hl.js")}"></script>\n'
            f'<script>window.WALLET = {data};</script>\n<script src="{asset("wallet.js")}"></script>\n')


def build_wallet():
    p = os.path.join(DOCS, "data", "hl", "latest.json")
    with open(p, encoding="utf-8") as f:
        hl = json.load(f)
    pnl, roi = hl["boards"]["pnl"], hl["boards"]["roi30"]
    scored = sorted((r for r in pnl["rows"] if r["t"] is not None), key=lambda r: -r["t"])
    examples = [("Highest t in the PnL top 100", scored[0]["address"]),
                ("Median of the PnL top 100", scored[len(scored) // 2]["address"]),
                ("#1 by 30-day ROI", roi["rows"][0]["address"])]
    ex = "".join(f'<button class="linkbtn" data-ex="{a}">{html.escape(t)}</button>' for t, a in examples)

    def short(a):
        return a[:6] + "…" + a[-4:]

    def money(x):
        x = float(x)
        return f"${x/1e6:,.1f}M" if abs(x) >= 1e6 else f"${x/1e3:,.0f}k"

    rows = ""
    for r in pnl["rows"][:15]:
        t = "—" if r["t"] is None else f"{r['t']:.2f}"
        w = 0 if r["t"] is None else min(abs(r["t"]) / pnl["t_bar_best_of_n"], 1) * 100
        neg = " neg" if (r["t"] or 0) < 0 else ""
        dag = "<sup>†</sup>" if "pnl_outside_record" in r["flags"] else ""
        rows += (f'<tr><td class="r">{r["rank"]}</td><td><a class="mono" href="/wallet/?a={r["address"]}">{short(r["address"])}</a>'
                 f'{" · " + html.escape(r["display"]) if r.get("display") else ""}'
                 f'{" <span class=" + chr(34) + "tag tag-grey" + chr(34) + ">vault · " + html.escape(r["vault"]) + "</span>" if r.get("vault") else ""}</td><td class="r">{money(r["pnl_all_time"])}</td>'
                 f'<td class="r">{r["weeks"] if r["weeks"] else "—"}</td><td class="r">{t}{dag}</td>'
                 f'<td><span class="mbar"><span class="track"><span class="fill{neg}" style="width:{w:.1f}%"></span>'
                 f'<span class="t2" style="left:{2 / pnl["t_bar_best_of_n"] * 100:.1f}%"></span></span></span></td></tr>')

    c = hl.get("cohort")
    cohort_html = ""
    if c:
        if c["scored"]:
            reading = (f'<div><b class="c-accent">{c["n_t_ge_2"]} / {c["scored"]}</b><span>reach t = 2 on the record since the freeze</span></div>')
        else:
            reading = f'<div><b>{c["first_readings"]}</b><span>first readings: a wallet needs 8 weeks of record after the freeze before it gets a t</span></div>'
        cohort_html = f"""
<section id="forward"><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Forward record · frozen {c['frozen_at'][:10]}</div><h2 style="margin-top:12px">The same {c['members']} wallets, scored only on what they do from now on.</h2>
 <p>A record found by looking back is a record chosen after the fact. So on {c['frozen_at'][:10]} we froze today’s two top-100 lists and publish, every day, how each wallet does after that moment. Nothing before the freeze counts, and the list cannot be edited: its hash is below and its history is in git.</p></div></div>
 <div class="stats" style="margin:8px 0 18px">
  <div><b>{c['members']}</b><span>wallets frozen at {c['frozen_at'].replace('T', ' ').replace('Z', ' UTC')}</span></div>
  {reading}
  <div><b>daily</b><span>refreshed from the public API by a scheduled job in the repository</span></div>
 </div>
 <p class="muted small mono" style="overflow-wrap:anywhere">{html.escape(c['file'])} · sha256 {c['sha256']}</p>
 <div class="btns" style="margin-top:12px"><a class="btn btn-secondary" href="/data/hl/{html.escape(c['file'])}">Frozen list</a><a class="btn btn-secondary" href="/data/hl/latest.json">Daily scores (JSON)</a><a class="btn btn-secondary" href="/record/">What would count against us</a></div>
</div></section>
"""

    page = head("Check a Hyperliquid wallet · Evidence Deflator",
                "Paste any Hyperliquid address. See whether its record can be told apart from luck, and how many more months it would need.",
                "/wallet/", extra=ld({**APP_LD, "@type": "WebApplication", "name": "Evidence Deflator · Hyperliquid wallet check",
                                       "url": SITE + "/wallet/", "operatingSystem": "Web"}), alt=WALLET_ALT) + header("wallet", WALLET_ALT) + f"""
<main>
<div class="container page-head">
 <nav class="venue-switch" aria-label="Venue"><a href="/wallet/" aria-current="page">Hyperliquid</a><a href="/polymarket/">Polymarket</a></nav>
 <div class="eyebrow"><span class="dot"></span>Hyperliquid · wallet check · public data, computed in your browser</div>
 <h1>Paste a Hyperliquid address. See how much of its record counts.</h1>
 <p class="lede">A leaderboard shows who made the most. It does not show whether that could have been luck. This reads the wallet’s public PnL history and answers one question: how strong is the evidence, and how long until it could be strong enough?</p>
 <form class="wcheck" id="wform" autocomplete="off">
  <input id="waddr" name="a" placeholder="0x… Hyperliquid address" spellcheck="false" aria-label="Hyperliquid address">
  <button class="btn btn-primary" type="submit">Check <span class="arr">→</span></button>
 </form>
 <div class="wex muted small">Try: {ex}</div>
 {ELSEWHERE_EN}
</div>

<div class="container" id="wout" hidden>
 <div class="instrument wres">
  <div class="instrument-head"><span class="t mono" id="wid"></span><span id="wtag"></span></div>
  <div class="instrument-body"><h2 id="whead" style="margin:18px 4px 6px"></h2><p id="wsub" class="muted" style="margin:0 4px 10px"></p>
   <p id="wvault" class="muted small" style="margin:0 4px 10px" hidden></p>
   <div class="wfound" id="wfound" role="group" hidden></div>
   <div class="chart" id="wmeter"></div></div>
  <div class="instrument-foot">
   <div><b id="wl">—</b><span><b class="mono" id="wlp" style="display:inline;font-size:inherit"></b> · <span id="wll">chance that luck alone gets a record this strong</span></span></div>
   <div><b id="ww">—</b><span>weeks of record above $1k</span></div>
   <div><b id="wm">—</b><span id="wml">months of record to clear the bar, at this Sharpe</span></div>
   <div><b id="wt">—</b><span>t, adjusted for record length (≈ Sharpe × √years) · <span id="ws">annualised Sharpe, weekly</span></span></div>
  </div>
 </div>
 <p class="muted small" id="wbtc" style="margin:10px 4px 0" hidden></p>
 <div class="wcharts" id="wcharts" hidden>
  <figure class="wfig"><figcaption id="wcurvecap"></figcaption><div class="chart" id="wcurve"></div></figure>
  <figure class="wfig"><figcaption id="wprojcap"></figcaption><div class="chart" id="wproj"></div></figure>
 </div>
 <ul class="wflags" id="wflags"></ul>
 <div class="wdd" id="wdd" hidden><p id="wddt"></p></div>
 <div class="wnext" id="wnextbox" hidden><h3>What would change the verdict</h3><ul id="wnext"></ul></div>
 <p class="wcta">Deciding whether to put money behind this record? <a href="/memo/sample/">See what a one-page memo covers</a> · <a href="{ISSUE_AUDIT}">request one</a>.</p>
 <details class="wfine"><summary>Read this before acting on it</summary>
  <p>t is about the record, not about what copying it would earn. A copier trades after the trader and at a different size; the shorter the holding period, the more of the edge that delay costs.</p>
  <p>The drawdown reading measures the edge on this same record, usually one found for being good, so the edge is more likely too high than too low; with a smaller true edge, drawdowns are more common than it says. A reading, not a signal to hold or sell.</p>
 </details>
 <div class="btns" style="margin:18px 0 8px"><button class="btn btn-secondary copy" id="wcopy" data-copy=""><span class="cp">Copy link to this result</span><span class="ok">Copied</span></button>
  <a class="btn btn-secondary" id="whl" href="#" rel="noopener">Open on Hyperliquid</a></div>
 <p class="muted small" id="wnote"></p>
</div>

<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Hyperliquid’s own leaderboard, rescored · {hl['fetched'][:10]}</div><h2 style="margin-top:12px">The top of the board is ranked by profit. {"None of it has" if pnl['n_t_ge_bar'] == 0 else str(pnl['n_t_ge_bar']) + " of it " + ("has" if pnl['n_t_ge_bar'] == 1 else "have")} strong evidence yet; {pnl['n_t_ge_2'] - pnl['n_t_ge_bar']} {"is" if pnl['n_t_ge_2'] - pnl['n_t_ge_bar'] == 1 else "are"} promising.</h2></div></div>
 <div class="stats" style="margin:8px 0 26px">
  <div><b class="c-accent">{pnl['n_t_ge_bar']} / {pnl['scored']}</b><span>of the all-time PnL top 100 have strong evidence: they clear the best-of-{pnl['ranked_from']:,} bar (t ≥ {pnl['t_bar_best_of_n']:.2f})</span></div>
  <div><b>{pnl['n_t_ge_2'] - pnl['n_t_ge_bar']} / {pnl['scored']}</b><span>are promising, not proven: t ≥ 2, enough for a wallet picked blind</span></div>
  <div><b class="c-accent">{roi['n_t_ge_bar']} / {roi['scored']}</b><span>of the 30-day ROI top 100 (account ≥ $10k) have strong evidence; {roi['n_t_ge_2'] - roi['n_t_ge_bar']} are promising.</span></div>
 </div>
 <div class="table-wrap"><table class="data"><thead><tr><th class="r">PnL rank</th><th>Wallet</th><th class="r">All-time PnL</th><th class="r">Weeks</th><th class="r">t</th><th>Share of the bar</th></tr></thead><tbody>{rows}</tbody></table></div>
 <p class="muted small" style="margin-top:10px">Bar: one result needs t ≥ 2. A wallet found by scanning a board of N accounts needs the best-of-N bar, {pnl['t_bar_best_of_n']:.2f} here. † Most of this wallet’s PnL was booked while the account held under $1,000, so it cannot be turned into a return; t covers only the weeks that can be measured. All {pnl['shown']} + {roi['shown']} rows: <a href="/data/hl/latest.json">latest.json</a> (built by <a href="{REPO}/blob/main/tools/build_hl_board.py"><code>tools/build_hl_board.py</code></a>).</p>
</div></section>
{cohort_html}
<section><div class="container narrow prose">
 <h2>How it reads a wallet</h2>
 <p><strong>Returns come from PnL, not account value.</strong> Account value moves when the owner deposits or withdraws; PnL does not. Each week’s return is the change in cumulative PnL divided by the account value at the start of the week. Weeks that start below $1,000 are skipped.</p>
 <p><strong>Weekly, because the history is.</strong> Hyperliquid keeps older history about a week apart and recent history minutes apart. Everything is put on one weekly grid; a week with no new data point is merged into the next one, not counted as a zero.</p>
 <p><strong>Short records are not over-read.</strong> A t computed from a handful of weeks has fat tails: with eight weeks and no skill at all, t ≥ 2 turns up about twice as often as the bar assumes. So t is taken from Student’s t with the record’s effective degrees of freedom (fewer when a few long gaps carry the record) and put back on the usual scale. For a long record it is close to Sharpe × √years; for a short one it is lower. Tested: with no skill, the share of records reaching 2 stays at the nominal 2.3% however sparsely the history was sampled.</p>
 <p><strong>Two bars.</strong> If you came to this wallet with no prior selection, t ≥ 2 is the usual bar. If you found it by sorting a leaderboard, you picked the best of many, and the bar rises with the number you picked from (Bonferroni on {pnl['ranked_from']:,} accounts: {pnl['t_bar_best_of_n']:.2f}). Most people find wallets on leaderboards. That bar counts every account as independent; accounts that trade alike are fewer independent bets, which would lower it to about 2.6 by our <a href="https://github.com/Beltran12138/evidence-deflator#a-track-record-with-no-model-behind-it">rough estimate</a> (an order of magnitude, not a measurement).</p>
 <p><strong>What t cannot see.</strong> Tail risk that has not happened yet. A strategy that sells insurance can show no losing week for a long time. Where the record has no losing week, or one week made most of the gains, the page says so. A seller that scales its positions to recent volatility can keep its weeks looking ordinary before a large loss and, scaled down, around it, so these notes can miss it.</p>
 <p><strong>The drawdown reading.</strong> Most money arrives after a strong run and leaves in the drawdown that follows, which is often an ordinary one; the gap between a strategy’s return and its investors’ return is, in one manager’s words, “usually the biggest cost” (<a href="https://www.toptradersunplugged.com/podcast/why-investors-keep-getting-trend-following-wrong-ft-patrick-welton/" rel="noopener">Patrick Welton on Top Traders Unplugged</a>). So the page says how far the record is below its own peak, in weekly returns added up since the peak (the same returns t uses; compounding would describe a portfolio nobody held, since accounts add and withdraw money), and how much of its time a record with the same measured edge and volatility spends at least that far down. Under 2% is rare enough to doubt the edge; 10% or more is ordinary. The share comes from the drawdown distribution of a random walk with that drift, corrected for weekly sampling, and is checked against simulation.</p>
 <p><strong>Evidence is not what a copier gets.</strong> t measures the record the trader made. A copier enters after the trader, at another size and with other fees; the shorter the holding period, the more of the edge the delay costs, and a size that works for $50k may move the market at $5M. A record that clears the bar is evidence about the trader, not a forecast of your return.</p>
 <p><strong>What it counts.</strong> The PnL Hyperliquid records for the account: perps and the spot account, which holds HIP-4 outcome contracts. Trading on HyperEVM, such as Papertrade or HyperEVM options protocols, is not in it. A wallet that sells options on HyperEVM and hedges with perps shows only the hedge.</p>
 <p class="muted small">Not investment advice. Public data from <code>api.hyperliquid.xyz</code>, fetched by your browser. {PRIVACY} Method: <a href="/method/">Method</a>, Lo (2002), Bailey &amp; López de Prado (2014).</p>
</div></section>
</main>
""" + footer(wallet_scripts(pnl["ranked_from"], WALLET_T_EN, (hl.get("vaults") or {}).get("listed")))
    write("wallet/index.html", page)


def build_polymarket():
    """Polymarket wallet check: audit 008's per-position test, run in the browser (assets/polymarket.js)."""
    with open(os.path.join(DOCS, "data", "cex", "polymarket-2026-10-15.json"), encoding="utf-8") as f:
        pm = json.load(f)
    n, bar_ = pm.get("n_floor_revised_2026_10_16", pm["n_floor"]), pm.get("bar_best_of_n_floor_revised", pm["bar_best_of_n_floor"])
    rows = {r["name"]: r for r in pm["rows"]}
    examples = [("#1 by all-time profit", rows["Theo4"]["wallet"]),
                ("Looks like a star on closed positions only", rows["DrPufferfish"]["wallet"]),
                ("Highest z in the top 50", rows["asparagus2012"]["wallet"])]
    ex = "".join(f'<button class="linkbtn" data-ex="{a}">{html.escape(t)}</button>' for t, a in examples)
    data = json.dumps({"N": n, "bar": bar_, "selfPath": "/polymarket/",
                       "countUrl": "https://api.evidencedeflator.com/api/count?k=pm&l=en"})
    page = head("Polymarket wallet check · Evidence Deflator",
                "Paste a Polymarket wallet or username and see whether its record of picks can be told apart from luck, position by position, counting the losers Polymarket lists separately.",
                "/polymarket/") + header("wallet") + f"""
<main>
<div class="container page-head">
 <nav class="venue-switch" aria-label="Venue"><a href="/wallet/">Hyperliquid</a><a href="/polymarket/" aria-current="page">Polymarket</a></nav>
 <div class="eyebrow"><span class="dot"></span>Polymarket · wallet check · public data, computed in your browser</div>
 <h1>Paste a Polymarket wallet. See whether its picks beat the prices it paid.</h1>
 <p class="lede">A profit board shows who made the most. It does not show whether that wallet bought at prices that were too low for how things turned out, more often than chance allows. This page reads every resolved position and answers that.</p>
 <form class="wcheck" id="pform" autocomplete="off">
  <input id="paddr" name="a" placeholder="0x… wallet, polymarket.com profile link, or username" spellcheck="false" aria-label="Polymarket wallet or username">
  <button class="btn btn-primary" type="submit">Check <span class="arr">→</span></button>
 </form>
 <div class="wex muted small">Try: {ex}</div>
 <p class="muted small elsewhere">Hyperliquid wallets: <a href="/wallet/">the wallet check</a>.</p>
</div>

<div class="container" id="pout" hidden>
 <div class="instrument wres">
  <div class="instrument-head"><span class="t mono" id="pid"></span><span id="ptag"></span></div>
  <div class="instrument-body"><h2 id="phead" style="margin:18px 4px 6px"></h2><p id="psub" class="muted" style="margin:0 4px 10px"></p>
   <div class="chart" id="pmeter"></div></div>
  <div class="instrument-foot">
   <div><b id="pz">—</b><span>z, positions in one event counted as one bet</span></div>
   <div><b id="pev">—</b><span>events</span></div>
   <div><b id="pres">—</b><span>resolved positions</span></div>
   <div><b id="pedge">—</b><span>average edge per share: outcome minus price paid</span></div>
  </div>
 </div>
 <ul class="wflags" id="pflags"></ul>
 <div class="btns" style="margin:18px 0 8px"><button class="btn btn-secondary copy" id="pcopy" data-copy=""><span class="cp">Copy link to this result</span><span class="ok">Copied</span></button>
  <a class="btn btn-secondary" id="ppm" href="#" rel="noopener">Open on Polymarket</a></div>
 <p class="muted small" id="pnote"></p>
</div>

<section><div class="container narrow prose">
 <h2>How it reads a wallet</h2>
 <p><strong>One question per position.</strong> A share bought at price p pays $1 if it wins. With no skill, it wins with probability p, so the edge, outcome minus price paid, averages zero. Someone who keeps buying at prices that turn out too low has a positive edge, and z measures how far that is from chance.</p>
 <p><strong>Bets on one event are one bet.</strong> Ten positions on the same election share one outcome. z sums the edge within each event before comparing it with chance, so a wallet cannot look strong by splitting one view into many positions.</p>
 <p><strong>The losers Polymarket lists elsewhere.</strong> A losing share is worth nothing, so many are never redeemed. They stay among open positions, not closed ones. Counting only closed positions made 11 of the profit top 50 look like stars in <a href="/audits/008-polymarket-profit-board.html">audit 008</a>; this page counts both.</p>
 <p><strong>Two bars.</strong> z ≥ 2 is the usual bar for a wallet you came to with no prior selection. A wallet found on the profit board was picked from at least {n:,} wallets, so it needs z ≥ {bar_:.2f}. That is a floor: the board reports no total, and a username search on it returns a wallet ranked {n:,}. Of the top 50 in audit 008, none came close; the highest z was 2.40.</p>
 <p><strong>What z cannot see.</strong> Position sizes (each position counts once; a few huge winning bets can make the money while the picks overall are ordinary), and whether the wallet traded on information others did not have.</p>
 <p class="muted small">Not investment advice. Public data from <code>data-api.polymarket.com</code>, fetched by your browser; the wallet is never sent to us, and each check adds one tally with no address. Method: <a href="/audits/008-polymarket-profit-board.html">audit 008</a>, <a href="{REPO}/blob/main/tools/audit_polymarket.py"><code>tools/audit_polymarket.py</code></a>.</p>
</div></section>
</main>
""" + footer(f'<script src="/assets/site.js"></script>\n<script>window.PM = {data};</script>\n<script src="{asset("polymarket.js")}"></script>\n')
    write("polymarket/index.html", page)


MEMO_ALT = {"en": "/memo/sample/", "zh-Hans": "/zh-hans/memo/sample/", "zh-Hant": "/zh-hant/memo/sample/"}


def build_memo_sample():
    """/memo/sample/: the one-page memo format, shown on one public record (numbers from tools/memo_sample.py)."""
    src = "hlp-2026-10-16.json"
    with open(os.path.join(DOCS, "data", "memo", src), encoding="utf-8") as f:
        m = json.load(f)
    with open(os.path.join(DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        hl = json.load(f)
    sc, v, b = m["score"], m["vault"] or {}, m["bars"]
    kids = set(((v.get("relationship") or {}).get("data") or {}).get("childAddresses") or [])
    on_board = [r for r in hl["boards"]["pnl"]["rows"] if r["address"] in kids]
    kid_list = ", ".join(f'#{r["rank"]} {html.escape(r["vault"] or (r["address"][:6] + "…" + r["address"][-4:]))}' for r in on_board)
    cohort = hl.get("cohort") or {}
    a = m["address"]
    yes, no = '<span class="c-pos">clears</span>', '<span class="c-accent">does not clear</span>'
    mm = m["months_more_at_this_sharpe"]["board_independent"]
    page = head("Sample evidence memo · Hyperliquidity Provider (HLP) · Evidence Deflator",
                "What a one-page evidence memo looks like, on one public record: Hyperliquid's HLP vault, the strongest record on the all-time PnL board.",
                "/memo/sample/", alt=MEMO_ALT) + header("", MEMO_ALT) + f"""
<main><div class="container doc" style="max-width:820px;padding-block:56px 72px">
 <div class="eyebrow"><span class="dot"></span>Sample evidence memo · {m['fetched'][:10]}</div>
 <h1 style="margin-top:14px">Hyperliquidity Provider (HLP)</h1>
 <p class="muted small mono" style="margin-top:10px">vault <a href="/wallet/?a={a}">{a}</a> · data from api.hyperliquid.xyz, fetched {m['fetched'].replace('T', ' ').replace('+00:00', ' UTC')} · <a href="/data/memo/{src}">raw numbers</a></p>

 <div class="example-result" style="max-width:none;margin-top:28px;cursor:default">
  <span class="eyebrow">The question</span>
  <span class="ex-say" style="margin-top:8px">A depositor is looking at HLP because it is the strongest record on Hyperliquid’s all-time PnL board. How much of that record counts as evidence?</span>
  <span class="ex-head" style="margin-top:16px"><b>Short answer</b><span class="tag tag-amber">Promising, not proven</span></span>
  <span class="ex-say">Strong for a record picked blind: t = {sc['t']:.2f} over {sc['weeks']:.0f} weeks. Not yet strong enough for the best of {m['board_n']:,} accounts (bar {b['board_independent']:.2f}); at its own Sharpe of {sc['sharpe']:.2f} it needs about {mm:.0f} more months. And what it shows is not a trader’s skill: it is the exchange’s own vault, which earns from market making, liquidations and platform fees.</span>
 </div>

 <h2 style="margin-top:44px">1 · What the record is</h2>
 <ul>
  <li>A Hyperliquid vault, described by Hyperliquid as: “{html.escape(v.get('description') or '')}” Deposits are {'open' if v.get('allow_deposits') else 'closed'}. The leader holds {100 * (v.get('leader_fraction') or 0):.2f}% and takes {100 * (v.get('leader_commission') or 0):.0f}% of depositors’ profits.</li>
  <li>It is the parent of {len(kids)} child vaults. {len(on_board)} of them are also on the all-time PnL top 100 ({kid_list}), so that board shows one operation {len(on_board) + 1} times.</li>
  <li>History {m['history_from']} to {m['history_to']}: {sc['intervals']} scored intervals covering {sc['weeks']:.1f} weeks. Weeks with no new sample in Hyperliquid’s history are merged into the next interval rather than counted as flat.</li>
  <li>Coverage: HLP trades on HyperCore, so its whole PnL is in the record Hyperliquid keeps; the HyperEVM gap noted on the wallet page does not apply. Deposits and withdrawals change the account value, never the PnL.</li>
 </ul>

 <h2 style="margin-top:36px">2 · The numbers</h2>
 <div class="table-wrap"><table class="data memo-table">
  <thead><tr><th>Measure</th><th class="r">Value</th><th>Reading</th></tr></thead>
  <tbody>
   <tr><td>t (Student’s t, {sc['dof']:.0f} effective degrees of freedom)</td><td class="r mono">{sc['t']:.2f}</td><td>Annualised Sharpe {sc['sharpe']:.2f} × √{sc['weeks'] / 52:.1f} years, adjusted for record length</td></tr>
   <tr><td>Bar for a record picked blind</td><td class="r mono">{b['single']:.2f}</td><td>{yes if m['clears']['single'] else no}</td></tr>
   <tr><td>Bar for the best of {m['board_n']:,}, accounts treated as independent</td><td class="r mono">{b['board_independent']:.2f}</td><td>{yes if m['clears']['board_independent'] else no}; about {mm:.0f} more months at this Sharpe</td></tr>
   <tr><td>Same bar, rough allowance for accounts that trade alike</td><td class="r mono">≈&nbsp;{b['board_correlated_rough']:.1f}</td><td>{yes if m['clears']['board_correlated_rough'] else no}; an order of magnitude, not a measurement</td></tr>
  </tbody></table></div>

 <h2 style="margin-top:36px">3 · What t cannot see</h2>
 <ul>
  <li><strong>Shape of the record.</strong> {100 * m['weeks_positive_share']:.0f}% of intervals were positive. The worst three were {', '.join(f'{100 * x:.1f}%' for x in m['worst_weeks'])}; the deepest drawdown, compounding the intervals, was {abs(100 * m['max_drawdown_compounded']):.1f}%. Skew is {m['skew']:+.1f}: the largest moves were gains. That is not the shape of a strategy that wins small and loses big, at least so far.</li>
  <li><strong>The tail that has not happened.</strong> A vault that takes over liquidated positions is on the other side when prices gap. The worst case it is exposed to need not appear in {sc['weeks'] / 52:.1f} years of history, and t cannot price it.</li>
  <li><strong>Where the returns come from.</strong> Fees and liquidation flow are income from the venue’s own activity. For a depositor the question is less whether someone is skilled than whether that income continues, and on what terms.</li>
 </ul>

 <h2 style="margin-top:36px">4 · What would change the verdict</h2>
 <ul>
  <li>More record: at a steady Sharpe of {sc['sharpe']:.2f}, about {mm:.0f} more months to clear the best-of-{m['board_n']:,} bar.</li>
  <li>The forward record: HLP is one of the {cohort.get('members', 200)} wallets frozen on {cohort.get('frozen_at', '')[:10]}. Its score on the record after the freeze is published daily from {cohort.get('first_readings', '')}.</li>
  <li>A drawdown well beyond the {abs(100 * m['max_drawdown_compounded']):.1f}% seen so far, which would show the tail described above.</li>
 </ul>

 <h2 style="margin-top:36px">5 · Method and reproducibility</h2>
 <p>Same estimator as the <a href="/wallet/?a={a}">wallet check</a>; definitions in the <a href="/method/#wallets">method</a>. To recompute: <code>python tools/memo_sample.py {a} out.json --board-n {m['board_n']}</code> from <a href="{REPO}">the repository</a>.</p>
 <p class="muted small" style="margin-top:28px;border-top:1px solid var(--rule);padding-top:16px">This page shows the format of a one-page evidence memo, on a public record. It is not investment advice. HLP was not consulted and paid nothing; we never take money from the party being scored.</p>
</div></main>
""" + footer()
    write("memo/sample/index.html", page)


def build_404():
    page = head("Not found · Evidence Deflator", "Page not found.", "/404.html") + header("") + """
<main class="container page-head" style="min-height:50vh"><div class="eyebrow"><span class="dot"></span>404</div>
<h1>This page cannot be ruled out as missing.</h1><p class="lede">Try the <a href="/leaderboard/">leaderboard</a>, the <a href="/audits/">audits</a> or the <a href="/">home page</a>.</p></main>
""" + footer()
    write("404.html", page)


HAND_PAGES = [  # hand-maintained pages that only receive the shared head links, header and footer
    ("check/index.html", "check", "/check/"),
    ("audit.html", "audits", "/audit.html"),
    ("case-nuclear.html", "audits", "/case-nuclear.html"),
    ("how-many-decisions.html", "check", "/how-many-decisions.html"),
]


def inject_chrome():
    """Refresh the marked head/header/footer blocks inside the hand-maintained pages."""
    foot = "<footer" + footer().split("<footer", 1)[1].rsplit("</body>", 1)[0]
    for rel, active, path in HAND_PAGES:
        p = os.path.join(DOCS, rel)
        with open(p, encoding="utf-8") as f:
            s = f.read()
        links = "\n".join([
            f'<link rel="icon" href="{FAVICON}">',
            f'<link rel="canonical" href="{SITE}{path}">',
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap">',
            '<link rel="stylesheet" href="/assets/chrome.css">'] + ([BEACON.strip()] if BEACON else []))
        for name, body in (("site-head", links), ("site-header", header(active)), ("site-footer", foot)):
            s, n = re.subn(rf"<!-- {name} -->.*?<!-- /{name} -->",
                           lambda m, name=name, body=body: f"<!-- {name} -->\n{body}\n<!-- /{name} -->", s, count=1, flags=re.S)
            assert n == 1, (rel, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
        print("refreshed", rel)


# ---------------------------------------------------------------- questions
# One page per question people actually ask, answered in the first paragraph with
# today's numbers. Answer engines cite pages whose headings match the question.

import sys as _sys
_sys.path.insert(0, os.path.join(ROOT, "src"))
from hl_wallet import bar as _bar  # noqa: E402

# Set once the Worker answers at this host (worker/README.md); empty keeps it off the pages.
API_HOST = "https://api.evidencedeflator.com"
API_LINE = (f', or <code>GET {API_HOST}/api/wallet?a=0x…</code>' if API_HOST else "")

QUESTIONS = [
    ("hyperliquid-trader-skill-or-luck", "Is this Hyperliquid trader skilled or just lucky?"),
    ("how-many-months-of-backtest", "How many months of backtest or track record are enough?"),
    ("why-leaderboard-winner-is-not-evidence", "Why isn't the #1 trader on a leaderboard evidence of skill?"),
]


def _months(t, sharpe):
    m = (t / sharpe) ** 2 * 12
    return f"{m:.0f} months" if m < 36 else f"{m / 12:.1f} years"


RECORD_ALT = {"en": "/record/", "zh-Hans": "/zh-hans/record/", "zh-Hant": "/zh-hant/record/"}


def record_data():
    """Everything /record/ shows, for both languages: the calls with a test and the date each was written
    down, the frozen lists with their hashes, and the on-chain readings. A reading date that has passed
    with no result filled in shows as overdue, which is a mark against us too."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        hc = json.load(f)["cohort"]
    with open(os.path.join(DOCS, "data", "papertrade", "frozen-2026-10-16.json"), encoding="utf-8") as f:
        pt = json.load(f)
    calls = [  # result stays None until a reading is published; then it is the outcome, whatever it is
        {"id": "papertrade", "audit": "/audits/010-papertrade-leaderboard.html", "prereg": "/data/papertrade/PREREG.md",
         "written": "2026-10-16", "written_commit": "2cd7deb", "frozen": pt["frozen_at"], "readings": ["2026-10-23", "2026-10-30"], "result": None},
        {"id": "hl_cohort", "audit": "/wallet/#forward", "prereg": "/record/#hl-cohort",
         "written": "2026-10-18", "written_commit": None, "frozen": hc["frozen_at"], "readings": ["2026-12-09"], "result": None},
    ]
    for c in calls:
        due = [d for d in c["readings"] if d <= today]
        c["status"] = "done" if c["result"] else ("overdue" if due else "pending")
    frozen = [
        {"what": "hl", "file": "/data/hl/" + hc["file"], "sha256": hc["sha256"], "at": hc["frozen_at"], "n": hc["members"]},
        {"what": "pt_board", "file": "/data/papertrade/" + pt["board_file"], "sha256": pt["board_csv_sha256"], "at": pt["frozen_at"], "n": pt["board_rows"]},
    ]
    onchain = [  # docs/data/erc8004/README.md
        {"date": "2026-10-17", "chain": "Base", "agent": "DegenAI · agentId 19136", "t": "1.33", "tag": "single",
         "tx": "0xeaedbc13bf17a7cbd30c7509825217691aa2669d44a8637fb2379f9bb401a385", "url": "https://basescan.org/tx/"},
        {"date": "2026-10-17", "chain": "Ethereum", "agent": "DegenAI · agentId 23121", "t": "1.33", "tag": "single",
         "tx": "0x716b5e99cce13a5b7d0190f9b6c02923aafd02168e77016def8f266647f7d8f7", "url": "https://etherscan.io/tx/"},
    ]
    return {"today": today, "calls": calls, "frozen": frozen, "onchain": onchain, "cohort": hc}


def build_record():
    d = record_data()
    st = {"pending": ("tag-grey", "Pending"), "overdue": ("tag-red", "Overdue: reading not yet published"), "done": ("tag-green", "Read")}
    pt, hl = d["calls"]
    def status(c):
        cls, txt = st[c["status"]]
        return f'<span class="tag {cls}">{txt}</span>'
    frozen = "".join(f'<tr><td>{"Hyperliquid forward cohort" if f["what"] == "hl" else "Papertrade all-time board"}</td><td class="r">{f["n"]:,}</td>'
                     f'<td class="mono">{f["at"].replace("T", " ").replace("Z", " UTC")}</td><td class="mono" style="white-space:normal;overflow-wrap:anywhere"><a href="{f["file"]}">{html.escape(f["file"].rsplit("/", 1)[1])}</a><br>sha256 {f["sha256"]}</td></tr>' for f in d["frozen"])
    chain = "".join(f'<tr><td class="mono">{o["date"]}</td><td>{o["chain"]}</td><td>{o["agent"]}</td><td class="r">{o["t"]}</td><td>{o["tag"]}</td>'
                    f'<td class="mono" style="white-space:normal;overflow-wrap:anywhere"><a href="{o["url"]}{o["tx"]}" rel="noopener">{o["tx"][:10]}…{o["tx"][-6:]}</a></td></tr>' for o in d["onchain"])
    page = head("Our record · Evidence Deflator", "Every forward call Evidence Deflator has made, written down with a date and the result that would show it wrong, before any outcome existed.",
                "/record/", alt=RECORD_ALT) + header("", RECORD_ALT) + f"""
<main class="container article narrow prose">
<div class="eyebrow"><span class="dot"></span>Our record · built {d['today']}</div>
<h1 style="margin-top:16px">We are scored too</h1>
<p class="lede" style="margin-top:14px">A check that rates other people’s records should keep one of its own. Each call below was written down with a date, and with the result that would show we were wrong, before any outcome existed. Every reading is published here, whatever it shows. A reading date that passes without a result shows as overdue.</p>

<h2 id="calls">Calls with a test</h2>

<h3 id="papertrade">1 · Papertrade’s leaderboard does not predict what comes next {status(pt)}</h3>
<p><b>Written</b> 2026-10-16, before the freeze (commit <code>{pt['written_commit']}</code>, then the frozen file). <b>Frozen</b> {pt['frozen'].replace('T', ' ').replace('Z', ' UTC')}. <b>Readings</b> 2026-10-23 (interim) and 2026-10-30 (primary).</p>
<p><b>What would count against us:</b> at the 2026-10-30 reading, the 24-hour PnL top 100 beats a seeded random control by more than 15 percentage points in the share of wallets that made money after the freeze, with a median above zero. Then the board carries information, and we will say so. Fewer than 30 wallets trading after the freeze reads as “not enough data”, not as a result. Full text: <a href="{pt['prereg']}">PREREG.md</a> · <a href="{pt['audit']}">audit 010</a>.</p>

<h3 id="hl-cohort">2 · Hyperliquid’s top boards hold little forward skill {status(hl)}</h3>
<p><b>Frozen</b> {hl['frozen'].replace('T', ' ').replace('Z', ' UTC')}: every address on that day’s all-time PnL and 30-day ROI top 100s, {d['cohort']['members']} wallets, scored only on what they do after the freeze. <b>Reading</b> 2026-12-09, the first day a wallet can have eight weeks of record after the freeze.</p>
<p><b>Written</b> 2026-10-18. The list and its rule were frozen on 2026-10-14, but the result that would count against us was not written down then; it is written here, four days later and before any wallet can be scored.</p>
<p><b>What would count against us:</b> of the cohort wallets with at least eight weeks of record after the freeze, more than 10% reach t ≥ 2 on that record at the 2026-12-09 reading. Luck alone gives about 2.3%; if most of them had a true Sharpe of 3, roughly one in five would (normal approximation; the small-sample correction makes it somewhat lower). More than 10% would mean these boards pick up more skill than we say, and we will say so. Reported alongside, with no pass mark: for wallets that were promising before the freeze (t ≥ 2) against the rest, the share with t above zero after it. Fewer than 30 wallets with eight weeks reads as “not enough data”, and the reading moves to 2027-01-06.</p>

<h2 id="frozen">Lists we froze</h2>
<p>Each file is in the repository with its full history, so a change after the freeze would show in git and break the hash.</p>
<div class="table-wrap"><table class="data"><thead><tr><th>List</th><th class="r">Entries</th><th>Frozen</th><th>File and sha256</th></tr></thead><tbody>{frozen}</tbody></table></div>

<h2 id="onchain">Readings we cannot edit</h2>
<p>Written to the ERC-8004 reputation registry from <code>0xF02cF39d6b91Ac62B1D21d0F1C39335118c1F9A1</code>, the project’s only feedback address. These are readings, not predictions: t on the agent’s record since it registered. <a href="/data/erc8004/README.md">How they are built</a>.</p>
<div class="table-wrap"><table class="data"><thead><tr><th>Date</th><th>Chain</th><th>Agent</th><th class="r">t</th><th>Field</th><th>Transaction</th></tr></thead><tbody>{chain}</tbody></table></div>

<h2 id="errors">Errors</h2>
<p>Every number on the site is recomputed by scripts in the repository, and every change to a published page is in its git history. If you think a number is wrong, <a href="{REPO}/issues/new?title=Wrong%20number%3A%20">open an issue</a> with the page and the number; corrections are made in public and listed here with the date and the commit. Corrections so far: none. This list is kept by hand; <a href="{REPO}/issues?q=is%3Aissue">every issue ever filed</a> is public, so you can check it against them.</p>
</main>
""" + footer()
    write("record/index.html", page)


def build_questions():
    with open(os.path.join(DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        hl = json.load(f)
    pnl, roi = hl["boards"]["pnl"], hl["boards"]["roi30"]
    n_acc, day = pnl["ranked_from"], hl["fetched"][:10]
    b_n = _bar(n_acc)
    top10 = pnl["rows"][:10]
    outside = sum("pnl_outside_record" in r["flags"] for r in top10)
    unscored10 = sum(r["t"] is None for r in top10)
    others = "".join(f'<li><a href="/q/{slug}/">{html.escape(q)}</a></li>' for slug, q in QUESTIONS)
    form = ('<form class="wcheck" action="/wallet/" method="get" autocomplete="off" style="margin:22px 0">'
            '<input name="a" placeholder="0x… Hyperliquid address" spellcheck="false" aria-label="Hyperliquid address">'
            '<button class="btn btn-primary" type="submit">Check <span class="arr">→</span></button></form>')

    bodies = {
        "hyperliquid-trader-skill-or-luck": (
            f"Paste the address below. On {day}, of the {pnl['scored']} wallets in Hyperliquid’s all-time PnL top 100 with enough history to score, "
            f"{pnl['n_t_ge_2']} would pass the usual test (t ≥ 2) if you had picked them blind, and {pnl['n_t_ge_bar']} pass the bar that applies when "
            f"you found them by sorting a board of {n_acc:,} accounts (t ≥ {b_n:.2f}). For the 30-day ROI top 100: {roi['n_t_ge_2']} and {roi['n_t_ge_bar']} of {roi['scored']}.",
            f"""{form}
<h2>What the check does</h2>
<p>It takes the wallet’s public portfolio history from Hyperliquid, turns it into weekly returns (change in cumulative PnL over the account value at the start of the week, so deposits and withdrawals are not returns), and asks how strong that record is: t = annualised Sharpe × √years, adjusted for short and irregular records.</p>
<h2>Which bar applies</h2>
<p>If someone sent you this one wallet and you had no other candidates, t ≥ 2 is the usual bar. If you found it on a leaderboard, it is the best of {n_acc:,}, and someone is always on a streak in a crowd that size. The bar for the best of {n_acc:,} is t ≥ {b_n:.2f} (Bonferroni). Most people find wallets on leaderboards. That bar counts every account as independent; accounts that trade alike are fewer independent bets, which would lower it to about 2.6 by our <a href="https://github.com/Beltran12138/evidence-deflator#a-track-record-with-no-model-behind-it">rough estimate</a> (an order of magnitude, not a measurement).</p>
<h2>What the verdict cannot see</h2>
<p>A strategy that sells insurance can show no losing week for a long time. The page flags a record with no losing week, one where a single week made most of the gains, and one where most of the PnL was booked while the account held under $1,000 and cannot be turned into a return. In the PnL top 10 on {day}, {outside} carry that last flag and {unscored10} have too little measurable history to score at all.</p>
<p>From an agent: the MCP tool <code>hyperliquid_wallet</code>{API_LINE}, or the skill in the <a href="{REPO}">repository</a>.</p>"""),
        "how-many-months-of-backtest": (
            f"At a true annualised Sharpe of 1, about 48 months to reach t = 2 for a single result; at Sharpe 2, 12 months. "
            f"If the result is the best of many tries, it needs more: the best of 100 needs t ≥ {_bar(100):.2f}, which at Sharpe 1 is {_months(_bar(100), 1)}.",
            f"""<h2>The formula</h2>
<div class="eq">t = Sharpe × √years        months needed = (t / Sharpe)² × 12</div>
<p>This is Lo (2002) under i.i.d. returns, so it is a floor: autocorrelated returns need longer.</p>
<h2>The table</h2>
<div class="table-wrap"><table class="lb-table"><thead><tr><th>True Sharpe</th><th class="r">One result (t ≥ 2)</th><th class="r">Best of 100 (t ≥ {_bar(100):.2f})</th><th class="r">Best of {n_acc:,} (t ≥ {b_n:.2f})</th></tr></thead><tbody>
{"".join(f'<tr><td>{sh}</td><td class="r">{_months(2, sh)}</td><td class="r">{_months(_bar(100), sh)}</td><td class="r">{_months(b_n, sh)}</td></tr>' for sh in (0.5, 1, 2, 3))}
</tbody></table></div>
<h2>Which months count</h2>
<p>Only months the result was not fitted on. For a backtest run with a language model, months before the model’s training cutoff cannot be ruled out as seen; only months after it are clean. <a href="/check/">Check a backtest</a> splits the window for you. For a trader you are about to copy, only the record after the day you picked them tests the pick.</p>
<p>Count every variant tried, including ones that were dropped. An agent can try fifty in a minute; the plugin in the <a href="{REPO}">repository</a> counts them as it goes.</p>"""),
        "why-leaderboard-winner-is-not-evidence": (
            f"Because the top of a board is the maximum of many draws. Among {n_acc:,} accounts, someone is on a streak by chance alone; the best of {n_acc:,} has to clear t ≥ {b_n:.2f}, not 2. "
            f"On {day}, {pnl['n_t_ge_bar']} of the {pnl['scored']} scoreable wallets in Hyperliquid’s all-time PnL top 100 did.",
            f"""<h2>The bar rises with the number you picked from</h2>
<div class="table-wrap"><table class="lb-table"><thead><tr><th>Picked from</th><th class="r">t needed</th></tr></thead><tbody>
{"".join(f'<tr><td>{n:,}</td><td class="r">{_bar(n):.2f}</td></tr>' for n in (1, 10, 100, 1000, n_acc))}
</tbody></table></div>
<p>The bar keeps the chance that a no-skill account clears it, anywhere on the board, at the 2.3% a single test allows (Bonferroni on α = 1 − Φ(2)). Counting every account as independent overstates the charge when accounts copy each other; the true number of independent bets is unknown, so the table is an upper bound on the bar and the honest range sits below it.</p>
<h2>Profit ranks are not return ranks</h2>
<p>A PnL board ranks dollars. A large account with an ordinary return outranks a small one with an exceptional return, and PnL booked into a near-empty account cannot be turned into a return at all. In the all-time PnL top 10 on {day}, {outside} wallets had most of their PnL booked while the account held under $1,000.</p>
<h2>What would count</h2>
<p>A record found after the fact has already been picked for looking good. The clean test is forward: freeze the list, then watch. We froze 200 wallets from the top of the board on 2026-10-14 and publish how each does from then on, on the <a href="/wallet/">wallet page</a>.</p>"""),
    }
    for slug, q in QUESTIONS:
        lead, rest = bodies[slug]
        faq = ld({"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q,
                  "acceptedAnswer": {"@type": "Answer", "text": lead}}]})
        alt = {"en": f"/q/{slug}/", "zh-Hans": f"/zh-hans/q/{slug}/", "zh-Hant": f"/zh-hant/q/{slug}/"}
        page = head(f"{q} · Evidence Deflator", lead[:300], f"/q/{slug}/", extra=faq, alt=alt) + header("", alt) + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>Question · data as of {day}</div>
<h1 style="margin-top:16px">{html.escape(q)}</h1>
<p class="lede" style="margin-top:14px">{lead}</p>
{rest}
<h2>Related questions</h2><ul>{others}</ul>
<p class="muted small">Numbers rebuild daily from <a href="/data/hl/latest.json">latest.json</a>. Method: <a href="/method/">Method</a>. Not investment advice.</p>
</article></div></main>
""" + footer()
        write(f"q/{slug}/index.html", page)


# ---------------------------------------------------------------- privacy, terms

LEGAL_UPDATED = "2026-10-17"


def build_legal():
    issues = REPO + "/issues"
    pages = {
        "privacy": ("Privacy", "What Evidence Deflator collects: no accounts, no cookies, no stored wallet addresses.", f"""
<p class="lede" style="margin-top:14px">No accounts, no cookies, no stored wallet addresses. Last updated {LEGAL_UPDATED}.</p>
<h2>The website (evidencedeflator.com)</h2>
<p>Static pages hosted on GitHub Pages behind Cloudflare. We count page views with Cloudflare Web Analytics, which sets no cookies and does not identify you. When you check a wallet on the site, your browser asks Hyperliquid’s public API for that wallet’s history directly; the address is not sent to us. After a verdict is shown, the page sends our API one tally that says only “a check was done” and the page language, so we can count daily checks. A click from a result to the sample memo, or to request one, adds the same kind of tally. If you visit a page with <code>?team=1</code>, your browser keeps a flag (in local storage, not a cookie) that marks its tallies as our own testing; it is meant for us, and <code>?team=0</code> removes it.</p>
<h2>The API and MCP server (api.evidencedeflator.com)</h2>
<p>When you or your AI assistant call the API or the MCP tool, the request carries a wallet address and, optionally, a number. Our server, a Cloudflare Worker, forwards the address to Hyperliquid’s public info API to fetch that wallet’s history, scores it, and returns the result. We do not store the address or the result, and we have not turned on request logging for the Worker. Each completed check adds one tally to a daily count (whether it came from the API or the MCP tool), without the address or anything about the caller. Cloudflare, which runs the Worker, processes requests (including your IP address) under its own privacy policy. Hyperliquid receives the address under its own terms.</p>
<p>A wallet address on a public blockchain is public data. Do not send anything else; the tool does not need it.</p>
<h2>The Telegram bot and the Chrome extension</h2>
<p>The Telegram bot receives the messages you send it through Telegram, which processes them under its own privacy policy. The Worker above reads the address in your message, checks it the same way, replies, and keeps nothing: not the message, not your chat or user ID. Each check adds one tally to the daily count.</p>
<p>The Chrome extension reads the address or trader ID in the URL of the page you are on and fetches that record directly from the exchange's public API (Hyperliquid, Binance or OKX). It sends nothing about the trader or you to us; it only downloads our daily board sizes. It has no analytics.</p>
<h2>The Python package, Claude Code plugin and skill</h2>
<p>They run on your machine. The plugin’s backtest counter keeps a small log of matching shell commands in your local plugin data folder; it is never sent anywhere. The package and plugin contact Hyperliquid (and our API, if you use the hosted MCP tool) only when you check a wallet.</p>
<h2>Changes and contact</h2>
<p>If this changes, this page and its date change with it, and the history is public in the <a href="{REPO}">repository</a>. Questions: <a href="{issues}">GitHub issues</a>.</p>"""),
        "terms": ("Terms", "Terms for using Evidence Deflator's website, API, MCP server and open-source code.", f"""
<p class="lede" style="margin-top:14px">Free to use, open source, no warranty, not investment advice. Last updated {LEGAL_UPDATED}.</p>
<h2>What this is</h2>
<p>Evidence Deflator computes statistical estimates from public data: how strong a trading record is once you allow for its length and for how it was picked. The estimates rest on stated assumptions (listed on the <a href="/method/">method page</a>) and can be wrong. A record that passes is not a recommendation, and a past record is not your future return after fees, latency and slippage.</p>
<h2>Not advice</h2>
<p>Nothing here is investment, financial, legal or tax advice, or an offer to buy or sell anything. Do not use it as the only basis for a decision.</p>
<h2>Use of the API and MCP server</h2>
<p>You may call the hosted API and MCP server for free. Do not use them to overload the service or Hyperliquid’s API. We may rate-limit, change or stop the hosted service at any time; the code stays available.</p>
<h2>Code and data</h2>
<p>The code is MIT-licensed; see the <a href="{REPO}">repository</a>. Wallet data comes from Hyperliquid’s public API and belongs to its sources.</p>
<h2>No warranty</h2>
<p>The website, API, MCP server and code are provided “as is”, without warranty of any kind, and to the extent the law allows we are not liable for any loss arising from their use.</p>
<h2>Contact</h2>
<p><a href="{issues}">GitHub issues</a>.</p>"""),
    }
    for slug, (title, desc, body) in pages.items():
        page = head(f"{title} · Evidence Deflator", desc, f"/{slug}/") + header("") + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>{title}</div>
<h1 style="margin-top:16px">{title}</h1>
{body}
</article></div></main>
""" + footer()
        write(f"{slug}/index.html", page)


# IndexNow (Bing, Yandex, Seznam, Naver...): the key is public by design; the
# file at /<key>.txt proves we own the host. tools/indexnow.py submits URLs.
INDEXNOW_KEY = "b756502a8abaf3fb7bf6e69716e37269"
NOT_IN_SITEMAP = {"404.html", "macau.html", "pitch.html"}  # error page and live decks


# llms.txt (llmstxt.org): a plain-text map for language models. No evidence yet that
# answer engines read it; it costs one file.
LLMS_TXT = f"""# Evidence Deflator

> Checks whether a trading record can be told apart from luck once you allow for how it was picked. Paste a Hyperliquid wallet and get a verdict; the best of a leaderboard of ~47,000 accounts has to clear t >= 4.90, not 2. Open source (MIT), no account, not investment advice.

## Use it

- [Check a Hyperliquid wallet]({SITE}/wallet/): browser tool, the address is not sent to us
- [JSON API]({API_HOST}/api/wallet?a=0x393d0b87ed38fc779fd9611144ae649ba6082109): `GET /api/wallet?a=<address>&picked_from=<N>`
- [Remote MCP server]({API_HOST}/mcp): streamable HTTP, one read-only tool `hyperliquid_wallet(address, picked_from)`
- [API, Python package and plugin install]({SITE}/api/)

## Questions

- [Is this Hyperliquid trader skilled or just lucky?]({SITE}/q/hyperliquid-trader-skill-or-luck/)
- [How many months of backtest or track record are enough?]({SITE}/q/how-many-months-of-backtest/)
- [Why isn't the #1 trader on a leaderboard evidence of skill?]({SITE}/q/why-leaderboard-winner-is-not-evidence/)

## Method and data

- [Method]({SITE}/method/): t = Sharpe x sqrt(years) with a small-sample correction; Bonferroni bar for the best of N
- [Daily Hyperliquid board data]({SITE}/data/hl/latest.json) (CC BY 4.0)
- [Frozen forward cohort, 2026-10-14]({SITE}/data/hl/cohort-2026-10-14.json): 200 wallets scored only on PnL after the freeze
- [Source code]({REPO})
"""


def build_crawl_files():
    """robots.txt, sitemap.xml and the IndexNow key file, from the pages on disk."""
    with open(os.path.join(DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        fresh = json.load(f)["fetched"][:10]
    urls = []
    for root, _, files in os.walk(DOCS):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), DOCS).replace(os.sep, "/")
            if not name.endswith(".html") or rel in NOT_IN_SITEMAP:
                continue
            urls.append("/" + (rel[: -len("index.html")] if name == "index.html" else rel))
    urls.sort(key=lambda u: (u.count("/"), u))
    daily = {"/", "/wallet/"}  # rebuilt from the daily Hyperliquid data
    body = "".join(f"  <url><loc>{SITE}{u}</loc>" + (f"<lastmod>{fresh}</lastmod>" if u in daily else "") + "</url>\n"
                   for u in urls)
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")
    # Everything is public and meant to be read and cited, by search and answer engines alike.
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    write(f"{INDEXNOW_KEY}.txt", INDEXNOW_KEY)
    write("llms.txt", LLMS_TXT)
    return urls


def main():
    with open(os.path.join(DOCS, "leaderboard", "2026-10.json"), encoding="utf-8") as f:
        lb = json.load(f)
    rows = build_audits()
    build_home(rows, lb)
    build_leaderboard(lb)
    build_method()
    build_api()
    build_wallet()
    build_polymarket()
    build_memo_sample()
    build_404()
    build_questions()
    build_legal()
    build_record()
    import site_zh
    site_zh.build(_sys.modules[__name__])
    inject_chrome()
    build_crawl_files()


if __name__ == "__main__":
    main()
