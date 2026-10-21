"""Trading Mandate v0: an account owner's signed, expiring limits for one agent key.

The owner signs a short JSON document (which symbols, largest order, largest daily loss, how many
orders a day, from when until when) with an Ethereum key, the same kind of signature a wallet makes
for "Sign message" (EIP-191 personal_sign). The document names the one key allowed to act under it,
the gate's key. The gate checks every order against the mandate, signs each ledger line with that
key, and copies the mandate into the ledger, so the ledger alone is enough for anyone to check that
every allowed order was inside limits the owner signed (``audit``).

Spec: docs/gate/MANDATE.md. Needs eth-account (``pip install eth-account``).
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

TYPE = "trading-mandate"
VERSION = "0"
HEADER = "Trading mandate v0 (evidencedeflator.com/gate/mandate)\n"
SCOPE_KEYS = ("allow", "sides", "max_order_usd", "max_position_usd", "max_daily_loss_usd", "max_orders_per_day")


def _eth():
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct
    except ImportError as e:  # pragma: no cover
        raise SystemExit("mandates need eth-account: pip install eth-account") from e
    return Account, encode_defunct


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> float:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


# ---------------------------------------------------------------- keys

def keygen(path: str) -> str:
    """A fresh secp256k1 key in a file of its own; returns its address. Refuses to overwrite."""
    Account, _ = _eth()
    if os.path.exists(path):
        raise SystemExit(f"{path} exists; not overwriting a key")
    acct = Account.create(secrets.token_hex(32))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(acct.key.hex() + "\n")
    return acct.address


def load_key(path: str):
    Account, _ = _eth()
    with open(path, encoding="utf-8") as f:
        k = f.read().strip()
    return Account.from_key(k if k.startswith("0x") else "0x" + k)


def address_of(path: str) -> str:
    return load_key(path).address


def sign_text(key_path_or_account, text: str) -> str:
    Account, encode_defunct = _eth()
    acct = load_key(key_path_or_account) if isinstance(key_path_or_account, str) else key_path_or_account
    sig = acct.sign_message(encode_defunct(text=text)).signature.hex()
    return sig if sig.startswith("0x") else "0x" + sig


def recover(text: str, signature: str) -> str:
    Account, encode_defunct = _eth()
    return Account.recover_message(encode_defunct(text=text), signature=signature)


def same_addr(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a) and bool(b) and a.lower() == b.lower()


# ---------------------------------------------------------------- mandate

def draft(issuer: str, agent: str, venue: str, account: str, scope: Dict[str, Any],
          days: float = 30.0, now: Optional[float] = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    sc = {k: scope[k] for k in SCOPE_KEYS if scope.get(k) is not None}
    if "allow" in sc:
        sc["allow"] = sorted({s.upper() for s in sc["allow"]})
    sc.setdefault("sides", ["buy", "sell"])
    return {"type": TYPE, "version": VERSION, "id": secrets.token_hex(8), "issuer": issuer, "agent": agent,
            "venue": venue, "account": account, "scope": sc,
            "not_before": iso(now), "expires": iso(now + days * 86400)}


def message(m: Dict[str, Any]) -> str:
    """The exact text the owner signs: a fixed header line, then the mandate as canonical JSON."""
    return HEADER + canon(m)


def mandate_hash(signed: Dict[str, Any]) -> str:
    return hashlib.sha256(canon(signed).encode()).hexdigest()


def attach(m: Dict[str, Any], signature: str) -> Dict[str, Any]:
    return {"mandate": m, "sig": {"scheme": "eip191", "signature": signature}}


def sign(m: Dict[str, Any], issuer_key) -> Dict[str, Any]:
    return attach(m, sign_text(issuer_key, message(m)))


def verify(signed: Dict[str, Any], now: Optional[float] = None, agent: Optional[str] = None) -> List[str]:
    """Problems with a signed mandate; empty means it is valid now (and for ``agent``, if given)."""
    out: List[str] = []
    m, sig = signed.get("mandate") or {}, signed.get("sig") or {}
    if m.get("type") != TYPE or m.get("version") != VERSION:
        return [f"not a {TYPE} v{VERSION}"]
    if sig.get("scheme") != "eip191":
        return [f"unknown signature scheme {sig.get('scheme')}"]
    try:
        who = recover(message(m), sig["signature"])
    except Exception as e:
        return [f"signature does not parse ({e})"]
    if not same_addr(who, m.get("issuer")):
        out.append(f"signed by {who}, not by the issuer {m.get('issuer')}")
    if now is not None:
        if now < parse_iso(m["not_before"]):
            out.append(f"not valid before {m['not_before']}")
        if now >= parse_iso(m["expires"]):
            out.append(f"expired at {m['expires']}")
    if agent is not None and not same_addr(agent, m.get("agent")):
        out.append(f"names agent {m.get('agent')}, but this gate's key is {agent}")
    return out


def rules(signed: Dict[str, Any]) -> Dict[str, Any]:
    """The mandate's scope in the gate's rule vocabulary (agent_gate.check)."""
    sc = signed["mandate"]["scope"]
    return {"allow": sc.get("allow") or [], "max_order_usd": sc.get("max_order_usd"),
            "max_position_usd": sc.get("max_position_usd"), "max_daily_loss_usd": sc.get("max_daily_loss_usd"),
            "max_orders_per_day": sc.get("max_orders_per_day"), "sides": sc.get("sides") or ["buy", "sell"]}


def revocation_message(mandate_id: str, ts: str) -> str:
    return f"{HEADER}revoke {mandate_id} at {ts}"


def revoke(signed: Dict[str, Any], issuer_key, now: Optional[float] = None) -> Dict[str, Any]:
    ts = iso(time.time() if now is None else now)
    mid = signed["mandate"]["id"]
    return {"revoke": mid, "ts": ts, "signature": sign_text(issuer_key, revocation_message(mid, ts))}


def revocation_valid(rev: Dict[str, Any], signed: Dict[str, Any]) -> bool:
    m = signed["mandate"]
    if rev.get("revoke") != m["id"]:
        return False
    try:
        return same_addr(recover(revocation_message(rev["revoke"], rev["ts"]), rev["signature"]), m["issuer"])
    except Exception:
        return False


def load(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(obj: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
