"""tools/build_registry.py: reading issue forms into registry entries."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_registry as br  # noqa: E402

A1, A2 = "0x" + "a" * 40, "0x" + "b" * 40


def issue(title, body, created, user="alice", labels=()):
    return {"title": title, "body": body, "created_at": created, "html_url": "https://github.com/x/y/issues/1",
            "user": {"login": user}, "labels": [{"name": n} for n in labels]}


def form(addr, name="Bot", trials="_No response_"):
    return (f"### Hyperliquid wallet address\n\n{addr}\n\n### Agent name\n\n{name}\n\n"
            f"### Model and its training cutoff\n\n_No response_\n\n### Strategies tried before this one\n\n{trials}\n")


def test_parse_form_reads_answers_and_skips_no_response():
    f = br.parse_form(form(A1, "Alpha", "40"))
    assert f == {"address": A1, "name": "Alpha", "trials": "40"}


def test_entries_keep_the_earliest_registration_and_drop_bad_ones():
    raw = [
        issue("[registry] later dup", form(A1.upper().replace("0X", "0x"), "Dup"), "2026-11-02T00:00:00Z"),
        issue("[registry] first", form(A1, "First"), "2026-11-01T00:00:00Z"),
        issue("[registry] bad address", form("0x123"), "2026-11-01T01:00:00Z"),
        issue("not a registration", form(A2), "2026-11-01T02:00:00Z"),
        issue("[registry] flagged", form(A2), "2026-11-01T03:00:00Z", labels=("invalid",)),
    ]
    out = br.entries(raw)
    assert [(e["address"], e["name"], e["registered_at"]) for e in out] == [(A1, "First", "2026-11-01T00:00:00Z")]
