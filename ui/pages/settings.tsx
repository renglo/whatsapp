import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface AgentProps {
  portfolio: string;
  org: string;
  tool: string;
  tree?: { portfolios: Record<string, unknown> };
  onNavigate: (path: string) => void;
}

const SINGLETON_ID = "00000000-0000-0000-0000-000000000000";
const CONFIG_ORG = "_all";

type ConfigForm = {
  phone_number_id: string;
  access_token: string;
  app_secret: string;
  verify_token: string;
  display_phone_e164: string;
  api_version: string;
  agent_handler: string;
  webhook_enabled: string;
};

const EMPTY: ConfigForm = {
  phone_number_id: "",
  access_token: "",
  app_secret: "",
  verify_token: "",
  display_phone_e164: "",
  api_version: "v22.0",
  agent_handler: "dumbo/generic_agent",
  webhook_enabled: "true",
};

export default function WhatsappSettings({ portfolio }: AgentProps) {
  const [form, setForm] = useState<ConfigForm>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apiBase = import.meta.env.VITE_API_URL;
  const path = `${apiBase}/_data/${portfolio}/${CONFIG_ORG}/whatsapp_config/${SINGLETON_ID}`;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(path, {
        headers: { Authorization: `Bearer ${sessionStorage.accessToken}` },
      });
      if (!res.ok) {
        setError("Could not load whatsapp_config — run Install first");
        setForm(EMPTY);
        return;
      }
      const data = await res.json();
      setForm({
        phone_number_id: String(data.phone_number_id || ""),
        access_token: String(data.access_token || ""),
        app_secret: String(data.app_secret || ""),
        verify_token: String(data.verify_token || ""),
        display_phone_e164: String(data.display_phone_e164 || ""),
        api_version: String(data.api_version || "v22.0"),
        agent_handler: String(data.agent_handler || "dumbo/generic_agent"),
        webhook_enabled: String(data.webhook_enabled ?? "true"),
      });
    } catch {
      setError("Could not load whatsapp_config");
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const res = await fetch(path, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${sessionStorage.accessToken}`,
        },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        setError("Save failed");
        return;
      }
      setMessage("Saved");
      await load();
    } catch {
      setError("Save failed");
    } finally {
      setSaving(false);
    }
  }

  function field(key: keyof ConfigForm, label: string, hint?: string, type = "text") {
    return (
      <div className="space-y-1.5">
        <Label htmlFor={key}>{label}</Label>
        <Input
          id={key}
          type={type}
          value={form[key]}
          onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
        />
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-2xl p-4 sm:p-6">
      <Card>
        <CardHeader>
          <CardTitle>WhatsApp settings</CardTitle>
          <CardDescription>
            Meta Cloud API credentials for this portfolio (stored in{" "}
            <code>whatsapp_config</code> at <code>_all</code>).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}
          {message && <p className="text-sm text-emerald-700">{message}</p>}

          {!loading && (
            <>
              {field("phone_number_id", "Phone number id", "Meta phone_number_id for Graph sends")}
              {field("access_token", "Access token", "System User / permanent token", "password")}
              {field("app_secret", "App secret", "Used for X-Hub-Signature-256", "password")}
              {field("verify_token", "Webhook verify token", "Must match Meta webhook GET hub.verify_token")}
              {field(
                "display_phone_e164",
                "Display phone (E.164)",
                "Fallback for wa.me links if Meta lookup fails — use full E.164 (e.g. +15551234567)",
              )}
              {field("api_version", "API version", "e.g. v22.0")}
              {field(
                "agent_handler",
                "Agent handler",
                "extension/handler for linked messages (default dumbo/generic_agent)",
              )}
              {field("webhook_enabled", "Webhook enabled", "true / false")}

              <Button onClick={() => void save()} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
