"""Meta Cloud API helpers — HMAC verify + Graph send."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

_logger = logging.getLogger(__name__)

GRAPH_HOST = "https://graph.facebook.com"


def verify_meta_signature(*, raw_body: str, signature: str | None, app_secret: str) -> bool:
    """Validate ``X-Hub-Signature-256`` against the exact raw body Meta signed."""
    if not signature or not app_secret:
        return False
    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    try:
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def meta_webhook_handshake(
    *,
    mode: str | None,
    token: str | None,
    challenge: str | None,
    verify_token: str,
) -> str | None:
    """Return challenge string when GET subscribe handshake is valid."""
    if mode != "subscribe" or not verify_token or token is None or challenge is None:
        return None
    if not hmac.compare_digest(str(token), str(verify_token)):
        return None
    return str(challenge)


def send_whatsapp_text(
    *,
    access_token: str,
    phone_number_id: str,
    to: str,
    body: str,
    api_version: str = "v22.0",
) -> dict[str, Any]:
    """POST a free-form text message via Graph API."""
    if not access_token or not phone_number_id or not to or not body:
        return {"success": False, "error": "Missing send parameters"}

    url = f"{GRAPH_HOST}/{api_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    try:
        import requests

        response = requests.post(url, headers=headers, json=payload, timeout=20)
        data = {}
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}
        if not response.ok:
            _logger.error("Meta send failed %s: %s", response.status_code, data)
            return {
                "success": False,
                "status": response.status_code,
                "error": data,
            }
        message_id = None
        messages = data.get("messages") if isinstance(data, dict) else None
        if isinstance(messages, list) and messages:
            message_id = messages[0].get("id")
        return {"success": True, "id": message_id, "output": data}
    except Exception as exc:
        _logger.exception("Meta send exception")
        return {"success": False, "error": str(exc)}


def parse_meta_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract inbound text messages from a Meta Cloud webhook body.

    Returns a list of dicts: external_id, display_name, text, message_id, timestamp.
    """
    results: list[dict[str, Any]] = []
    entries = payload.get("entry") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return results

    for entry in entries:
        changes = (entry or {}).get("changes") or []
        for change in changes:
            value = (change or {}).get("value") or {}
            messages = value.get("messages") or []
            if not messages:
                continue
            contacts = value.get("contacts") or []
            contact_by_wa: dict[str, str] = {}
            for contact in contacts:
                wa_id = str((contact or {}).get("wa_id") or "")
                name = str(((contact or {}).get("profile") or {}).get("name") or "")
                if wa_id:
                    contact_by_wa[wa_id] = name

            for message in messages:
                if not isinstance(message, dict):
                    continue
                if message.get("type") != "text":
                    continue
                text = str(((message.get("text") or {}).get("body")) or "").strip()
                if not text:
                    continue
                external_id = str(message.get("from") or "")
                if not external_id:
                    continue
                results.append(
                    {
                        "external_id": external_id,
                        "display_name": contact_by_wa.get(external_id, ""),
                        "text": text,
                        "message_id": str(message.get("id") or ""),
                        "timestamp": str(message.get("timestamp") or ""),
                    }
                )
    return results
