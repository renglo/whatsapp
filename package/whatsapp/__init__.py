"""WhatsApp (Meta Cloud API) channel extension for Renglo."""

__version__ = "1.0.0"
__all__ = ["get_handler", "list_handlers", "HANDLERS"]


def _get_initialize_extension():
    from whatsapp.handlers.initialize_extension import InitializeExtension

    return InitializeExtension


def _get_whatsapp_onboardings():
    from whatsapp.handlers.whatsapp_onboardings import WhatsappOnboardings

    return WhatsappOnboardings


def _get_mint_link():
    from whatsapp.handlers.mint_link import MintLink

    return MintLink


def _get_inbound():
    from whatsapp.handlers.inbound import Inbound

    return Inbound


def _get_post_message():
    from whatsapp.handlers.post_message import PostMessage

    return PostMessage


def _get_identities():
    from whatsapp.handlers.identities import Identities

    return Identities


HANDLERS = {
    "initialize_extension": _get_initialize_extension,
    "whatsapp_onboardings": _get_whatsapp_onboardings,
    "mint_link": _get_mint_link,
    "inbound": _get_inbound,
    "post_message": _get_post_message,
    "identities": _get_identities,
}


def get_handler(handler_name: str):
    """Get an instantiated handler by name."""
    if handler_name not in HANDLERS:
        available = ", ".join(HANDLERS.keys())
        raise KeyError(
            f"Handler '{handler_name}' not found. Available handlers: {available}"
        )
    return HANDLERS[handler_name]()


def list_handlers():
    """List all available handler names."""
    return list(HANDLERS.keys())
