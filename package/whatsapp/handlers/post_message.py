"""Send a WhatsApp text message via Meta Graph API."""

from __future__ import annotations

from typing import Any, Dict

from renglo.common import load_config
from renglo.data.data_controller import DataController

from ..lib.config import CONFIG_ORG, ConfigStore
from ..lib.describe import describe_document
from ..lib.meta_client import send_whatsapp_text


class PostMessage:
    def __init__(self) -> None:
        config = load_config()
        self.DAC = DataController(config=config)

    def describe(self, payload=None):
        return describe_document(
            "post_message",
            "Send WhatsApp message",
            "Send a WhatsApp text via the Meta Graph API. portfolio is injected by the platform. "
            "target also accepts to. message also accepts text.",
            {
                "target": {
                    "type": "string",
                    "title": "Recipient",
                    "description": "WhatsApp id of the recipient.",
                },
                "message": {"type": "string", "title": "Message"},
            },
            required=["target", "message"],
            output_schema={
                "type": "object",
                "description": "Meta Graph API send result.",
            },
        )

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
