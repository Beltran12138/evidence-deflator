"""The plugin's PreToolUse hook that sends orders through the gate instead of a broker's MCP tools."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(__file__)
SCRIPT = os.path.join(HERE, "..", "plugins", "evidence-deflator", "scripts", "gate_only_orders.py")
sys.path.insert(0, os.path.dirname(SCRIPT))

import gate_only_orders as h  # noqa: E402

PATTERN = r"(place|submit|create|replace)_?\w*order"


def ev(name):
    return {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": {}}


def test_off_by_default():
    assert h.decide(ev("mcp__alpaca__place_stock_order"), "") is None


def test_a_broker_order_tool_is_refused_and_pointed_at_the_gate():
    r = h.decide(ev("mcp__alpaca__place_stock_order"), PATTERN)
    assert r and "place_order" in r and "gate" in r


def test_the_gates_own_tools_and_non_order_tools_pass():
    assert h.decide(ev("mcp__gate__place_order"), PATTERN) is None
    assert h.decide(ev("mcp__agent-gate__place_order"), PATTERN) is None
    assert h.decide(ev("mcp__alpaca__get_account"), PATTERN) is None
    assert h.decide(ev("Bash"), PATTERN) is None


def test_gate_server_name_is_configurable():
    assert h.decide(ev("mcp__guard__place_order"), PATTERN, gate_server="guard") is None
    assert h.decide(ev("mcp__gate__place_order"), PATTERN, gate_server="guard")


def test_a_broken_pattern_refuses_rather_than_lets_through():
    assert h.decide(ev("mcp__alpaca__place_stock_order"), "(") is not None


def test_the_script_speaks_the_hook_protocol():
    env = dict(os.environ, CLAUDE_PLUGIN_OPTION_DIRECT_ORDER_PATTERN=PATTERN)
    out = subprocess.run([sys.executable, SCRIPT], input=json.dumps(ev("mcp__alpaca__place_stock_order")),
                         capture_output=True, text=True, env=env, timeout=30).stdout
    d = json.loads(out)["hookSpecificOutput"]
    assert d["hookEventName"] == "PreToolUse" and d["permissionDecision"] == "deny"
    env.pop("CLAUDE_PLUGIN_OPTION_DIRECT_ORDER_PATTERN")
    out = subprocess.run([sys.executable, SCRIPT], input=json.dumps(ev("mcp__alpaca__place_stock_order")),
                         capture_output=True, text=True, env=env, timeout=30).stdout
    assert out == ""


def test_plugin_manifest_and_hooks_are_valid_json():
    root = os.path.join(HERE, "..", "plugins", "evidence-deflator")
    m = json.load(open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8"))
    assert {"direct_order_pattern", "gate_server"} <= set(m["userConfig"])
    hooks = json.load(open(os.path.join(root, "hooks", "hooks.json"), encoding="utf-8"))["hooks"]
    assert any("gate_only_orders.py" in x["command"] for e in hooks["PreToolUse"] for x in e["hooks"])
