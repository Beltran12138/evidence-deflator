"""tools/vault_flow_v2.py: exact flows exclude the leader; ledger paging neither drops nor doubles events."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import vault_flow_v2 as W  # noqa: E402

DAY = 86400 * 1000
VAULT, LEADER, FOLLOWER = "0xvault", "0xleader", "0xf1"


def dep(t, usdc, vault=VAULT):
    return {"time": t, "hash": f"d{t}{usdc}", "delta": {"type": "vaultDeposit", "vault": vault, "usdc": str(usdc)}}


def wd(t, usd, user, vault=VAULT):
    return {"time": t, "hash": f"w{t}{usd}", "delta": {"type": "vaultWithdraw", "vault": vault, "user": user,
                                                        "requestedUsd": str(usd), "netWithdrawnUsd": str(usd),
                                                        "commission": "0", "closingCost": "0", "basis": "0"}}


def test_flows_split_leader_from_followers():
    row = {"vault": VAULT, "leader": LEADER, "t": 100 * DAY, "av_t": 100_000.0}
    vault_ev = [dep(101 * DAY, 30_000), dep(102 * DAY, 20_000),       # 20k of these is the leader's
                wd(103 * DAY, 5_000, FOLLOWER), wd(104 * DAY, 10_000, LEADER),
                dep(99 * DAY, 999_999), dep(131 * DAY, 999_999),       # outside (t, t + 30d]
                dep(105 * DAY, 777, vault="0xother")]                  # another vault
    leader_ev = [dep(102 * DAY, 20_000), dep(110 * DAY, 4_000, vault="0xother")]
    f_all, f_star = W.flows(row, vault_ev, leader_ev)
    assert f_all == pytest.approx((50_000 - 15_000) / 100_000)
    assert f_star == pytest.approx((30_000 - 5_000) / 100_000)


def test_ledger_paging_keeps_every_event_once(monkeypatch):
    events = [dep(W.START + i, 1) for i in range(4500)]
    events += [dep(W.START + 3999, 2)]  # a second event in the millisecond that ends page two
    events.sort(key=lambda e: e["time"])
    calls = []

    def fake_post(body, tries=12):
        calls.append(body["startTime"])
        return [e for e in events if e["time"] >= body["startTime"]][:2000]

    monkeypatch.setattr(W, "post", fake_post)
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    got = W.ledger(VAULT)
    assert len(got) == len(events)
    assert len({(e["time"], e["delta"]["usdc"]) for e in got}) == len(events)
