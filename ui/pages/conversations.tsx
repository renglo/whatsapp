import ChatInspect from "@extensions/data/ui/pages/chat_inspect";
import { getCurrentUserId } from "@extensions/data/ui/lib/current-user-id";

interface AgentProps {
  portfolio: string;
  org: string;
  tool: string;
}

/** Portfolio-scoped WhatsApp sessions live at org ``_all``. */
const SESSION_ORG = "_all";

export default function WhatsappConversations({ portfolio, tool }: AgentProps) {
  const userId = getCurrentUserId();

  if (!userId) {
    return (
      <div className="mx-auto max-w-2xl p-6 text-sm text-muted-foreground">
        Could not resolve your user id — sign in again or reload the console home page.
      </div>
    );
  }

  return (
    <ChatInspect
      portfolio={portfolio}
      org={SESSION_ORG}
      tool={tool}
      readOnly
      title="WhatsApp conversations"
      description={`Renglo threads for whatsapp-user / ${userId}. Newest thread is the active lane; create a new thread after compaction to reset context.`}
      fixedEntityType="whatsapp-user"
      fixedEntityId={userId}
      threadSource="session_threads"
      apiSegment="_session"
    />
  );
}
