"""channel_identities, channel_link_codes, and inbound dedup ring operations."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any

from .link_token import (
    LINK_CODE_TTL_SECONDS,
    extract_link_code,
    generate_link_token,
    hash_link_code,
)

_logger = logging.getLogger(__name__)

CHANNEL = "whatsapp"
IDENTITIES_RING = "channel_identities"
CODES_RING = "channel_link_codes"
DEDUP_RING = "channel_inbound_dedup"
INBOUND_DEDUP_TTL_SECONDS = 7 * 24 * 60 * 60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _attrs(row: dict[str, Any]) -> dict[str, Any]:
    attrs = dict(row.get("attributes") or {})
    if "_id" in row:
        attrs["_id"] = row["_id"]
    elif "_id" not in attrs and row.get("_id"):
        attrs["_id"] = row["_id"]
    # When callers already flattened via get_a_b / get_a_b_query:
    if not attrs and row:
        attrs = dict(row)
    return attrs


class IdentityStore:
    def __init__(self, data_controller: Any, portfolio: str, org: str) -> None:
        org_id = str(org or "").strip()
        if not org_id:
            raise ValueError("org is required")
        self.DAC = data_controller
        self.portfolio = portfolio
        self.org = org_id

    def _query(self, ring: str, value: str) -> list[dict[str, Any]]:
        response = self.DAC.get_a_b_query(
            {
                "portfolio": self.portfolio,
                "org": self.org,
                "ring": ring,
                "operator": "begins_with",
                "value": value,
                "limit": 50,
                "lastkey": None,
                "sort": "desc",
            }
        )
        if not response.get("success"):
            return []
        return list(response.get("items") or [])

    def _system_post(self, ring: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.DAC.construct_post_item(self.portfolio, self.org, ring, payload)
        return self.DAC.DAM.post_a_b(self.portfolio, self.org, ring, item)

    def _system_put(self, ring: str, idx: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.DAC.construct_put_item(self.portfolio, self.org, ring, idx, payload)
        if "error" in item:
            return item
        return self.DAC.DAM.put_a_b_c(self.portfolio, self.org, ring, idx, item)

    def _system_delete(self, ring: str, idx: str) -> dict[str, Any]:
        return self.DAC.DAM.delete_a_b_c(self.portfolio, self.org, ring, idx)

    def _list_ring_raw(self, ring: str) -> list[dict[str, Any]]:
        listed = self.DAC.DAM.get_a_b(self.portfolio, self.org, ring, limit=200)
        return [_attrs(r) for r in (listed.get("items") or [])]

    def _claim_dedup(
        self,
        *,
        id_hash: str,
        message_id: str,
        ttl_seconds: int = INBOUND_DEDUP_TTL_SECONDS,
    ) -> bool:
        """Return True when the dedup key is new; False when an active row already exists."""
        prefix = f"{CHANNEL}:{id_hash}"
        now = int(time.time())
        for item in self._query(DEDUP_RING, prefix):
            if str(item.get("message_id")) != message_id and str(item.get("id_hash")) != id_hash:
                continue
            try:
                expires = int(str(item.get("expires_at") or "0"))
            except ValueError:
                expires = 0
            if expires and expires < now:
                continue
            return False
        expires_at = now + max(60, int(ttl_seconds))
        posted = self._system_post(
            DEDUP_RING,
            {
                "channel": CHANNEL,
                "id_hash": id_hash,
                "message_id": message_id,
                "expires_at": str(expires_at),
            },
        )
        if posted.get("error"):
            _logger.warning("inbound dedup record failed: %s", posted)
            return True
        return True

    def claim_inbound_envelope(
        self,
        body_hash: str,
        *,
        ttl_seconds: int = INBOUND_DEDUP_TTL_SECONDS,
    ) -> bool:
        """Return True when this exact webhook body is new; False on EventBridge/Meta replays."""
        digest = (body_hash or "").strip().lower()
        if not digest:
            return True
        token = f"envelope:{digest}"
        id_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return self._claim_dedup(id_hash=id_hash, message_id=token, ttl_seconds=ttl_seconds)

    def claim_inbound_message(
        self,
        message_id: str,
        *,
        ttl_seconds: int = INBOUND_DEDUP_TTL_SECONDS,
    ) -> bool:
        """Return True when this Meta ``messages[].id`` is new; False when already seen."""
        text = (message_id or "").strip()
        if not text:
            return True
        id_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return self._claim_dedup(id_hash=id_hash, message_id=text, ttl_seconds=ttl_seconds)

    def resolve_identity(self, external_id: str) -> dict[str, Any] | None:
        items = self._query(IDENTITIES_RING, f"{CHANNEL}:{external_id}")
        for item in items:
            if str(item.get("channel")) == CHANNEL and str(item.get("external_id")) == external_id:
                return item
        return None

    def list_for_user(self, user_id: str, *, authenticated: bool = True) -> list[dict[str, Any]]:
        if authenticated:
            response = self.DAC.get_a_b(self.portfolio, self.org, IDENTITIES_RING, limit=200)
            if response.get("success") is False:
                return []
            items = response.get("items") or []
        else:
            items = self._list_ring_raw(IDENTITIES_RING)
        return [
            i
            for i in items
            if str(i.get("channel")) == CHANNEL and str(i.get("user_id")) == user_id
        ]

    def mint_link_code(self, user_id: str) -> dict[str, Any]:
        code = generate_link_token()
        code_hash = hash_link_code(code)
        expires_at = int(time.time()) + LINK_CODE_TTL_SECONDS

        listed = self.DAC.get_a_b(self.portfolio, self.org, CODES_RING, limit=200)
        pending = listed.get("items") or [] if listed.get("success") else []
        for row in pending:
            if (
                str(row.get("channel")) == CHANNEL
                and str(row.get("user_id")) == user_id
                and not str(row.get("consumed_at") or "").strip()
            ):
                doc_id = row.get("_id")
                if doc_id:
                    self.DAC.put_a_b_c(
                        self.portfolio,
                        self.org,
                        CODES_RING,
                        doc_id,
                        {"expires_at": "0"},
                    )

        doc = {
            "channel": CHANNEL,
            "code_hash": code_hash,
            "user_id": user_id,
            "expires_at": str(expires_at),
            "consumed_at": "",
        }
        response, status = self.DAC.post_a_b(self.portfolio, self.org, CODES_RING, doc)
        if not response.get("success"):
            return {
                "success": False,
                "message": "Could not mint link code",
                "output": response,
                "status": status,
            }
        return {
            "success": True,
            "code": code,
            "expires_at": expires_at,
            "expires_at_iso": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
            "output": response,
        }

    def _pending_link_row(self, code: str) -> dict[str, Any] | None:
        code_hash = hash_link_code(code)
        items = self._query(CODES_RING, f"{CHANNEL}:{code_hash}")
        row = next(
            (
                i
                for i in items
                if str(i.get("channel")) == CHANNEL
                and str(i.get("code_hash")) == code_hash
                and not str(i.get("consumed_at") or "").strip()
            ),
            None,
        )
        if not row:
            return None
        try:
            expires_at = int(float(str(row.get("expires_at") or "0")))
        except (TypeError, ValueError):
            expires_at = 0
        if expires_at <= int(time.time()):
            return None
        if not str(row.get("user_id") or "").strip():
            return None
        return row

    def pending_link_minter(self, code: str) -> str | None:
        """User id that minted this unconsumed, unexpired code. Does not consume."""
        row = self._pending_link_row(code)
        if not row:
            return None
        return str(row.get("user_id") or "")

    def consume_link_code(
        self,
        *,
        external_id: str,
        code: str,
        display_name: str = "",
    ) -> dict[str, Any]:
        row = self._pending_link_row(code)
        if not row:
            return {"status": "invalid"}

        minter = str(row.get("user_id") or "")
        if not minter:
            return {"status": "invalid"}

        existing = self.resolve_identity(external_id)
        if existing and str(existing.get("user_id")) != minter:
            return {"status": "conflict"}

        doc_id = row.get("_id")
        if not doc_id:
            return {"status": "invalid"}

        claim = self._system_put(CODES_RING, doc_id, {"consumed_at": _now_iso()})
        if claim.get("error"):
            _logger.error("Failed to claim link code: %s", claim)
            return {"status": "invalid"}

        replaced: list[dict[str, str]] = []
        for ident in self._list_ring_raw(IDENTITIES_RING):
            if (
                str(ident.get("channel")) == CHANNEL
                and str(ident.get("user_id")) == minter
                and str(ident.get("external_id")) != external_id
            ):
                rid = ident.get("_id")
                if rid:
                    self._system_delete(IDENTITIES_RING, rid)
                    replaced.append(
                        {
                            "external_id": str(ident.get("external_id") or ""),
                            "display_name": str(ident.get("display_name") or ""),
                        }
                    )

        now = _now_iso()
        if existing and str(existing.get("user_id")) == minter:
            eid = existing.get("_id")
            if eid:
                self._system_put(
                    IDENTITIES_RING,
                    eid,
                    {
                        "display_name": display_name or existing.get("display_name") or "",
                        "last_seen_at": now,
                    },
                )
        else:
            posted = self._system_post(
                IDENTITIES_RING,
                {
                    "channel": CHANNEL,
                    "external_id": external_id,
                    "user_id": minter,
                    "display_name": display_name or "",
                    "linked_at": now,
                    "last_seen_at": now,
                },
            )
            if posted.get("error"):
                _logger.error("Failed to create identity: %s", posted)
                return {"status": "invalid"}

        return {"status": "linked", "user_id": minter, "replaced": replaced}

    def unlink(self, user_id: str, external_id: str | None = None) -> dict[str, Any]:
        identities = self.list_for_user(user_id, authenticated=True)
        removed = []
        for ident in identities:
            if external_id and str(ident.get("external_id")) != external_id:
                continue
            doc_id = ident.get("_id")
            if not doc_id:
                continue
            response, status = self.DAC.delete_a_b_c(
                self.portfolio, self.org, IDENTITIES_RING, doc_id
            )
            removed.append(
                {"id": doc_id, "success": bool(response.get("success")), "status": status}
            )
        return {"success": True, "removed": removed}

    def touch_last_seen(self, identity: dict[str, Any]) -> None:
        doc_id = identity.get("_id")
        if not doc_id:
            return
        try:
            self._system_put(IDENTITIES_RING, doc_id, {"last_seen_at": _now_iso()})
        except Exception as exc:
            _logger.warning("touch_last_seen failed: %s", exc)


def extract_code_from_text(text: str) -> str | None:
    return extract_link_code(text)
