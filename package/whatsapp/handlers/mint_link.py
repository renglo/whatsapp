"""Mint a LINK deep-link token for the authenticated user."""

from __future__ import annotations

from typing import Any, Dict

from renglo.auth.auth_controller import AuthController
from renglo.common import load_config
from renglo.data.data_controller import DataController

from .config import CONFIG_ORG, ConfigStore
from .identity_store import IdentityStore
from .link_token import (
    format_e164_display,
    is_meta_us_test_number,
    link_prefill_message,
    normalize_wa_me_digits,
    whatsapp_deep_link,
)
from .meta_client import fetch_display_phone_digits


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
        phone_source = "config"
        digits = ""
        if cfg.is_send_ready():
            meta_digits = fetch_display_phone_digits(
                access_token=cfg.access_token,
                phone_number_id=cfg.phone_number_id,
                api_version=cfg.api_version,
            )
            if meta_digits:
                digits = meta_digits
                phone_source = "meta"
        if not digits:
            digits = normalize_wa_me_digits(cfg.display_phone_e164)
            phone_source = "config"

        deep_link = whatsapp_deep_link(digits, minted["code"]) if len(digits) >= 8 else None
        prefill = link_prefill_message(minted["code"])
        meta_test = is_meta_us_test_number(digits)
        display_phone = format_e164_display(digits)
        if not deep_link:
            return {
                "success": False,
                "message": (
                    "Could not build WhatsApp deep link — set display_phone_e164 in WhatsApp "
                    "Config or ensure phone_number_id + access_token can read the number from Meta."
                ),
                "phone_digits": digits or None,
                "phone_source": phone_source,
            }

        return {
            "success": True,
            "action": "mint_link",
            "code": minted["code"],
            "expiresAt": minted["expires_at_iso"],
            "expires_at": minted["expires_at"],
            "deepLink": deep_link,
            "phone_digits": digits,
            "phone_source": phone_source,
            "display_phone_e164": display_phone or cfg.display_phone_e164,
            "prefillMessage": prefill,
            "isMetaTestNumber": meta_test,
            "output": {
                "code": minted["code"],
                "expiresAt": minted["expires_at_iso"],
                "deepLink": deep_link,
                "phone_digits": digits,
                "phone_source": phone_source,
                "display_phone_e164": display_phone or cfg.display_phone_e164,
                "prefillMessage": prefill,
                "isMetaTestNumber": meta_test,
            },
        }
