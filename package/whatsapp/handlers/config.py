"""Load / ensure the singleton ``whatsapp_config`` ring document."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

_logger = logging.getLogger(__name__)

SINGLETON_ID = "00000000-0000-0000-0000-000000000000"
RING = "whatsapp_config"
CONFIG_ORG = "_all"


@dataclass
class WhatsappConfig:
    phone_number_id: str = ""
    access_token: str = ""
    app_secret: str = ""
    verify_token: str = ""
    display_phone_e164: str = ""
    api_version: str = "v22.0"
    agent_handler: str = "dumbo/generic_agent"
    webhook_enabled: bool = True

    def is_send_ready(self) -> bool:
        return bool(self.phone_number_id and self.access_token)

    def is_verify_ready(self) -> bool:
        return bool(self.app_secret and self.verify_token)


class ConfigStore:
    """Reads / ensures the extension singleton config (portfolio-scoped at ``_all``)."""

    def __init__(self, data_controller: Any, portfolio: str, org: str = CONFIG_ORG) -> None:
        self.DAC = data_controller
        self.portfolio = portfolio
        self.org = org or CONFIG_ORG

    def _parse_bool(self, raw: Any, default: bool = True) -> bool:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        if raw is None:
            return default
        return bool(raw)

    def _from_doc(self, res: dict[str, Any]) -> WhatsappConfig:
        return WhatsappConfig(
            phone_number_id=str(res.get("phone_number_id") or "").strip(),
            access_token=str(res.get("access_token") or "").strip(),
            app_secret=str(res.get("app_secret") or "").strip(),
            verify_token=str(res.get("verify_token") or "").strip(),
            display_phone_e164=str(res.get("display_phone_e164") or "").strip(),
            api_version=str(res.get("api_version") or "v22.0").strip() or "v22.0",
            agent_handler=str(res.get("agent_handler") or "dumbo/generic_agent").strip()
            or "dumbo/generic_agent",
            webhook_enabled=self._parse_bool(res.get("webhook_enabled"), True),
        )

    def load_raw(self) -> dict[str, Any] | None:
        """Load singleton via DataModel (no authorize) — for webhook ingress."""
        try:
            row = self.DAC.DAM.get_a_b_c(self.portfolio, self.org, RING, SINGLETON_ID)
            if not row or row.get("error") or "_id" not in row:
                listed = self.DAC.DAM.get_a_b(self.portfolio, self.org, RING, limit=5)
                items = listed.get("items") or []
                if not items:
                    return None
                row = next(
                    (i for i in items if str(i.get("_id")) == SINGLETON_ID),
                    items[0],
                )
            attrs = dict(row.get("attributes") or {})
            if not attrs and isinstance(row, dict):
                # Unexpected shape — last resort
                attrs = {k: v for k, v in row.items() if not str(k).startswith("portfolio")}
            attrs["_id"] = row.get("_id") or attrs.get("_id") or SINGLETON_ID
            return attrs
        except Exception as exc:
            _logger.warning("Failed to load whatsapp_config (raw): %s", exc)
            return None

    def load(self) -> WhatsappConfig:
        try:
            res = self.DAC.get_a_b_c(self.portfolio, self.org, RING, SINGLETON_ID)
            if res.get("success") is False or "_id" not in res:
                raw = self.load_raw()
                if not raw:
                    _logger.warning("whatsapp_config not found; using defaults")
                    return WhatsappConfig()
                return self._from_doc(raw)
            return self._from_doc(res)
        except Exception as exc:
            _logger.warning("Failed to load whatsapp_config: %s", exc)
            raw = self.load_raw()
            if raw:
                return self._from_doc(raw)
            return WhatsappConfig()

    def load_for_ingress(self) -> WhatsappConfig:
        """Unauthenticated path used by inbound webhook processing."""
        raw = self.load_raw()
        if not raw:
            return WhatsappConfig()
        return self._from_doc(raw)

    def ensure_defaults(self, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        defaults = {
            "phone_number_id": "",
            "access_token": "",
            "app_secret": "",
            "verify_token": "",
            "display_phone_e164": "",
            "api_version": "v22.0",
            "agent_handler": "dumbo/generic_agent",
            "webhook_enabled": "true",
        }
        if payload:
            defaults.update(payload)
        existing = self.DAC.get_a_b_c(self.portfolio, self.org, RING, SINGLETON_ID)
        if existing.get("success") is not False and "_id" in existing:
            return {
                "success": True,
                "action": "ensure_whatsapp_config",
                "message": "Config already present",
                "output": existing,
            }
        response, _status = self.DAC.post_a_b(self.portfolio, self.org, RING, defaults)
        return {
            "success": bool(response.get("success")),
            "action": "ensure_whatsapp_config",
            "message": "Config created" if response.get("success") else "Config create failed",
            "output": response,
        }
