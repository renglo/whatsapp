# WhatsApp extension

Meta Cloud API channel for Renglo: inbound webhooks, LINK deep-link user binding, and Graph outbound send. Each org owns its own `whatsapp_config`.

The installable Python distribution is **`renglo-whatsapp`** (import package `whatsapp`) under `package/`.

## Why a thin edge Lambda?

Meta (and BSPs) retry when the webhook is slow. The main Flask API Lambda can cold-start past that budget. Renglo keeps a **platform-native webhook edge** (Stack B) that:

1. Answers Meta’s GET verify handshake
2. On POST, enqueues EventBridge and returns **200** immediately
3. Lets universal ingress ACK quickly and run `whatsapp/inbound` off the hot path when async workers are available

## Architecture

```
Meta → HTTP API → platform webhook edge → 200
                     └─ EventBridge (~5s client timeout) → POST /_schd/ingress → **202 Accepted**
                              └─ async worker (Lambda Event self-invoke, peer ECS, or local thread)
                                   └─ whatsapp/inbound → agent → Graph reply when ready
                                                   ├─ HMAC + envelope/message dedup
                                                   ├─ LINK consume / identity bind
                                                   └─ agent_handler (e.g. dumbo/generic_agent)
                                                          └─ Graph send reply
```

### Duplicate forensics (Meta vs EventBridge)

We have **not** pinned your production duplicates to Meta or EventBridge yet — that requires correlating IDs on real traffic. Each processed user turn stores trace fields on the session `user_message` (visible in **WhatsApp conversations**):

| Field | Meaning |
|-------|---------|
| `whatsapp_inbound_message_id` | Meta `messages[].id` (wamid). Same wamid → same user text from Meta’s perspective. |
| `eventbridge_event_id` | EventBridge event `id` on the HTTP POST to `/_schd/ingress`. **Stable across EventBridge retries** of the same bus event. |
| `webhook_edge_receipt_id` | New UUID per Meta POST accepted at the webhook edge. **New Meta delivery → new receipt**, even if the body is identical. |
| `ingress_http_request_id` | API Gateway / load-balancer request id for that ingress HTTP call. **Changes on each EventBridge delivery attempt**. |
| `webhook_envelope_sha256` | SHA-256 of the raw webhook JSON (dedup key). |

How to read duplicates:

- **Same wamid + same `eventbridge_event_id` + different `ingress_http_request_id`** → EventBridge redelivered the same bus event (ingress slow/error/timeout).
- **Same wamid + different `eventbridge_event_id` or `webhook_edge_receipt_id`** → Meta (or the edge) produced **multiple** bus events for the same message.
- **Same wamid, first row only in UI** → later copies were deduped; check API logs for `duplicate` / `duplicate_envelope` lines (they include the same trace fields).

Dedup and async ingress (below) are **mitigations** suggested by architecture; use the table above to confirm the source in your environment.

### Retries and load (mitigations)

| Layer | Behavior |
|-------|----------|
| **Envelope dedup** | After HMAC, claims `webhook_envelope_sha256` in `channel_inbound_dedup`. |
| **Message dedup** | Claims Meta `messages[].id`. |
| **Async ingress** | `/_schd/ingress` returns **202** and runs handlers in a background worker (Lambda async self-invoke on API Lambda, or peer ECS when configured). EventBridge stops retrying; the agent can use the full Lambda timeout. Sync fallback only if async start fails. |
| **EventBridge cap** | Stack B target retry limit (when deployed). |

