from __future__ import annotations

from typing import Any, Dict, List

from flask import current_app

from renglo.auth.auth_controller import AuthController
from renglo.common import load_config

from ..lib.describe import describe_document


class WhatsappOnboardings:
    """Install the WhatsApp tool on a portfolio. Per-org setup is initialize_extension."""

    def __init__(self) -> None:
        config = load_config()
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

        existing = self.AUC.list_entity("tool", portfolio_id=portfolio)
        items = ((existing or {}).get("document") or {}).get("items") or []
        for item in items:
            if str(item.get("handle") or "") == handle:
                tool_id = item.get("_id")
                self.bridge["tool_id"] = tool_id
                return {
                    "success": True,
                    "action": action,
                    "message": "Tool already installed",
                    "input": kwargs,
                    "output": item,
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

    def describe(self, payload=None):
        return describe_document(
            "whatsapp_onboardings",
            "WhatsApp onboarding",
            "Install the WhatsApp tool on a portfolio. Config and handler catalog are created "
            "per org when the tool is assigned to that org.",
            {},
            output_schema={
                "type": "array",
                "description": "One result object per setup step.",
                "items": {"type": "object"},
            },
        )

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
