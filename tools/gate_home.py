"""The agent-gate product page: the English homepage (/) and its Chinese twin (/gate/), one structure.

Called from build_site.main(). The hero's receipt is read from the signed-mandate demo's real ledger
(docs/gate/demo-2026-10-21-mandate) every build, so the page cannot drift from the file it links to.
Visual direction from the 2026-10-21 council: paper, ink, mono ledger lines, one red for refusals,
one motion (the refusal stamp lands once). Applies to these two pages only for now.
"""
import json
import os

PAPER = """<style>
body{background:var(--bg)}
.gx h1{font-family:var(--serif);font-weight:560;font-size:clamp(34px,3.8vw,50px);line-height:1.1;letter-spacing:-.02em;margin:16px 0 0}
.gx h2{font-family:var(--serif);font-weight:560;font-size:clamp(28px,3.2vw,38px);line-height:1.15;letter-spacing:-.015em;margin:0}
.gx .lede{font-size:18.5px;line-height:1.6;color:var(--ink-2);max-width:560px;margin-top:20px}
.gx .note{font-size:13.5px;color:var(--muted);margin-top:14px;line-height:1.6}
.gx section{padding:72px 0;border-top:1px solid var(--rule)}
.gx .sec-k{font:500 11.5px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:14px}
.gx .sec-p{color:var(--ink-2);font-size:16.5px;line-height:1.65;max-width:680px;margin-top:14px}
.hero2{display:grid;grid-template-columns:1fr 1.05fr;gap:52px;align-items:center;padding:64px 0 76px}
.hero2 .ctas{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}
.hero2 .btn-primary{background:var(--ink);color:var(--bg)}
/* the receipt */
.rcpt{background:var(--surface);border:1px solid var(--rule);border-radius:4px;font:13px/1.65 var(--mono);color:var(--ink-2);box-shadow:0 1px 0 var(--rule-2),0 18px 40px -28px rgba(20,20,20,.35)}
.rcpt .hd{display:flex;justify-content:space-between;gap:12px;padding:14px 18px;border-bottom:1px dashed var(--rule);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.rcpt .mand{padding:14px 18px;border-bottom:1px dashed var(--rule)}
.rcpt .mand b{color:var(--ink);font-weight:600}
.rcpt .k{color:var(--faint)}
.rcpt .ln{display:grid;grid-template-columns:74px 1fr auto;gap:12px;padding:10px 18px;border-bottom:1px solid var(--rule-2);align-items:baseline}
.rcpt .ln .o{color:var(--ink);font-weight:600}
.rcpt .ln .why{grid-column:2/4;color:var(--muted);font-size:12px;margin-top:-4px}
.rcpt .ln .sig{grid-column:2/4;color:var(--faint);font-size:11.5px}
.rcpt .st{font-weight:700;letter-spacing:.06em;font-size:12px}
.rcpt .ok{color:var(--pos)}
.rcpt .no{color:var(--accent);border:2px solid var(--accent);padding:1px 7px;border-radius:3px;transform:rotate(-4deg);display:inline-block;animation:stamp .45s cubic-bezier(.2,1.6,.4,1) .7s both}
.rcpt .ft{padding:12px 18px;font-size:12px;color:var(--muted)}
.rcpt .ft b{color:var(--pos)}
.rcpt a{color:inherit}
@keyframes stamp{from{opacity:0;transform:rotate(-4deg) scale(2.2)}to{opacity:1;transform:rotate(-4deg) scale(1)}}
@media (prefers-reduced-motion:reduce){.rcpt .no{animation:none}}
/* steps */
.steps{margin-top:34px;border-top:1px solid var(--rule)}
.step{display:grid;grid-template-columns:56px 1fr 1.15fr;gap:28px;padding:26px 0;border-bottom:1px solid var(--rule);align-items:start}
.step .n{font:600 13px var(--mono);color:var(--accent);padding-top:4px}
.step b{display:block;font-size:19px;font-weight:600;color:var(--ink)}
.step p{color:var(--ink-2);font-size:15.5px;line-height:1.6;margin-top:6px}
.step pre,.gx pre{background:var(--sunk);border:1px solid var(--rule);border-radius:4px;padding:14px 16px;font:12.5px/1.6 var(--mono);color:var(--ink);overflow-x:auto;margin:0;white-space:pre}
/* real run */
.run{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:30px;align-items:start}
.term{background:#111;color:#E9E7E1;border-color:#111}
.term .dim{color:#8C8A84}.term .blk{color:#FF6B5E}.term .okc{color:#7FCB9E}
.said{border-left:3px solid var(--accent);padding:2px 0 2px 18px;color:var(--ink-2);font-size:15.5px;line-height:1.65}
.said p{margin:0 0 10px}
/* stress bars */
.bars{margin-top:34px;max-width:900px}
.bar{display:grid;grid-template-columns:260px 1fr;gap:20px;align-items:center;margin-bottom:16px}
.bar .lab{font-size:14.5px;color:var(--ink-2);text-align:right;line-height:1.4}
.bar .tr{position:relative;height:40px;display:flex;align-items:center}
.bar .f{height:100%;background:var(--rule)}
.bar.hot .f{background:var(--accent)}
.bar .v{font:600 20px var(--mono);margin-left:12px;color:var(--ink)}
.bar.hot .v{position:absolute;right:12px;color:var(--bg);margin:0}
/* contrast */
.vs{display:grid;grid-template-columns:1fr 1fr;margin-top:30px;border-top:1px solid var(--rule)}
.vs div{padding:24px 28px 8px 0}.vs div+div{padding-left:28px;border-left:1px solid var(--rule)}
.vs h3{font:500 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 14px}
.vs .ours h3{color:var(--accent)}
.vs p{font-size:16.5px;line-height:1.55;margin:0 0 12px;color:var(--ink-2)}.vs .ours p{color:var(--ink);font-weight:500}
/* lists and tables */
.works{margin-top:28px;border-top:1px solid var(--rule)}
.works .w{display:grid;grid-template-columns:220px 1fr;gap:24px;padding:14px 0;border-bottom:1px solid var(--rule-2);font-size:15px}
.works .w b{font-weight:600}.works .w span{color:var(--ink-2)}
.gx table{border-collapse:collapse;width:100%;font-size:14.5px;margin-top:24px}
.gx td,.gx th{border-bottom:1px solid var(--rule);padding:10px 12px 10px 0;text-align:left;vertical-align:top;line-height:1.55}
.gx th{font:500 11.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.gx td:first-child{width:30%;font-weight:500}
.founder{display:flex;justify-content:space-between;gap:30px;flex-wrap:wrap;align-items:baseline}
.founder p{color:var(--ink-2);font-size:15.5px;max-width:640px;margin:8px 0 0}
.hero2>*,.step>*,.run>*,.vs>*,.bar>*,.works .w>*{min-width:0}
.rcpt{overflow:hidden;overflow-wrap:anywhere}
@media (max-width:900px){.rcpt .ln{grid-template-columns:76px 1fr auto;gap:8px}.gx main,.gx{overflow-x:hidden}.hero2,.run,.vs{grid-template-columns:1fr}.vs div+div{padding-left:0;border-left:0}.step{grid-template-columns:40px 1fr}.step pre{grid-column:2}.bar{grid-template-columns:1fr}.bar .lab{text-align:left}.works .w{grid-template-columns:1fr;gap:4px}}
</style>
"""

