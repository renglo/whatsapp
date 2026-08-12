from __future__ import annotations

from typing import Any, Dict, List

from flask import current_app

from renglo.auth.auth_controller import AuthController
from renglo.common import load_config
from renglo.data.data_controller import DataController

from .config import ConfigStore


class WhatsappOnboardings:
    """Install WhatsApp tool, schd entries, and singleton config."""

    def __init__(self) -> None:
        config = load_config()
        self.DAC = DataController(config=config)
        self.AUC = AuthController(config=config)
        self.bridge: Dict[str, Any] = {}

    def create_tool(self, portfolio: str, tool: str, handle: str) -> Dict[str, Any]:
        action = "create_tool"
        current_app.logger.debug("Installing WhatsApp tool in portfolio")

        kwargs = {
            "name": tool,
            "handle": handle,
            "portfolio_id": portfolio,
        }
        response = self.AUC.create_entity("tool", **kwargs)
        self.bridge["tool_id"] = response.get("document", {}).get("_id")

        if not response.get("success"):
            return {
                "success": False,
                "action": action,
                "message": "Could not install tool",
                "input": kwargs,
                "output": response,
            }
        return {
            "success": True,
            "action": action,
            "message": "Tool installed",
            "input": kwargs,
            "output": response,
        }

    def create_schd_tool_doc(self, portfolio: str, org: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        action = "create_schd_tool_doc"
        response, _status = self.DAC.post_a_b(portfolio, org, "schd_tools", doc)
        if not response.get("success"):
            return {
                "success": False,
                "action": action,
                "message": "Could not register schd tool",
                "input": doc,
                "output": response,
            }
        return {
            "success": True,
            "action": action,
            "message": "Scheduler tool registered",
            "input": doc,
            "output": response,
        }

    def refresh_tree(self) -> Dict[str, Any]:
        action = "refresh_tree"
        response = self.AUC.refresh_tree()
        if not response.get("success"):
            return {
                "success": False,
                "action": action,
                "message": "Tree could not be generated",
                "input": [],
                "output": response,
            }
        return {
            "success": True,
            "action": action,
            "message": "The tree has been generated",
            "input": [],
            "output": response,
        }

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []

        existing_portfolio = None
        if "portfolio" in payload and payload["portfolio"] != "":
            existing_portfolio = str(payload["portfolio"])

        if not existing_portfolio:
            return {"success": False, "output": "No portfolio selected"}

        response_tool = self.create_tool(existing_portfolio, "WhatsApp", "whatsapp")
        results.append(response_tool)
        if not response_tool["success"]:
            return {"success": False, "output": results}

        for doc in (
            {
                "key": "whatsapp_inbound",
                "name": "WhatsApp Inbound",
                "goal": "Process Meta WhatsApp webhook events (link gate + agent dispatch)",
                "handler": "whatsapp/inbound",
                "init": "_",
                "instructions": "Called asynchronously from the edge Lambda via EventBridge.",
                "input": '{"raw_body":"...","signature_header":"sha256=..."}',
                "output": "_",
            },
            {
                "key": "whatsapp_post_message",
                "name": "WhatsApp Post Message",
                "goal": "Send a WhatsApp text message via Meta Graph API",
                "handler": "whatsapp/post_message",
                "init": "_",
                "instructions": "Requires whatsapp_config access_token and phone_number_id.",
                "input": '{"target":"wa_id","message":"text"}',
                "output": "_",
            },
            {
                "key": "whatsapp_mint_link",
                "name": "WhatsApp Mint Link",
                "goal": "Mint a LINK token + wa.me deep link for the current user",
                "handler": "whatsapp/mint_link",
                "init": "_",
                "instructions": "Authenticated console Connect WhatsApp flow.",
                "input": "{}",
                "output": "_",
            },
        ):
            response_schd = self.create_schd_tool_doc(existing_portfolio, "_all", doc)
            results.append(response_schd)
            if not response_schd["success"]:
                return {"success": False, "output": results}

        cfg = ConfigStore(self.DAC, existing_portfolio, "_all").ensure_defaults()
        results.append(cfg)
        if not cfg.get("success"):
            return {"success": False, "output": results}

        response_tree = self.refresh_tree()
        results.append(response_tree)
        if not response_tree["success"]:
            return {"success": False, "output": results}

        return {
            "success": True,
            "message": "run completed",
            "input": payload,
            "output": results,
        }
