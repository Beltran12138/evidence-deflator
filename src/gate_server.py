"""MCP server for the agent gate: give an AI agent this instead of direct broker access.

The agent gets five tools. ``place_order`` goes through the owner's rules and is logged either
way; there is no tool that edits rules or the ledger, so the agent cannot loosen its own limits.
Rules live in the config file the owner controls (see agent_gate.DEFAULTS), or in a mandate the
owner signed. ``propose_mandate`` lets the agent turn the owner's plain-language limits into a
draft with worked examples; only the owner's signature puts a draft in force.

    python src/gate_server.py --config gate.json

Claude Code, one session only (nothing written to your settings):

    claude --mcp-config gate-mcp.json --strict-mcp-config

with gate-mcp.json = {"mcpServers": {"gate": {"command": "python",
                      "args": ["src/gate_server.py", "--config", "gate.json"]}}}

This is a separate server from mcp_server.py on purpose: that one scores records and never
touches an account; this one sits in front of an account.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent_gate  # noqa: E402
import mandate_examples  # noqa: E402

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:  # pragma: no cover
    raise SystemExit("gate_server needs the mcp package: pip install mcp") from e

mcp = FastMCP("agent-gate")
_GATE: Optional[agent_gate.Gate] = None


def gate() -> agent_gate.Gate:
    global _GATE
    if _GATE is None:
        _GATE = agent_gate.Gate(agent_gate.load_config(os.environ.get("GATE_CONFIG")))
    return _GATE


@mcp.tool()
def place_order(symbol: str, side: str, usd: Optional[float] = None, qty: Optional[float] = None,
                reason: str = "") -> Dict[str, Any]:
    """Place a market order through the owner's gate. Give exactly one of usd (notional) or qty.

    The gate checks the owner's rules (single-order size, daily loss, allowed symbols, orders per
    day) and either passes the order to the account or refuses it. Either way the request is
    written to a tamper-evident ledger. A refusal is final for this order: do not split it into
    smaller orders to get under a limit, and tell the user what was refused and why.
    Put your reason for the trade in ``reason``; it is logged with the order.
    """
    e = gate().place(symbol, side, usd=usd, qty=qty, note=reason)
    return {"decision": e["decision"], "reasons": e["reasons"], "request": e["request"],
            "fill": e.get("fill"), "equity_after": e["equity_after"], "ledger_line": e["seq"]}


@mcp.tool()
def account() -> Dict[str, Any]:
    """Cash, positions and equity of the gated account, and the rules in force."""
    g = gate()
    if g.cfg.get("mandate") and not g.mandate:
        rules: Any = "none in force: the owner has not signed a mandate yet, so every order is refused"
    else:
        rules = g._rules()
    return {"account": g.broker.account(), "rules": rules, "broker": g.broker.name}


@mcp.tool()
def recent_log(n: int = 10) -> List[str]:
    """The last n ledger lines, allowed and refused, as one line each."""
    return [agent_gate._fmt(e) for e in gate().ledger.read()[-max(1, min(n, 200)):]]


@mcp.tool()
def propose_mandate(owner_words: str, allow: List[str], max_order_usd: float, max_daily_loss_usd: float,
                    max_position_usd: Optional[float] = None, max_orders_per_day: Optional[int] = None,
                    sides: Optional[List[str]] = None, days: float = 14.0,
                    issuer: Optional[str] = None) -> Dict[str, Any]:
    """Turn the owner's own words about limits into a draft mandate, plus worked examples to confirm.

    Use this when the owner describes, in plain language, what you may and may not trade. Put their
    exact words in ``owner_words`` and your reading of them in the other fields. Nothing changes:
    the draft has no force until the owner signs it with their own key. Show the owner every example
    (order, decision) and ask them to confirm each one; if any decision surprises them, your reading
    was wrong, so revise and propose again. Never present the draft as signed or in force.
    """
    scope: Dict[str, Any] = {"allow": [s.upper() for s in allow], "max_order_usd": max_order_usd,
                             "max_daily_loss_usd": max_daily_loss_usd}
    if max_position_usd is not None:
        scope["max_position_usd"] = max_position_usd
    if max_orders_per_day is not None:
        scope["max_orders_per_day"] = max_orders_per_day
    if sides:
        scope["sides"] = [s.lower() for s in sides]
    cases = mandate_examples.examples(scope)
    out: Dict[str, Any] = {"status": "draft, not in force until the owner signs", "owner_words": owner_words,
                           "scope": scope, "days": days, "examples": cases}
    cfg = gate().cfg
    if issuer and cfg.get("mandate") and cfg.get("gate_key"):
        venue = cfg["broker"] + ("-" + cfg.get("network", "testnet") if cfg["broker"] == "hyperliquid" else "")
        m = agent_gate.mandate_mod.draft(issuer, agent_gate.mandate_mod.address_of(cfg["gate_key"]), venue,
                                         cfg.get("account") or cfg["broker"], scope, days=days)
        agent_gate.mandate_mod.save(m, cfg["mandate"] + ".unsigned.json")
        out["text_to_sign"] = agent_gate.mandate_mod.message(m)
        out["sign_url"] = "https://evidencedeflator.com/gate/sign/#m=" + base64.urlsafe_b64encode(
            out["text_to_sign"].encode()).decode().rstrip("=")
        out["next"] = ("owner signs text_to_sign in their wallet (or at evidencedeflator.com/gate/sign), "
                       "then runs: agent-gate mandate attach --sig 0x…")
    pdir = os.path.join(cfg["state_dir"], "proposals")
    os.makedirs(pdir, exist_ok=True)
    with open(os.path.join(pdir, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + ".json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return out


@mcp.tool()
def scorecard() -> Dict[str, Any]:
    """This account's own record so far: weekly returns from the ledger, t, and how much longer it
    would need at this Sharpe. Under 8 weeks there is no verdict. Compared with doing nothing."""
    return gate().scorecard()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    a = ap.parse_args()
    if a.config:
        os.environ["GATE_CONFIG"] = os.path.abspath(a.config)
    mcp.run()


if __name__ == "__main__":
    main()