T = {
 "en": dict(
  title="Agent gate · signed limits and an auditable ledger for AI trading agents · Evidence Deflator",
  desc="Your AI trading agent can trade only inside limits you signed with your own wallet. Every decision is signed into a ledger anyone can audit. Open source.",
  kicker="Agent gate · open source, MIT",
  h1="Your AI agent can trade. Only inside limits you signed.",
  lede="The agent sends orders to the gate, not the broker. The gate passes what fits your limits, refuses the rest, and signs every decision into a ledger that anyone can audit without trusting the gate.",
  cta1="Install in three minutes", cta2="Open the real ledger",
  status_note="Today: a simulated crypto account at live Hyperliquid prices, and Alpaca paper (US stocks), run live. Hyperliquid connector: signatures verified on testnet, no fill yet.",
  r_head="Real ledger · 2026-10-21 demo", r_open="open the file",
  r_mand="Mandate signed by", r_wallet="owner wallet", r_scope="BTC, ETH · ≤ $500/order · ≤ $200/day loss · to 2026-11-04",
  r_agent="Only key that can act", r_allow="ALLOWED", r_block="REFUSED",
  r_audit="audit: every allowed order re-checked against the signed limits →", r_ok="ok", r_test="test keys",
  how_k="How it works", how_h="Three steps, and the agent never holds a key that can trade.",
  s1="Sign the limits", s1p="Symbols, largest order, per-symbol position, daily loss, orders a day, expiry. You sign them with your own Ethereum wallet; the document names the one key allowed to act: the gate's.",
  s2="The agent asks the gate", s2p="Over MCP, or through an adapter in its own framework. Orders inside the limits go to the broker; the rest are refused, with the reason. An order that only reduces risk always passes.",
  s3="Audit from the ledger alone", s3p="Each line carries the hash of the one before and the gate's signature. audit re-checks every allowed order against the signed limits. A wholesale rewrite of the file, which a bare hash chain cannot catch, is caught.",
  run_k="A real agent", run_h="Told to buy $5,000 of ETH at once. Refused. It did not split the order.",
  run_p="2026-10-21: Claude connected to the gate over MCP, simulated account at live Hyperliquid prices. The instruction was “I'm bullish today, buy $5,000 of ETH now, and $300 of BTC.”",
  said_h="The agent's reply (excerpt, translated)",
  said=["BTC was bought. The ETH order was refused by the gate and did not fill.",
        "I did not split the $5,000 into ten orders of $500 to get round the limit. A refusal from the gate is final; splitting the order would defeat the risk rule you set.",
        "If $5,000 is the position you really want, raise max_order_usd in the gate's config. That is for you to change, not me."],
  st_k="What we found", st_h="A daily-loss limit alone does not cap a day.",
  st_p="We replayed the gate's own rules on 199 real days of Hyperliquid hourly returns (BTC, ETH), 30 days × 1,000 runs, starting at $10,000, $500 an order, 20 orders a day. The limit stops new risk, not losses on what is already held. So the default rules now include a per-symbol position limit.",
  b1="The daily-loss limit you set", b2="<b>Rule-abiding</b> agent using every limit: worst day, median", b3="With a $2,000 per-symbol position limit",
  st_src="Hourly closes; no liquidation, funding or fees.", st_link="Method and numbers →",
  vs_k="Why it has to be yours", vs_h="Guardrails sold with the agent stay with whoever sells the agent.",
  vs_a="Guardrails built into an agent product", vs_a1="The rules sit with whoever sells the agent", vs_a2="So does the record", vs_a3="Change agent or broker, and they are gone",
  vs_b="This gate", vs_b1="The limits are signed by you", vs_b2="Anyone can audit the ledger", vs_b3="Change agent or broker; they stay",
  w_k="Works with", w_h="Plugs in where your agent already sends orders.",
  works=[("Any MCP client", "Claude, Cursor and others get four tools: place_order, account, recent_log, scorecard. None can change limits or the ledger."),
         ("Hyperliquid", "The gate's key is your account's approved API wallet; you approve it from your main wallet. Signatures verified on testnet; no fill yet."),
         ("Alpaca paper", "US stocks on your paper account. Run live on 2026-10-21."),
         ("ai-hedge-fund", "A gated Broker wrapper; run against the project's own SimBroker."),
         ("lumibot", "A Strategy mixin; run inside a real lumibot backtest."),
         ("TradingAgents", "Turns its rating into one order you size; nothing trades on its own.")],
  in_k="Install", in_h="Three minutes, from a clone.",
  in_note="Sign a mandate with your wallet: <a href=\"/gate/sign/\">/gate/sign/</a>. Spec: <a href=\"https://github.com/Beltran12138/evidence-deflator/blob/main/docs/gate/MANDATE.md\">MANDATE.md</a>. Adapters: <a href=\"https://github.com/Beltran12138/evidence-deflator/blob/main/docs/gate/INTEGRATIONS.md\">INTEGRATIONS.md</a>.",
  tb_k="Status", tb_h="What it does today, and what it does not.", tb_th=("Part", "Status"),
  rows=[("Simulated crypto account", "Works. Fills at live Hyperliquid mid prices; the agent run above used it."),
        ("Alpaca paper (US stocks)", "Works with your own paper keys. Run live 2026-10-21: an in-limit AAPL order accepted, an over-limit SPY and an off-list TSLA refused."),
        ("Signed mandate + audit", "Works. Demo ledger and a forged rewrite caught: <a href=\"https://github.com/Beltran12138/evidence-deflator/tree/main/docs/gate/demo-2026-10-21-mandate\">demo</a>."),
        ("Hyperliquid", "Connected; signatures verified on testnet. No fill yet: testnet funds need an address that has deposited on mainnet."),
        ("Stress test before signing", "Works: python src/gate_stress.py --config gate.json."),
        ("Weekly scorecard", "Works; under 8 weeks of record it reports the length, not a verdict."),
        ("Investment advice", "None. The gate does not judge whether an order is a good idea; it enforces your limits and keeps the record.")],
  sc_k="The scorecard", sc_h="Is your agent's record skill, or luck?",
  sc_p="The ledger's equity is scored with the same ruler as our wallet check: weekly returns, a t-statistic, and a bar that rises with how many candidates were tried. Of Hyperliquid's all-time top 100 by profit, none clears it yet.",
  sc_link="The wallet check and leaderboard →",
  f_k="Who builds it", f_p="Bernard, the author of chapter 9 of <i>AI 智能投资手册</i> (an AI investing handbook). Built in the open, MIT licence; questions and design-partner requests through GitHub.",
  f_link="GitHub →", other=("/gate/", "中文", "zh-Hans")),
 "zh": dict(
  title="Agent gate · AI 交易 agent 的授权闸与可审计账本 · Evidence Deflator",
  desc="AI 交易 agent 只能在你用自己钱包签名的限额之内下单；每个决定都签名写进任何人都能复核的账本。开源。",
  kicker="Agent gate · 开源 · MIT",
  h1="AI agent 替你下单，<br>只在你签的限额之内。",
  lede="agent 不再直接调券商，而是调闸门。你的限额之内放行，越界拒绝；每一个决定都签名写进账本，任何人不用信任闸门，只凭账本就能复核。",
  cta1="三分钟装上", cta2="打开真实账本",
  status_note="现在可用：按 Hyperliquid 实时价格成交的加密模拟盘；Alpaca 美股模拟账户（已实测）。Hyperliquid 接入：测试网签名已验证，尚未成交。",
  r_head="真实账本 · 2026-10-21 演示", r_open="打开文件",
  r_mand="授权签发人", r_wallet="账户主人的钱包", r_scope="BTC, ETH · 单笔 ≤ $500 · 每日亏损 ≤ $200 · 至 2026-11-04",
  r_agent="唯一能执行的密钥", r_allow="放行", r_block="拦下",
  r_audit="audit：逐笔复核放行的单是否在签名限额之内 →", r_ok="通过", r_test="测试钥匙",
  how_k="怎么工作", how_h="三步。agent 手里始终没有能下单的钥匙。",
  s1="签下限额", s1p="能买哪些标的、单笔多大、单标的仓位多大、一天最多亏多少、一天几笔、到哪天为止。你用自己的以太坊钱包签名；文件里写明唯一能执行它的密钥：闸门的那把。",
  s2="agent 来问闸门", s2p="通过 MCP，或者通过它所在框架里的适配器。限额之内的单交给券商；越界的拒绝，并写明原因。只减少风险的单永远放行。",
  s3="只凭账本就能审计", s3p="每一行带着上一行的哈希和闸门的签名。audit 逐笔复核放行的单是否在签名限额之内。整份重写账本的伪造，单靠哈希链查不出，现在能查出来。",
  run_k="真实运行", run_h="让它一口气买 5,000 美元 ETH。被拦下。它没有拆单。",
  run_p="2026-10-21，Claude 通过 MCP 连上闸门（模拟盘，Hyperliquid 实时价格）。指令是「今天很看好，马上买 5,000 美元 ETH，再买 300 美元 BTC」。",
  said_h="agent 的回复（节选，原文）",
  said=["结果是：BTC 买入成交了，ETH 那笔被 gate 拦了，没有成交。",
        "我没有把 $5,000 拆成十笔 $500 去绕开限额。gate 拒绝一笔订单就是最终结果，拆单绕过等于废掉你自己设的风控规则。",
        "如果 $5,000 才是你真正想要的仓位，就去 gate 配置里把 max_order_usd 调高。这得你自己改，我不应该替你改。"],
  st_k="我们发现的", st_h="只设「每日亏损上限」，挡不住一天的亏损。",
  st_p="我们用 Hyperliquid 199 天真实小时收益（BTC、ETH）回放闸门自己的规则：30 天 × 1,000 次，起始 $10,000，单笔 $500，每天 20 笔。这个上限只拦新开的仓，拦不住手里仓位继续亏。所以默认规则已加上单标的仓位上限。",
  b1="你设的每日亏损上限", b2="<b>守规矩</b>但把额度用满的 agent：最坏一天（中位数）", b3="加上单标的仓位上限 $2,000 后",
  st_src="小时收盘价；未计强平、资金费、手续费。", st_link="方法与数据 →",
  vs_k="为什么必须在你手里", vs_h="跟 agent 一起卖的护栏，留在卖 agent 的人手里。",
  vs_a="agent 产品自带的护栏", vs_a1="规则在卖 agent 的人手里", vs_a2="账本也在他手里", vs_a3="换个 agent、换个券商，就没了",
  vs_b="这道闸", vs_b1="限额由你签名", vs_b2="账本任何人都能复核", vs_b3="换 agent、换券商，都还在",
  w_k="能接什么", w_h="接在你的 agent 本来就下单的地方。",
  works=[("任何 MCP 客户端", "Claude、Cursor 等拿到四个工具：place_order、account、recent_log、scorecard，没有一个能改限额或账本。"),
         ("Hyperliquid", "闸门的密钥就是你账户批准的 API 钱包，由你的主钱包批准。测试网签名已验证，尚未成交。"),
         ("Alpaca 模拟账户", "美股，用你自己的模拟账户。2026-10-21 已实测。"),
         ("ai-hedge-fund", "包一层券商接口；已对它自己的 SimBroker 实跑。"),
         ("lumibot", "一个 Strategy mixin；已在真实 lumibot 回测里跑过。"),
         ("TradingAgents", "把它的评级转成一笔由你定金额的单；不定金额就不交易。")],
  in_k="安装", in_h="三分钟，从克隆仓库开始。",
  in_note="用你的钱包签授权：<a href=\"/gate/sign/\">/gate/sign/</a>。规格：<a href=\"https://github.com/Beltran12138/evidence-deflator/blob/main/docs/gate/MANDATE.md\">MANDATE.md</a>。适配器：<a href=\"https://github.com/Beltran12138/evidence-deflator/blob/main/docs/gate/INTEGRATIONS.md\">INTEGRATIONS.md</a>。",
  tb_k="现状", tb_h="现在能做什么、不能做什么。", tb_th=("项", "状态"),
  rows=[("加密模拟盘", "可用。按 Hyperliquid 实时中间价成交；上面的真实运行就是它。"),
        ("Alpaca 模拟交易（美股）", "可用，需要你自己的模拟账户密钥。2026-10-21 实测：规则内的 AAPL 单提交成功，超限的 SPY 和白名单外的 TSLA 被拦，见 <a href=\"demo-2026-10-21-alpaca/ledger.jsonl\">账本</a>。"),
        ("签名授权 + audit", "可用。演示账本，以及一次被查出的整份重写伪造：<a href=\"https://github.com/Beltran12138/evidence-deflator/tree/main/docs/gate/demo-2026-10-21-mandate\">演示</a>。"),
        ("Hyperliquid", "已接入，测试网签名已验证。尚未成交：测试网领水需要在主网入过金的地址。"),
        ("签名前压力测试", "可用：python src/gate_stress.py --config gate.json。"),
        ("每周成绩单", "可用；记录不满 8 周时只给运行时长，不给结论。"),
        ("投资建议", "不做。闸门不判断一笔单好不好，只执行你的限额、记下发生了什么。")],
  sc_k="成绩单", sc_h="你的 agent 的记录，是本事还是运气？",
  sc_p="账本里的权益用和钱包检验同一把尺子打分：周收益、t 值，以及随试验次数抬高的门槛。Hyperliquid 历史盈利榜前 100 名，目前没有一个过线。",
  sc_link="钱包检验与排行 →",
  f_k="谁在做", f_p="伯纳德，《AI 智能投资手册》第九章作者。公开开发，MIT 许可；问题与设计合作方申请请走 GitHub。",
  f_link="GitHub →", other=("/", "English", "en")),
}


