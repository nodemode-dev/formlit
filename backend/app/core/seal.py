import hashlib
import hmac
import json
import secrets

SERVICE = "formlit"
ACCOUNT = "settings-seal"
FIELD = "seal"
REPORTS = ("seal", "sealBroken")
PATHS = ("claudeBin", "codexBin", "cursorBin", "antigravityBin")
LATER = ("codexBin", "cursorBin", "antigravityBin")
SEALED = ("outsideAgents",) + PATHS
_CACHE: dict = {"tried": False, "available": False, "key": None}


def reset() -> None:
    _CACHE.update(tried=False, available=False, key=None)


def _load(create: bool) -> bytes | None:
    if _CACHE["tried"] and (_CACHE["key"] is not None or not _CACHE["available"] or not create):
        return _CACHE["key"]
    _CACHE["tried"] = True
    try:
        import keyring

        stored = keyring.get_password(SERVICE, ACCOUNT)
        if not stored and create:
            keyring.set_password(SERVICE, ACCOUNT, secrets.token_hex(32))
            stored = keyring.get_password(SERVICE, ACCOUNT)
        key = bytes.fromhex(stored) if stored else None
    except Exception:
        _CACHE.update(available=False, key=None)
        return None
    _CACHE.update(available=True, key=key)
    return key


def digest(values: dict, key: bytes) -> str:
    body = json.dumps({k: values.get(k) for k in SEALED if k not in LATER or values.get(k)}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(key, body.encode("utf-8"), hashlib.sha256).hexdigest()


def loosened(values: dict) -> bool:
    return values.get("outsideAgents") == "allowed" or any(str(values.get(k) or "").strip() for k in PATHS)


def effective(stored: dict) -> dict:
    out = {k: v for k, v in stored.items() if k != FIELD and k not in REPORTS}
    key = _load(False)
    if not _CACHE["available"]:
        return {**out, "seal": "unavailable", "sealBroken": False}
    mark = stored.get(FIELD)
    if key is not None and isinstance(mark, str) and hmac.compare_digest(mark, digest(stored, key)):
        return {**out, "seal": "ok", "sealBroken": False}
    if not loosened(stored):
        return {**out, "seal": "unsealed", "sealBroken": False}
    out.update(outsideAgents="blocked" if stored.get("outsideAgents") == "blocked" else "ask", **{k: "" for k in PATHS})
    return {**out, "seal": "broken", "sealBroken": True}


def sign(merged: dict) -> dict:
    key = _load(True)
    clean = {k: v for k, v in merged.items() if k != FIELD and k not in REPORTS}
    if key is None:
        return clean
    return {**clean, FIELD: digest(clean, key)}
