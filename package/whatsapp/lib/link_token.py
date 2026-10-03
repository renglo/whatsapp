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


def normalize_wa_me_digits(phone: str, *, default_country_code: str = "1") -> str:
    """
    Normalize to international digits for wa.me / api.whatsapp.com (no ``+``).

    Handles common config mistakes such as NANP numbers saved without country code ``1``.
    """
    digits = digits_only(phone)
    if not digits:
        return ""
    while digits.startswith("00") and len(digits) > 4:
        digits = digits[2:]
    cc = digits_only(default_country_code) or "1"
    if len(digits) == 10 and cc == "1":
        return f"1{digits}"
    return digits


def format_e164_display(phone: str) -> str:
    """Human-readable E.164, e.g. ``+1 555 676 3551``."""
    digits = normalize_wa_me_digits(phone)
    if len(digits) == 11 and digits.startswith("1"):
        return f"+1 {digits[1:4]} {digits[4:7]} {digits[7:]}"
    if digits:
        return f"+{digits}"
    return ""


def is_meta_us_test_number(phone: str) -> bool:
    """
    Meta-provided US sandbox numbers use NANP ``555`` and are not public wa.me targets.

    They only exchange messages with phone numbers added as test recipients in the
    Meta App Dashboard (WhatsApp → API Setup).
    """
    digits = normalize_wa_me_digits(phone)
    return len(digits) == 11 and digits.startswith("1") and digits[1:4] == "555"