def short(h, n=6):
    return h[:n] + "…" + h[-4:] if h.startswith("0x") else h[:n + 4] + "…"


def receipt(t, rows, mand, base):
    m = mand["mandate"]
    lines = []
    for r in rows:
        if r.get("kind") != "order":
            continue
        q = r["request"]
        st = f'<span class="st ok">{t["r_allow"]}</span>' if r["decision"] == "allow" else f'<span class="st no">{t["r_block"]}</span>'
        side = "BUY" if q["side"] == "buy" else "SELL"
        why = f'<span class="why">{r["reasons"][0]}</span>' if r["decision"] != "allow" and r.get("reasons") else ""
        lines.append(f'<div class="ln"><span class="k">{r["ts"][11:19]}</span><span class="o">{side} {q["symbol"]} ${q["usd"]:,.0f}</span>{st}{why}'
                     f'<span class="sig">#{r["seq"]} · sha256 {r["hash"][:10]}… · sig {r.get("gate_sig", "")[:10]}…</span></div>')
    return (f'<div class="rcpt" aria-label="ledger excerpt">'
            f'<div class="hd"><span>{t["r_head"]}</span><a href="{base}ledger.jsonl">{t["r_open"]} ↗</a></div>'
            f'<div class="mand"><span class="k">{t["r_mand"]}</span> <b>{short(m["issuer"])}</b> <span class="k">· {t["r_wallet"]} ({t["r_test"]})</span><br>'
            f'{t["r_scope"]}<br><span class="k">{t["r_agent"]}</span> {short(m["agent"])}</div>'
            + "".join(lines) +
            f'<div class="ft">$ agent-gate audit · {t["r_audit"]} <b>{t["r_ok"]}</b></div></div>')


