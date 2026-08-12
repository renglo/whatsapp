"""Send a WhatsApp text message via Meta Graph API."""

from __future__ import annotations

from typing import Any, Dict

from renglo.common import load_config
from renglo.data.data_controller import DataController

from .config import CONFIG_ORG, ConfigStore
from .meta_client import send_whatsapp_text


class PostMessage:
    def __init__(self) -> None:
        config = load_config()
        self.DAC = DataController(config=config)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        portfolio = str(payload.get("portfolio") or "")
        if not portfolio:
            return {"success": False, "message": "portfolio required"}

        target = str(payload.get("target") or payload.get("to") or "").strip()
        message = str(payload.get("message") or payload.get("text") or "").strip()
        if not target or not message:
            return {"success": False, "message": "target and message required"}

        # Prefer authenticated load; fall back to ingress load for system callers.
        store = ConfigStore(self.DAC, portfolio, CONFIG_ORG)
        try:
            cfg = store.load()
            if not cfg.is_send_ready():
                cfg = store.load_for_ingress()
        except Exception:
            cfg = store.load_for_ingress()

        if not cfg.is_send_ready():
            return {
                "success": False,
                "message": "whatsapp_config missing phone_number_id or access_token",
            }

        result = send_whatsapp_text(
            access_token=cfg.access_token,
            phone_number_id=cfg.phone_number_id,
            to=target,
            body=message,
            api_version=cfg.api_version,
        )
        return {
            "success": bool(result.get("success")),
            "action": "post_message",
            "input": {"target": target, "message": message},
            "output": result,
        }
