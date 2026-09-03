# WhatsApp extension

Meta Cloud API channel for Renglo: inbound webhooks, LINK deep-link user binding, and Graph outbound send. Each portfolio owns its own `whatsapp_config` secrets.

The installable Python distribution is **`renglo-whatsapp`** (import package `whatsapp`) under `package/`.

## Why a thin edge Lambda?

Meta (and BSPs) retry when the webhook is slow. The main Flask API Lambda can cold-start past that budget. Renglo keeps a **platform-native webhook edge** (Stack B) that:

1. Answers Meta’s GET verify handshake
2. On POST, enqueues EventBridge and returns **200** immediately
3. Lets `whatsapp/inbound` do HMAC verify, LINK consume, and agent work asynchronously via universal ingress

## Architecture

```
Meta → HTTP API → platform webhook edge → 200
                     └─ EventBridge → POST /_schd/ingress → whatsapp/inbound
                                                                        ├─ LINK consume / identity bind
                                                                        └─ agent_handler (e.g. dumbo/generic_agent)
                                                                               └─ Graph send reply
```

Webhook URL (org from the path — see [Tenancy](#tenancy-portfolio-org--identity)):

```
{WEBHOOK_EDGE_BASE_URL}/{portfolio}/{org}/whatsapp
```

(`WEBHOOK_EDGE_BASE_URL` comes from Stack B after deploy / `write-local-config`.)

## Tenancy (portfolio, org, identity)

### WhatsApp number and credentials — per portfolio

`whatsapp_config` is a **portfolio singleton** stored at `(portfolio, _all)`. One Meta phone number / token set serves the whole portfolio. Orgs do **not** each get their own number from this extension.

### User linking — portfolio-wide (not per org)

`channel_identities` and `channel_link_codes` also live at `(portfolio, _all)`.

After Connect WhatsApp:

- A phone (`wa_id`) binds to **one Renglo `user_id`** for that portfolio
- The link is **not** scoped to a single org — it applies portfolio-wide
- It is **not** an org-shared inbox — each number belongs to one user (no-steal; replace-on-link for the same user)

Unlinked senders never reach the agent (they get a “connect in console” nag, or complete LINK binding).

### Org context for the agent — from the Meta webhook path

Meta’s callback URL carries both portfolio and org:

```
https://<WEBHOOK_EDGE_BASE_URL>/{portfolio}/{org}/whatsapp
```

Inbound passes that `org` into `agent_handler`. The message text is **not** used to infer org.

| Meta webhook URL | What the agent receives | Implication |
|------------------|-------------------------|-------------|
| `…/{portfolio}/{realOrgId}/whatsapp` | `org` = that org | Tools run in a concrete org (e.g. “list expenses” for that org). |
| `…/{portfolio}/_all/whatsapp` | `org` = `_all` | No specific org is resolved. The agent/tools must handle portfolio-wide search, ask which org, or otherwise disambiguate. WhatsApp itself will not pick an org. |

**Practical guidance:** point Meta at a real org when channel traffic should always be org-scoped. Use `_all` only if the configured `agent_handler` (and its tools) know how to work without a single org.

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

Links are **portfolio-wide** (see [Tenancy](#tenancy-portfolio-org--identity)): the phone maps to the user everywhere in that portfolio, independent of which org path Meta uses.

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
| `inbound` | EventBridge → `/_schd/ingress` | Verify, link gate, agent dispatch |
| `post_message` | Cognito / internal | Graph text send |

## Blueprints

| Ring | Purpose |
|------|---------|
| `whatsapp_config` | Singleton Meta credentials + agent routing |
| `channel_identities` | `whatsapp` + `external_id` → `user_id` |
| `channel_link_codes` | Hashed LINK tokens |

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