Webhook URL (org from the path — see [Tenancy](#tenancy-portfolio-org--identity)):

```
{WEBHOOK_EDGE_BASE_URL}/{portfolio}/{org}/whatsapp
```

(`WEBHOOK_EDGE_BASE_URL` comes from Stack B after deploy / `write-local-config`.)

## Tenancy (portfolio, org, identity)

Each org has its own WhatsApp number. Config, link codes, identities, dedup, and the agent all use the org in the path. There is no portfolio-wide bucket. An org whose id is `_all` is that org only.

### WhatsApp number and credentials — per org

`whatsapp_config` is stored at `(portfolio, org)`. Assign the tool to the org (that runs `initialize_extension`) before filling Config. Point Meta at that org:

```
{WEBHOOK_EDGE_BASE_URL}/{portfolio}/{org}/whatsapp
```

### User linking — this org

`channel_identities`, `channel_link_codes`, and `channel_inbound_dedup` live on the same org.

After Connect WhatsApp:

- A phone (`wa_id`) binds to **one Renglo `user_id`** for that org
- A link on one org does not apply to another org
- It is **not** a shared inbox — each number belongs to one user (no-steal; replace-on-link for the same user)

Unlinked senders never reach the agent (they get a “connect in console” nag, or complete LINK binding).

### Org context for the agent

Inbound passes the webhook path `org` into `agent_handler`. The message text is not used to pick an org.

## Install

### 1. Python package

```bash
cd extensions/whatsapp/package
pip install -e .
```

### 2. Blueprints

```bash
python installer/upload_blueprints.py <env> --aws-profile <profile> --aws-region <region>
```

### 3. Local webhook edge + ngrok (development)

To send Meta webhooks to your **local** API (no cloud backend deploy), use [`dev/webhook`](../../dev/webhook/README.md):

```bash
# Terminal A: local API on :5001 (RENGLO_INGRESS_SECRET in env_config.py)
# Terminal B:
cd dev/webhook && ./setup_venv.sh   # once
source run.sh                       # loads secret from env_config.py
# Optional: OPEN_NGROK=1 source run.sh
# Terminal C (if not using OPEN_NGROK):
ngrok http 5055
```

Meta callback: `https://<ngrok>/<portfolio>/<org>/whatsapp`

### 4. Platform webhook edge (cloud)

Deployed with **Stack B** (`WebhookIngress`). After deploy / `write-local-config`:

| Output / config | Purpose |
|-----------------|---------|
| `WEBHOOK_EDGE_BASE_URL` | Public Meta webhook base |
| `RENGLO_INGRESS_SECRET` | Shared EventBridge → API secret (`X-Renglo-Ingress-Secret`) |
| `{BASE_URL}/_schd/ingress` | Universal API entry for webhook events |

Point Meta at:

```
{WEBHOOK_EDGE_BASE_URL}/<portfolio_id>/<org_id>/whatsapp
```

Set `RENGLO_INGRESS_SECRET` on the API (see `env_config.py.TEMPLATE`). See [`ops/launcher/cdk/assets/webhook_edge/README.md`](../../ops/launcher/cdk/assets/webhook_edge/README.md) for stack testing.

### 5. Console

Add `whatsapp` to `VITE_EXTENSIONS`, then **Install** from the marketplace card (`whatsapp/whatsapp_onboardings`).

### 6. Meta credentials

Open the WhatsApp tool → **Config** and fill `whatsapp_config`:

| Field | Purpose |
|--------|---------|
| `phone_number_id` | Graph send node |
| `access_token` | Bearer token |
| `app_secret` | `X-Hub-Signature-256` verification |
| `verify_token` | GET `hub.verify_token` handshake |
| `display_phone_e164` | Fallback E.164 for `wa.me` links; **mint_link** reads the live number from Meta Graph when `access_token` + `phone_number_id` are set |
| `api_version` | Default `v22.0` |
| `agent_handler` | e.g. `dumbo/generic_agent` |
| `webhook_enabled` | `true` / `false` |

Subscribe to `messages`. Use the same verify token as in config.

## User linking (Connect WhatsApp)

Links belong to the org you are in (see [Tenancy](#tenancy-portfolio-org--identity)). The phone maps to your user for that org's number.

1. Signed-in user opens **Link** → **Open WhatsApp**
2. Console mints a high-entropy `LINK-<20>` (hashed at rest, 10 min TTL)
3. `wa.me/<digits>?text=…LINK-…` opens with a prefilled message (+ QR for laptop→phone)
4. User taps Send → inbound consumes the code → binds `wa_id` → Renglo `user_id`
5. Dashboard polls until **Connected ✓**

### Meta test numbers (`+1 555 …`)

Meta’s free sandbox numbers (e.g. `+1 555 676 3551`) **cannot** be opened via public [wa.me](https://wa.me) / click-to-chat links — WhatsApp will report “isn’t on WhatsApp” even when the URL is correct. They only exchange messages with phone numbers listed as **test recipients** in the [Meta App Dashboard](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started) (WhatsApp → API Setup).

For test numbers, the Connect UI shows manual steps:

1. Add your personal phone as a test recipient in Meta.
2. In WhatsApp on your phone, start a **new chat** and type `+1 555 676 3551` manually (do not use wa.me).
3. Send the prefilled `LINK-…` message.

For real customer linking, register a **real business phone number** in Meta (not a 555 test number).

Rules (from cos-demo): no silent auto-link, no-steal, replace-on-link, single-use codes.

Before any agent reply: Meta HMAC must verify, and the sender must already be linked (or be completing LINK).

## Handlers

| Handler | Auth | Role |
|---------|------|------|
| `whatsapp_onboardings` | Cognito `/_schd/run` | Install tool + schd_tools + config |
| `mint_link` | Cognito `/call` | Mint LINK + deep link |
| `identities` | Cognito `/call` | List / unlink |
| `inbound` | EventBridge → `/_schd/ingress` | Verify, dedup on Meta `messages[].id`, link gate, agent dispatch |
| `post_message` | Cognito / internal | Graph text send |

## Blueprints

| Ring | Purpose |
|------|---------|
| `whatsapp_config` | Singleton Meta credentials + agent routing |
| `channel_identities` | `whatsapp` + `external_id` → `user_id` |
| `channel_link_codes` | Hashed LINK tokens |
| `channel_inbound_dedup` | Seen Meta inbound message ids (~7d TTL metadata) |

## Package layout

```
extensions/whatsapp/
├── README.md
├── blueprints/
├── installer/          # upload_blueprints.py
├── package/            # renglo-whatsapp
└── ui/                 # console channels + settings
```

## License

MIT — see `LICENSE.txt` if present.
