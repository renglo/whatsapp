import { useEffect } from "react";
import WhatsappChannels from "@extensions/whatsapp/ui/pages/channels";
import WhatsappSettings from "@extensions/whatsapp/ui/pages/settings";
import WhatsappConversations from "@extensions/whatsapp/ui/pages/conversations";

interface Portfolio {
  name: string;
  portfolio_id: string;
  orgs: Record<string, Org>;
  tools: Record<string, Tool>;
}

interface Org {
  name: string;
  org_id: string;
  tools: string[];
}

interface Tool {
  name: string;
  handle: string;
}

export default function Whatsapp({
  portfolio,
  org,
  tool,
  section,
  tree,
  onNavigate,
}: {
  portfolio: string;
  org: string;
  tool: string;
  section?: string;
  tree?: { portfolios: Record<string, Portfolio> };
  onNavigate?: (path: string) => void;
}) {
  useEffect(() => {
    if (!section && onNavigate) {
      onNavigate(`/${portfolio}/${org}/${tool}/channels`);
    }
  }, [section, portfolio, org, tool, onNavigate]);

  if (!section) {
    return null;
  }

  return (
    <div className="flex min-h-screen w-full flex-col bg-muted/40">
      <div className="flex flex-col sm:gap-2 sm:pl-2">
        {section === "channels" && (
          <WhatsappChannels
            portfolio={portfolio}
            org={org}
            tool={tool}
            tree={tree}
            onNavigate={onNavigate ?? (() => {})}
          />
        )}
        {section === "settings" && (
          <WhatsappSettings
            portfolio={portfolio}
            org={org}
            tool={tool}
            tree={tree}
            onNavigate={onNavigate ?? (() => {})}
          />
        )}
        {section === "conversations" && (
          <WhatsappConversations portfolio={portfolio} org={org} tool={tool} />
        )}
      </div>
    </div>
  );
}
