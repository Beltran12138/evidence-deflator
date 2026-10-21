"""MCP server for the agent gate: give an AI agent this instead of direct broker access.

The agent gets four tools. ``place_order`` goes through the owner's rules and is logged either
way; there is no tool that edits rules or the ledger, so the agent cannot loosen its own limits.
Rules live in the config file the owner controls (see agent_gate.DEFAULTS).

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
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent_gate  # noqa: E402

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
    return {"account": g.broker.account(), "rules": g._rules(), "broker": g.broker.name}


@mcp.tool()
def recent_log(n: int = 10) -> List[str]:
    """The last n ledger lines, allowed and refused, as one line each."""
    return [agent_gate._fmt(e) for e in gate().ledger.read()[-max(1, min(n, 200)):]]


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
