"""Process Meta WhatsApp webhook events (HMAC verify, LINK gate, agent dispatch)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from renglo.auth.auth_controller import AuthController
from renglo.common import load_config
from renglo.data.data_controller import DataController
from renglo.schd.schd_loader import SchdLoader

from .config import CONFIG_ORG, ConfigStore
from .identity_store import IdentityStore, extract_code_from_text
from .meta_client import parse_meta_messages, send_whatsapp_text, verify_meta_signature
from .session_coords import ensure_renglo_thread, record_channel_delivery

_logger = logging.getLogger(__name__)

LINKED_REPLY = "✓ Connected. You can message me here anytime."
UNLINKED_REPLY = (
    "This WhatsApp number is not linked yet. "
    "Open the Renglo console → WhatsApp → Connect WhatsApp to link your account."
)
CONFLICT_REPLY = (
    "This WhatsApp number is already linked to another account. "
    "Unlink it there first, or contact your admin."
)
EXPIRED_REPLY = "That link code expired. Generate a new one in the console and try again."
INVALID_REPLY = "That link code is not valid. Generate a new one in the console and try again."


class Inbound:
    def __init__(self) -> None:
        config = load_config()
        self.config = config
        self.DAC = DataController(config=config)
        self.AUC = AuthController(config=config)
        self.SHL = SchdLoader()

    def _send(self, cfg, to: str, body: str) -> dict[str, Any]:
        if not cfg.is_send_ready():
            return {"success": False, "error": "send not configured"}
        return send_whatsapp_text(
            access_token=cfg.access_token,
            phone_number_id=cfg.phone_number_id,
            to=to,
            body=body,
            api_version=cfg.api_version,
        )

    def _extract_agent_text(self, agent_result: dict[str, Any]) -> str:
        if not isinstance(agent_result, dict):
            return ""
        # SchdLoader wraps: {success, output: handler_result}
        outer = agent_result.get("output", agent_result)
        if isinstance(outer, dict) and "output" in outer and "success" in outer:
            handler_out = outer
        elif isinstance(outer, dict):
            handler_out = outer
        else:
            return str(outer) if outer else ""

        for key in ("message", "reply", "text", "response"):
            val = handler_out.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

        nested = handler_out.get("output")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
        if isinstance(nested, dict):
            for key in ("message", "reply", "text", "response", "content"):
                val = nested.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        if isinstance(nested, list) and nested:
            last = nested[-1]
            if isinstance(last, str):
                return last.strip()
            if isinstance(last, dict):
                for key in ("message", "content", "text"):
                    val = last.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
        return ""

    def _run_agent(
        self,
        *,
        agent_handler: str,
        portfolio: str,
        org: str,
        user_id: str,
        message: str,
        external_id: str,
    ) -> dict[str, Any]:
        parts = agent_handler.split("/")
        if len(parts) != 2:
            return {"success": False, "error": f"Invalid agent_handler: {agent_handler}"}

        extension, handler_name = parts[0], parts[1]
        class_name = self.SHL.convert_module_name_to_class(handler_name)
        instance = self.SHL.load_code_class(extension, handler_name, class_name)
        if not instance:
            return {"success": False, "error": f"Could not load {agent_handler}"}

        # Impersonate the linked user so authorize() inside the agent succeeds.
        for attr in ("AUC", "DAC", "SHC", "CHC", "SSC"):
            controller = getattr(instance, attr, None)
            if controller is None:
                continue
            if hasattr(controller, "set_invocation_user"):
                controller.set_invocation_user(user_id)
            nested_auc = getattr(controller, "AUC", None)
            if nested_auc is not None and hasattr(nested_auc, "set_invocation_user"):
                nested_auc.set_invocation_user(user_id)

        self.AUC.set_invocation_user(user_id)
        self.DAC.AUC.set_invocation_user(user_id)

        session_org = CONFIG_ORG
        coords = ensure_renglo_thread(
            config=self.config,
            portfolio=portfolio,
            org=session_org,
            user_id=user_id,
        )
        if not coords.get("success"):
            return {
                "success": False,
                "error": coords.get("message") or "Could not resolve Renglo thread",
                "coords": coords,
            }

        agent_payload = {
            "portfolio": portfolio,
            "org": session_org,
            "user_id": user_id,
            "public_user": user_id,
            "entity_type": coords["entity_type"],
            "entity_id": coords["entity_id"],
            "thread": coords["thread_id"],
            "channel": "whatsapp",
            "data": message,
            "message": message,
            "external_id": external_id,
        }
        try:
            result = instance.run(agent_payload)
            return {
                "success": True,
                "output": result,
                "entity_type": coords["entity_type"],
                "entity_id": coords["entity_id"],
                "thread_id": coords["thread_id"],
            }
        except Exception as exc:
            _logger.exception("Agent dispatch failed")
            return {"success": False, "error": str(exc)}

    def _handle_message(
        self,
        *,
        portfolio: str,
        org: str,
        cfg,
        store: IdentityStore,
        msg: dict[str, Any],
    ) -> dict[str, Any]:
        external_id = msg["external_id"]
        text = msg["text"]
        display_name = msg.get("display_name") or ""

        identity = store.resolve_identity(external_id)
        link_code = extract_code_from_text(text)

        if identity:
            store.touch_last_seen(identity)
            user_id = str(identity.get("user_id") or "")
            if link_code:
                # Already linked — confirm without burning a new code.
                self._send(cfg, external_id, "✓ Already connected.")
                return {
                    "success": True,
                    "action": "already_linked",
                    "user_id": user_id,
                    "external_id": external_id,
                }

            agent_result = self._run_agent(
                agent_handler=cfg.agent_handler,
                portfolio=portfolio,
                org=org,
                user_id=user_id,
                message=text,
                external_id=external_id,
            )
            reply = self._extract_agent_text(agent_result)
            send_result = None
            delivery = None
            if reply:
                send_result = self._send(cfg, external_id, reply)
                delivery = record_channel_delivery(
                    config=self.config,
                    portfolio=portfolio,
                    org=CONFIG_ORG,
                    user_id=user_id,
                    agent_result=agent_result,
                    channel="whatsapp",
                    external_id=external_id,
                    send_result=send_result,
                    text=reply,
                )
                if not (delivery or {}).get("success"):
                    _logger.warning(
                        "Could not persist channel_delivery: %s", delivery
                    )
                if not (send_result or {}).get("success"):
                    _logger.error(
                        "WhatsApp delivery failed for %s: %s",
                        external_id,
                        send_result,
                    )
            elif not agent_result.get("success"):
                _logger.error("Agent failed: %s", agent_result)
            return {
                "success": True,
                "action": "agent",
                "user_id": user_id,
                "external_id": external_id,
                "agent": agent_result,
                "reply": reply,
                "send": send_result,
                "delivery": delivery,
            }

        # Unlinked
        if link_code:
            result = store.consume_link_code(
                external_id=external_id,
                code=link_code,
                display_name=display_name,
            )
            status = result.get("status")
            if status == "linked":
                self._send(cfg, external_id, LINKED_REPLY)
            elif status == "conflict":
                self._send(cfg, external_id, CONFLICT_REPLY)
            elif status == "expired":
                self._send(cfg, external_id, EXPIRED_REPLY)
            else:
                self._send(cfg, external_id, INVALID_REPLY)
            return {
                "success": True,
                "action": "link_consume",
                "status": status,
                "external_id": external_id,
                "result": result,
            }

        self._send(cfg, external_id, UNLINKED_REPLY)
        return {
            "success": True,
            "action": "unlinked_nag",
            "external_id": external_id,
        }

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        portfolio = str(payload.get("portfolio") or "")
        org = str(payload.get("org") or CONFIG_ORG)
        if not portfolio:
            return {"success": False, "message": "portfolio required"}

        raw_body = payload.get("raw_body")
        if raw_body is None and "gupshup_payload" in payload:
            # Compatibility shim — not used for Meta, but keep tolerant.
            raw_body = json.dumps(payload.get("gupshup_payload") or {})
        if raw_body is None and isinstance(payload.get("body"), (dict, list)):
            raw_body = json.dumps(payload["body"])
        if raw_body is None:
            raw_body = payload.get("detail_raw_body") or ""

        if isinstance(raw_body, (dict, list)):
            body_obj = raw_body
            raw_body = json.dumps(raw_body)
        else:
            raw_body = str(raw_body or "")
            try:
                body_obj = json.loads(raw_body) if raw_body else {}
            except json.JSONDecodeError:
                return {"success": False, "message": "Invalid JSON body"}

        signature = (
            payload.get("signature_header")
            or payload.get("x_hub_signature_256")
            or payload.get("X-Hub-Signature-256")
            or ""
        )

        cfg = ConfigStore(self.DAC, portfolio, CONFIG_ORG).load_for_ingress()
        if not cfg.webhook_enabled:
            return {"success": True, "action": "disabled", "message": "webhook_enabled=false"}

        if not cfg.app_secret:
            _logger.error("whatsapp_config.app_secret missing for %s", portfolio)
            return {"success": False, "message": "app_secret not configured"}

        if not verify_meta_signature(
            raw_body=raw_body,
            signature=str(signature) if signature else None,
            app_secret=cfg.app_secret,
        ):
            _logger.warning("Invalid Meta signature for portfolio %s", portfolio)
            return {"success": False, "message": "Invalid signature", "status": 403}

        messages = parse_meta_messages(body_obj if isinstance(body_obj, dict) else {})
        if not messages:
            return {"success": True, "action": "ignore", "message": "No text messages"}

        store = IdentityStore(self.DAC, portfolio, CONFIG_ORG)
        results: List[Dict[str, Any]] = []
        for msg in messages:
            results.append(
                self._handle_message(
                    portfolio=portfolio,
                    org=org,
                    cfg=cfg,
                    store=store,
                    msg=msg,
                )
            )

        return {
            "success": True,
            "action": "inbound",
            "count": len(results),
            "output": results,
        }
