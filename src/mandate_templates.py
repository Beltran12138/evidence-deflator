"""Starting points for a mandate's limits, scaled to the account.

Each template is a shape (what kind of authority it grants) with numbers as fractions of the account
value the owner gives. The fractions are this project's candidates, picked to be easy to reason about;
they are not recommendations and no study stands behind them. Before signing, look at what they allow
with ``mandate examples`` (concrete orders, allowed or refused) and ``agent-gate-stress`` (what the
limits permit over real price history: a daily-loss limit does not cap a day's loss).

    python src/agent_gate.py mandate templates
    python src/agent_gate.py mandate draft --template trial --account-usd 10000 --issuer 0x… --config gate.json
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "trial": {
        "what": "A first week with a new agent: small orders, a tight position cap, few orders a day.",
        "days": 7,
        "fractions": {"max_order_usd": 0.01, "max_position_usd": 0.05, "max_daily_loss_usd": 0.01},
        "fixed": {"max_orders_per_day": 5},
    },
    "long-only": {
        "what": "The agent may buy and sell what it holds, never go short.",
        "days": 30,
        "fractions": {"max_order_usd": 0.02, "max_position_usd": 0.10, "max_daily_loss_usd": 0.02},
        "fixed": {"max_orders_per_day": 20, "sides": ["buy"]},
    },
    "wind-down": {
        "what": "Close out: no new risk at all. Only orders that shrink a position pass, in pieces no larger "
                "than the single-order limit.",
        "days": 7,
        "fractions": {"max_order_usd": 0.05},
        "fixed": {"max_orders_per_day": 0},
    },
}


def scope(name: str, account_usd: float, allow: Optional[List[str]] = None) -> Dict[str, Any]:
    """The template's scope for an account of ``account_usd``, dollar limits rounded to whole dollars."""
    if name not in TEMPLATES:
        raise ValueError(f"unknown template {name!r}; one of {', '.join(TEMPLATES)}")
    if not account_usd or account_usd <= 0:
        raise ValueError("account_usd must be positive")
    t = TEMPLATES[name]
    sc: Dict[str, Any] = {k: max(1, round(f * account_usd)) for k, f in t["fractions"].items()}
    sc.update(t["fixed"])
    if allow:
        sc["allow"] = sorted({s.upper() for s in allow})
    return sc


def render(account_usd: Optional[float] = None) -> str:
    lines = ["Templates (fractions of the account are candidates, not recommendations):", ""]
    for name, t in TEMPLATES.items():
        lines.append(f"{name}  ({t['days']} days)  {t['what']}")
        parts = [f"{k} {f:.0%}" for k, f in t["fractions"].items()]
        parts += [f"{k} {v}" for k, v in t["fixed"].items()]
        lines.append("    " + ", ".join(parts))
        if account_usd:
            lines.append("    at ${:,.0f}: {}".format(account_usd, scope(name, account_usd)))
    return "\n".join(lines)
