# WhatsApp extension — specs

## Provider

Meta WhatsApp Cloud API only (v1). No Twilio / Gupshup in this package.

## Identity

User-linked via dashboard-minted `LINK-<20>` tokens (cos-demo semantics):

- SHA-256 at rest, 10 minute TTL, single-use
- No silent auto-link
- No-steal if `wa_id` already bound to another user
- Replace-on-link for the same user

## Ingress

Platform webhook edge (Stack B) ACKs Meta; EventBridge delivers to `POST /_schd/ingress` (`type=webhook`, `channel=whatsapp`), which runs `whatsapp/inbound` without Cognito. Inbound verifies `X-Hub-Signature-256` with the org’s `app_secret`.

## Agent routing

After link, messages go to `whatsapp_config.agent_handler` (default `dumbo/generic_agent`). The extension does not embed Dumbo.
