"""One sentence in, a mandate scope out, with no language model.

For owners who do not use an AI agent and do not read code: they write their limits the way they
would say them ("只做苹果和 SPY，单笔不超过 500，一天最多亏 200，每只股票最多拿 2000，两周有效"),
and this parser turns the common phrasings into the gate's rule fields. Every field it fills cites
the words it came from; anything it could not read is reported, never guessed. The owner then sees
the worked examples (mandate_examples.py) and confirms them before signing.

It is deliberately small and deterministic: the same sentence always gives the same rules, and a
browser port (docs/assets/mandate_text.js) is tested against this file on the same sentences.

    python src/mandate_text.py "只做苹果和 SPY，单笔不超过 500 美元，一天最多亏 200"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

NAMES = {  # common Chinese names for US tickers and coins; tickers in capitals are read as they are
    "苹果": "AAPL", "特斯拉": "TSLA", "英伟达": "NVDA", "微软": "MSFT", "谷歌": "GOOGL", "亚马逊": "AMZN",
    "脸书": "META", "奈飞": "NFLX", "台积电": "TSM", "标普500": "SPY", "标普": "SPY", "纳指": "QQQ",
    "纳斯达克": "QQQ", "比特币": "BTC", "以太坊": "ETH", "以太币": "ETH",
}
NOT_TICKERS = {"AI", "USD", "OK", "I", "A", "MAX", "PER", "ETF", "AND", "OR", "NO", "THE", "FOR", "DAY"}
CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}

NUM = r"(\$?\s*\d(?:[\d,]*\d)?(?:\.\d+)?\s*[万千kK]?|[零一二两三四五六七八九十百千万]+)"
GAP = r"[^\d$零一二两三四五六七八九十百千万，,；;。]"  # filler between a keyword and its number, within one clause
EGAP = r"[^\d$，,；;。]"  # the same for English
CLAUSE = r"(?:[^，,；;。\n]|,(?=\d))+"  # a clause; a comma between digits (1,000) does not end it


def cn_number(s: str) -> Optional[float]:
    """Chinese numerals as people write amounts: 五百, 两千, 一万五, 三千五百, 二十."""
    total, section, digit = 0, 0, None
    for ch in s:
        if ch in CN_DIGITS:
            digit = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            if unit == 10000:
                total += (section + (digit or 0)) * 10000
                section, digit = 0, None
            else:
                section += (1 if digit is None else digit) * unit
                digit = None
        else:
            return None
    rest = digit or 0
    if digit is not None and len(s) >= 2 and s[-2] in CN_UNITS and s[-2] != "十":  # 一万五 = 15000, 三千五 = 3500
        rest = digit * CN_UNITS[s[-2]] // 10
    return float(total + section + rest)


def to_number(tok: str) -> Optional[float]:
    t = tok.replace("$", "").replace(",", "").replace(" ", "")
    if not t:
        return None
    if re.fullmatch(r"[零一二两三四五六七八九十百千万]+", t):
        return cn_number(t)
    mult = 1
    if t[-1] in "万":
        mult, t = 10000, t[:-1]
    elif t[-1] in "千kK":
        mult, t = 1000, t[:-1]
    try:
        return float(t) * mult
    except ValueError:
        return None


def _int(x: float) -> Any:
    return int(x) if float(x).is_integer() else round(x, 2)


PATTERNS: List[Tuple[str, str]] = [
    ("max_orders_per_day", r"(?:一天|每天|每日|单日|当天)" + GAP + r"{0,6}?" + NUM + r"\s*(?:笔|单|次)"),
    ("max_orders_per_day", r"(?i)" + NUM + r"\s*(?:orders?|trades?)\s*(?:a|per|each)\s*day"),
    ("max_daily_loss_usd", r"(?:一天|每天|每日|单日|日内|当天)" + GAP + r"{0,6}?亏(?:损|钱)?" + GAP + r"{0,6}?" + NUM),
    ("max_daily_loss_usd", r"日亏(?:损)?" + GAP + r"{0,6}?" + NUM),
    ("max_daily_loss_usd", r"(?i)(?:lose|loss(?:es)?)" + EGAP + r"{0,20}?" + NUM + r"\s*(?:a|per|each|in a)\s*day"),
    ("max_daily_loss_usd", r"(?i)daily loss" + EGAP + r"{0,15}?" + NUM),
    ("max_order_usd", r"(?:单笔|每笔|一笔|每单|单次|每次下单)" + GAP + r"{0,8}?" + NUM),
    ("max_order_usd", r"(?i)" + NUM + r"\s*(?:usd|dollars?)?\s*(?:per|each|a)\s*(?:order|trade)"),
    ("max_order_usd", r"(?i)(?:per|each|single|any one)\s*(?:order|trade)" + EGAP + r"{0,15}?" + NUM),
    ("max_position_usd", r"(?:每只|每个|单只|单个|每支|单支|每种|单一)(?:股票|标的|币|品种)?" + GAP + r"{0,8}?" + NUM),
    ("max_position_usd", r"(?:仓位|持仓)" + GAP + r"{0,6}?" + NUM),
    ("max_position_usd", r"(?i)(?:position|per (?:stock|symbol|ticker|coin))" + EGAP + r"{0,20}?" + NUM),
]
VALIDITY = [
    r"有效期?" + GAP + r"{0,3}?" + NUM + r"\s*(天|日|周|星期|个?月)",
    NUM + r"\s*(天|日|周|星期|个?月)\s*(?:内)?有效",
    r"(?i)(?:valid\s*)?for\s*" + NUM + r"\s*(days?|weeks?|months?)",
]
NO_SHORT = r"(?i)(不做空|不许做空|不能做空|别做空|不要做空|禁止做空|只做多|不卖空|no short(?:ing|s)?|long only)"
NEGATE = r"(不要|别|不许|不准|禁止|不碰|不做|除了|no |not |avoid )"


def parse(text: str, default_days: float = 14.0) -> Dict[str, Any]:
    """Rule fields read from the sentence, the words each came from, what is missing, what was not read."""
    found: Dict[str, Any] = {}
    cites: List[Dict[str, Any]] = []
    used: List[Tuple[int, int]] = []

    def take(field: str, value: Any, m: re.Match) -> None:
        if field in found:
            return
        found[field] = value
        cites.append({"field": field, "value": value, "words": m.group(0).strip()})
        used.append(m.span())

    for field, pat in PATTERNS:
        for m in re.finditer(pat, text):
            if any(a <= m.start() < b for a, b in used):
                continue
            v = to_number(m.group(1))
            if v is None or v <= 0:
                continue
            take(field, _int(v), m)
            break
    for pat in VALIDITY:
        m = re.search(pat, text)
        if m:
            n, unit = to_number(m.group(1)), m.group(2).lower()
            if n:
                days = n * (7 if unit[0] in "周星w" else 30 if ("月" in unit or unit.startswith("month")) else 1)
                take("days", _int(days), m)
                break
    m = re.search(NO_SHORT, text)
    if m:
        take("sides", ["buy"], m)

    symbols: List[str] = []
    denied: List[str] = []
    spots = [(m.start(), m.end(), NAMES[m.group(0)]) for m in re.finditer("|".join(sorted(NAMES, key=len, reverse=True)), text)]
    spots += [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"(?<![A-Za-z])[A-Z]{1,5}(?![A-Za-z])", text) if m.group(0) not in NOT_TICKERS]
    for a, b, sym in sorted(spots):
        before = text[max(0, a - 6):a]
        clause_start = max(before.rfind(c) for c in "，,；;。") + 1
        if re.search(NEGATE, before[clause_start:]):
            denied.append(sym)
        elif sym not in symbols:
            symbols.append(sym)
        used.append((a, b))
    if symbols:
        found["allow"] = symbols
        cites.append({"field": "allow", "value": symbols,
                      "words": "、".join(text[a:b] for a, b, s in sorted(spots) if s in symbols)})

    missing = []
    if "allow" not in found:
        missing.append("allow")
    for k in ("max_order_usd", "max_daily_loss_usd", "max_position_usd"):
        if k not in found:
            missing.append(k)
    notes = []
    if denied:
        notes.append("denied_symbols:" + ",".join(denied))
    if "days" not in found:
        found["days"] = _int(default_days)
        notes.append("default_days")

    unread = []
    for m in re.finditer(CLAUSE, text):
        a, b = m.span()
        if not any(x < b and y > a for x, y in used) and re.search(r"[\w一-鿿]", m.group(0)):
            unread.append(m.group(0).strip())
    scope = {k: v for k, v in found.items() if k != "days"}
    return {"scope": scope, "days": found["days"], "cites": cites, "missing": missing, "notes": notes,
            "unread": unread}


FIELD_ZH = {"allow": "标的名单", "max_order_usd": "单笔上限", "max_daily_loss_usd": "每日亏损上限",
            "max_position_usd": "单标的仓位上限", "max_orders_per_day": "每日笔数", "sides": "方向", "days": "有效期（天）"}
MISSING_ZH = {"allow": "没说能交易哪些标的：不设名单，等于什么都能买",
              "max_order_usd": "没说单笔上限", "max_daily_loss_usd": "没说一天最多亏多少",
              "max_position_usd": "没说每个标的最多拿多少：没有它，每日亏损上限挡不住仓位越堆越大（见压力测试）"}


def render(r: Dict[str, Any]) -> str:
    out = ["闸门这样理解你的话："]
    for c in r["cites"]:
        out.append(f"  {FIELD_ZH[c['field']]}: {c['value']}    ← 「{c['words']}」")
    if "default_days" in r["notes"]:
        out.append(f"  有效期（天）: {r['days']}    ← 你没说，先按 {r['days']} 天")
    for k in r["missing"]:
        out.append("  缺：" + MISSING_ZH[k])
    for n in r["notes"]:
        if n.startswith("denied_symbols:"):
            out.append("  注意：你说了不要碰 " + n.split(":")[1] + "；闸门只认白名单，请直接说出允许交易的标的")
    for u in r["unread"]:
        out.append(f"  没看懂：「{u}」")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Read a mandate scope from one sentence, no model involved.")
    ap.add_argument("text")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = parse(a.text)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else render(r))


if __name__ == "__main__":
    main()
