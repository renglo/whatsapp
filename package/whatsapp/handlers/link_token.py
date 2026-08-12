"""LINK token format helpers (cos-demo semantics)."""

from __future__ import annotations

import hashlib
import re
import secrets

CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
TOKEN_LEN = 20
LINK_CODE_TTL_SECONDS = 10 * 60

LINK_CODE_SEARCH_RE = re.compile(
    rf"(?<![A-Z0-9])LINK-([{CODE_ALPHABET}]{{{TOKEN_LEN}}}|[{CODE_ALPHABET}]{{4}})(?![A-Z0-9])",
    re.IGNORECASE,
)


def generate_link_token() -> str:
    body = "".join(secrets.choice(CODE_ALPHABET) for _ in range(TOKEN_LEN))
    return f"LINK-{body}"


def hash_link_code(code: str) -> str:
    normalized = code.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_link_code(text: str) -> str | None:
    match = LINK_CODE_SEARCH_RE.search(text or "")
    if not match:
        return None
    return f"LINK-{match.group(1).upper()}"


def link_prefill_message(code: str) -> str:
    return f"Hi — please connect my account: {code}"


def whatsapp_deep_link(number_digits: str, code: str) -> str:
    from urllib.parse import quote

    text = link_prefill_message(code)
    return f"https://wa.me/{number_digits}?text={quote(text)}"


def digits_only(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")
