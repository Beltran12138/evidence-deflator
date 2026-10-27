"""PreToolUse hook: orders go through the agent gate, not straight to a broker's MCP tools.

Off unless the user sets the plugin option ``direct_order_pattern`` (a regular expression for order
tool names, matched case-insensitively against the tool part of ``mcp__<server>__<tool>``). With it
set, a matching tool call from any MCP server whose name does not contain ``gate_server`` (default
"gate") is refused, and the agent is told to use the gate's ``place_order``, which checks the owner's
signed limits and writes the ledger.

What it does not stop: an agent that calls the broker's HTTP API from a shell, or any process outside
Claude Code. The defence for those is keeping the broker key in the gate's process only
(docs/gate/MANDATE.md, "What it does not prove"). Standard library only; silent when it allows.
"""
import json
import os
import re
import sys


def decide(event, pattern, gate_server="gate"):
    """The refusal reason for this tool call, or None to let it through."""
    if not pattern:
        return None
    name = event.get("tool_name") or ""
    parts = name.split("__")
    if len(parts) < 3 or parts[0] != "mcp":
        return None
    server, tool = parts[1], "__".join(parts[2:])
    if gate_server and gate_server.lower() in server.lower():
        return None
    try:
        hit = re.search(pattern, tool, re.I)
    except re.error:
        return f"Evidence Deflator: direct_order_pattern {pattern!r} is not a valid regular expression; " \
               "refusing order-like tools until it is fixed."
    if not hit:
        return None
    return (f"Evidence Deflator: {name} would send an order straight to the broker. In this project orders go "
            f"through the agent gate: call the gate server's place_order tool instead (same symbol, side and "
            f"size). The gate checks the order against the limits the account owner signed and records it in "
            f"the ledger either way. If no gate server is connected, tell the user rather than retrying.")


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    reason = decide(event, os.environ.get("CLAUDE_PLUGIN_OPTION_DIRECT_ORDER_PATTERN", "").strip(),
                    os.environ.get("CLAUDE_PLUGIN_OPTION_GATE_SERVER", "").strip() or "gate")
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))


if __name__ == "__main__":
    main()