def page(B, lang, stress):
    t = T[lang]
    with open(os.path.join(B.DOCS, "gate", "demo-2026-10-21-mandate", "mandate.json"), encoding="utf-8") as f:
        mand = json.load(f)
    with open(os.path.join(B.DOCS, "gate", "demo-2026-10-21-mandate", "ledger.jsonl"), encoding="utf-8") as f:
        rows = [json.loads(x) for x in f if x.strip()]
    base = "/gate/demo-2026-10-21-mandate/"
    path = "/" if lang == "en" else "/gate/"
    alt = {"en": "/", "zh-Hans": "/gate/"}
    v0, cap = stress["as_given"]["max_out"]["worst_day_loss_p50"], stress["with_position_cap"]["max_out"]["worst_day_loss_p50"]
    lim = stress["rules"]["max_daily_loss_usd"]
    w = lambda x: f"{max(1.5, 100 * x / v0):.1f}%"
    said = "".join(f"<p>{s}</p>" for s in t["said"])
    works = "".join(f'<div class="w"><b>{a}</b><span>{b}</span></div>' for a, b in t["works"])
    trs = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in t["rows"])
    term = ('<pre class="term"><span class="dim">$ python src/agent_gate.py log --config gate.json</span>\n'
            '#0  09:27:54Z  BUY ETH  $5,000.00  <span class="blk">BLOCKED</span>\n'
            '    <span class="dim">order is $5,000.00, above the $500 single-order limit</span>\n'
            '#1  09:27:56Z  BUY BTC  $  300.00  <span class="okc">ALLOWED</span>\n'
            '    <span class="dim">0.003593 BTC @ 83,493.50</span>\n\n'
            '<span class="dim">$ python src/agent_gate.py verify --config gate.json</span>\n'
            '{"ok": true, "lines": 2, "head": "a3912dc8d6c2…"}</pre>')
    install = ('<pre>git clone https://github.com/Beltran12138/evidence-deflator && cd evidence-deflator\n'
               'pip install mcp eth-account\n'
               'python src/agent_gate.py demo                 # a scripted agent: allowed, refused, a tampered ledger caught\n'
               'python src/agent_gate.py init gate.json       # default limits, then edit\n'
               'python src/gate_stress.py --config gate.json  # what these limits allow, on real returns\n'
               'python src/gate_server.py --config gate.json  # the gate as an MCP server for your agent</pre>')
    snip1 = ('<pre>agent-gate keygen .gate/gate.key\n'
             'agent-gate mandate draft --config gate.json \\\n    --issuer 0xYourWallet --days 14\n'
             '# sign the printed text in your wallet\nagent-gate mandate attach --sig 0x…</pre>')
    snip2 = ('<pre>place_order("ETH", "buy", usd=5000)\n'
             '→ {"decision": "block",\n   "reasons": ["order is $5,000.00, above\n               the $500 single-order limit"]}</pre>')
    snip3 = ('<pre>agent-gate audit --config gate.json\n'
             '→ {"ok": true, "mandates": 1,\n   "orders_allowed": 2, "orders_rechecked": 2,\n   "problems": []}</pre>')
    body = f"""
<main class="gx"><div class="container">
<div class="hero2">
 <div>
  <div class="eyebrow"><span class="dot"></span>{t['kicker']}</div>
  <h1>{t['h1']}</h1>
  <p class="lede">{t['lede']}</p>
  <div class="ctas"><a class="btn btn-primary" href="#install">{t['cta1']} <span class="arr">→</span></a><a class="btn btn-secondary" href="{base}ledger.jsonl">{t['cta2']}</a></div>
  <p class="note">{t['status_note']}</p>
 </div>
 {receipt(t, rows, mand, base)}
</div>

<section id="how"><div class="sec-k">{t['how_k']}</div><h2>{t['how_h']}</h2>
 <div class="steps">
  <div class="step"><span class="n">01</span><div><b>{t['s1']}</b><p>{t['s1p']}</p></div>{snip1}</div>
  <div class="step"><span class="n">02</span><div><b>{t['s2']}</b><p>{t['s2p']}</p></div>{snip2}</div>
  <div class="step"><span class="n">03</span><div><b>{t['s3']}</b><p>{t['s3p']}</p></div>{snip3}</div>
 </div>
</section>

<section id="run"><div class="sec-k">{t['run_k']}</div><h2>{t['run_h']}</h2><p class="sec-p">{t['run_p']}</p>
 <div class="run">{term}<div class="said"><p><b>{t['said_h']}</b></p>{said}<p class="note"><a href="/gate/demo-2026-10-21/ledger.jsonl">ledger.jsonl</a> · <a href="/gate/demo-2026-10-21/agent-reply.md">agent-reply.md</a></p></div></div>
</section>

<section id="found"><div class="sec-k">{t['st_k']}</div><h2>{t['st_h']}</h2><p class="sec-p">{t['st_p']}</p>
 <div class="bars">
  <div class="bar"><div class="lab">{t['b1']}</div><div class="tr"><div class="f" style="width:{w(lim)}"></div><span class="v">${lim:,.0f}</span></div></div>
  <div class="bar hot"><div class="lab">{t['b2']}</div><div class="tr"><div class="f" style="width:100%"></div><span class="v">${v0:,.0f}</span></div></div>
  <div class="bar"><div class="lab">{t['b3']}</div><div class="tr"><div class="f" style="width:{w(cap)}"></div><span class="v">${cap:,.0f}</span></div></div>
 </div>
 <p class="note">{t['st_src']} <a href="https://github.com/Beltran12138/evidence-deflator/blob/main/docs/gate/MANDATE.md#stress-test-what-the-limits-allow-before-you-sign-them">{t['st_link']}</a></p>
</section>

<section id="yours"><div class="sec-k">{t['vs_k']}</div><h2>{t['vs_h']}</h2>
 <div class="vs"><div><h3>{t['vs_a']}</h3><p>{t['vs_a1']}</p><p>{t['vs_a2']}</p><p>{t['vs_a3']}</p></div>
 <div class="ours"><h3>{t['vs_b']}</h3><p>{t['vs_b1']}</p><p>{t['vs_b2']}</p><p>{t['vs_b3']}</p></div></div>
</section>

<section id="works"><div class="sec-k">{t['w_k']}</div><h2>{t['w_h']}</h2><div class="works">{works}</div></section>

<section id="install"><div class="sec-k">{t['in_k']}</div><h2>{t['in_h']}</h2><div style="margin-top:24px">{install}</div><p class="note">{t['in_note']}</p></section>

<section id="status"><div class="sec-k">{t['tb_k']}</div><h2>{t['tb_h']}</h2>
 <table><tr><th>{t['tb_th'][0]}</th><th>{t['tb_th'][1]}</th></tr>{trs}</table>
</section>

<section id="scorecard"><div class="sec-k">{t['sc_k']}</div><h2>{t['sc_h']}</h2><p class="sec-p">{t['sc_p']}</p><p class="note"><a href="/evidence/">{t['sc_link']}</a></p></section>

<section id="who"><div class="founder"><div><div class="sec-k">{t['f_k']}</div><p>{t['f_p']}</p></div><a class="btn btn-secondary" href="{B.REPO}">{t['f_link']}</a></div></section>
</div></main>
"""
    lang_attr = "en" if lang == "en" else "zh-Hans"
    return (B.head(t["title"], t["desc"], path, extra=PAPER, lang=lang_attr, alt=alt)
            + B.header("gate", alt, other=t["other"]) + body + B.footer())


def build(B):
    with open(os.path.join(B.DOCS, "data", "gate-stress-2026-10-21.json"), encoding="utf-8") as f:
        stress = json.load(f)
    B.write("index.html", page(B, "en", stress))
    B.write("gate/index.html", page(B, "zh", stress))
