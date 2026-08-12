"""Mint a LINK deep-link token for the authenticated user."""

from __future__ import annotations

from typing import Any, Dict

from renglo.auth.auth_controller import AuthController
from renglo.common import load_config
from renglo.data.data_controller import DataController

from .config import CONFIG_ORG, ConfigStore
from .identity_store import IdentityStore
from .link_token import digits_only, whatsapp_deep_link


class MintLink:
    def __init__(self) -> None:
        config = load_config()
        self.DAC = DataController(config=config)
        self.AUC = AuthController(config=config)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        portfolio = str(payload.get("portfolio") or "")
        if not portfolio:
            return {"success": False, "message": "portfolio required"}

        user_id = self.AUC.get_current_user()
        if not user_id:
            return {"success": False, "message": "Authentication required", "status": 401}

        store = IdentityStore(self.DAC, portfolio, CONFIG_ORG)
        minted = store.mint_link_code(user_id)
        if not minted.get("success"):
            return minted

        cfg = ConfigStore(self.DAC, portfolio, CONFIG_ORG).load()
        digits = digits_only(cfg.display_phone_e164)
        deep_link = whatsapp_deep_link(digits, minted["code"]) if len(digits) >= 8 else None

        return {
            "success": True,
            "action": "mint_link",
            "code": minted["code"],
            "expiresAt": minted["expires_at_iso"],
            "expires_at": minted["expires_at"],
            "deepLink": deep_link,
            "display_phone_e164": cfg.display_phone_e164,
            "output": {
                "code": minted["code"],
                "expiresAt": minted["expires_at_iso"],
                "deepLink": deep_link,
            },
        }
