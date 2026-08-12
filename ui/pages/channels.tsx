import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface AgentProps {
  portfolio: string;
  org: string;
  tool: string;
  tree?: { portfolios: Record<string, unknown> };
  onNavigate: (path: string) => void;
}

type Identity = {
  _id?: string;
  channel?: string;
  external_id?: string;
  display_name?: string;
  linked_at?: string;
  last_seen_at?: string;
};

type MintResult = {
  code: string;
  deepLink: string | null;
  expiresAt: string;
};

function unwrapHandlerOutput(data: unknown): Record<string, unknown> {
  if (!data || typeof data !== "object") return {};
  const root = data as Record<string, unknown>;
  // /call wraps as { success, output: handlerResult } or SchdLoader shape
  const output = root.output;
  if (output && typeof output === "object") {
    const inner = output as Record<string, unknown>;
    if (inner.output && typeof inner.output === "object" && ("code" in (inner.output as object) || "deepLink" in (inner.output as object) || "items" in (inner.output as object))) {
      return inner.output as Record<string, unknown>;
    }
    if ("code" in inner || "deepLink" in inner || "items" in inner || "success" in inner) {
      return inner;
    }
  }
  return root;
}

export default function WhatsappChannels({ portfolio, org, tool }: AgentProps) {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [loading, setLoading] = useState(true);
  const [minting, setMinting] = useState(false);
  const [mint, setMint] = useState<MintResult | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState<string | null>(null);
  const baselineRef = useRef<Set<string>>(new Set());

  const apiBase = import.meta.env.VITE_API_URL;
  const authHeaders = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${sessionStorage.accessToken}`,
  };

  const loadIdentities = useCallback(async () => {
    try {
      const res = await fetch(
        `${apiBase}/_schd/${portfolio}/${org}/call/whatsapp/identities`,
        {
          method: "POST",
          headers: authHeaders,
          body: JSON.stringify({ action: "list", portfolio }),
        },
      );
      if (!res.ok) {
        setError("Could not load linked identities");
        return [];
      }
      const data = await res.json();
      const unwrapped = unwrapHandlerOutput(data);
      const items = (unwrapped.items as Identity[]) || (unwrapped.output as Identity[]) || [];
      const list = Array.isArray(items) ? items : [];
      setIdentities(list);
      return list;
    } catch {
      setError("Could not load linked identities");
      return [];
    } finally {
      setLoading(false);
    }
  }, [apiBase, portfolio, org]);

  useEffect(() => {
    void loadIdentities();
  }, [loadIdentities]);

  useEffect(() => {
    if (!mint) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [mint]);

  useEffect(() => {
    if (!mint) return;
    let stopped = false;
    const poll = async () => {
      const list = await loadIdentities();
      const linked = list.some(
        (i) => i.channel === "whatsapp" && !baselineRef.current.has(String(i.external_id || "")),
      );
      if (linked && !stopped) {
        setMint(null);
      }
    };
    const iv = setInterval(() => {
      void poll();
    }, 2500);
    return () => {
      stopped = true;
      clearInterval(iv);
    };
  }, [mint, loadIdentities]);

  useEffect(() => {
    if (mint && Date.parse(mint.expiresAt) <= now) {
      setMint(null);
    }
  }, [mint, now]);

  async function connect() {
    setMinting(true);
    setError(null);
    setMint(null);
    baselineRef.current = new Set(
      identities.map((i) => String(i.external_id || "")).filter(Boolean),
    );
    const appWindow = typeof window !== "undefined" ? window.open("about:blank", "_blank") : null;
    if (appWindow) appWindow.opener = null;

    try {
      const res = await fetch(`${apiBase}/_schd/${portfolio}/${org}/call/whatsapp/mint_link`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ portfolio }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError("Failed to mint link code");
        appWindow?.close();
        return;
      }
      const unwrapped = unwrapHandlerOutput(data);
      const code = String(unwrapped.code || "");
      const deepLink = (unwrapped.deepLink as string | null) || null;
      const expiresAt = String(unwrapped.expiresAt || unwrapped.expires_at_iso || "");
      if (!code || !expiresAt) {
        setError("Mint response incomplete — check WhatsApp settings (display phone)");
        appWindow?.close();
        return;
      }
      setMint({ code, deepLink, expiresAt });
      if (deepLink && appWindow) {
        appWindow.location.href = deepLink;
      } else {
        appWindow?.close();
      }
    } catch {
      setError("Failed to mint link code");
      appWindow?.close();
    } finally {
      setMinting(false);
    }
  }

  async function unlink(externalId?: string) {
    await fetch(`${apiBase}/_schd/${portfolio}/${org}/call/whatsapp/identities`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ action: "unlink", portfolio, external_id: externalId }),
    });
    await loadIdentities();
  }

  const secondsLeft = mint
    ? Math.max(0, Math.floor((Date.parse(mint.expiresAt) - now) / 1000))
    : 0;
  const qrUrl = mint?.deepLink
    ? `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(mint.deepLink)}`
    : null;

  return (
    <div className="mx-auto w-full max-w-2xl p-4 sm:p-6">
      <Card>
        <CardHeader>
          <CardTitle>Connect WhatsApp</CardTitle>
          <CardDescription>
            Link your WhatsApp number to your Renglo account with a one-tap deep link. Tool: {tool}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}

          {identities.length > 0 ? (
            <div className="space-y-3">
              <p className="text-sm font-medium text-emerald-700">Connected ✓</p>
              {identities.map((identity) => (
                <div
                  key={identity._id || identity.external_id}
                  className="flex items-center justify-between rounded-md border border-border px-3 py-2"
                >
                  <div>
                    <div className="text-sm font-medium">
                      {identity.display_name || identity.external_id}
                    </div>
                    <div className="text-xs text-muted-foreground">{identity.external_id}</div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void unlink(identity.external_id)}
                  >
                    Unlink
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No WhatsApp number linked yet.</p>
          )}

          {!mint ? (
            <Button onClick={() => void connect()} disabled={minting}>
              {minting ? "Preparing…" : identities.length ? "Switch number" : "Open WhatsApp"}
            </Button>
          ) : (
            <div className="space-y-4 rounded-md border border-border p-4">
              <p className="text-sm">
                Waiting for your message… expires in {secondsLeft}s
              </p>
              {mint.deepLink && (
                <a
                  href={mint.deepLink}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-emerald-700 underline"
                >
                  Open WhatsApp again
                </a>
              )}
              {qrUrl && (
                <div>
                  <p className="mb-2 text-xs text-muted-foreground">
                    Scan with your phone if the dashboard is on a laptop:
                  </p>
                  <img src={qrUrl} alt="WhatsApp link QR" width={240} height={240} />
                </div>
              )}
              <p className="break-all font-mono text-xs text-muted-foreground">{mint.code}</p>
              <Button variant="ghost" size="sm" onClick={() => setMint(null)}>
                Cancel
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
