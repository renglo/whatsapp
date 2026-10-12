import ChatInspect from "@extensions/data/ui/pages/chat_inspect";
import { getCurrentUserId } from "@extensions/data/ui/utils/current-user-id";

interface AgentProps {
  portfolio: string;
  org: string;
  tool: string;
}

export default function WhatsappConversations({ portfolio, org, tool }: AgentProps) {
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
      org={org}
      tool={tool}
      readOnly
      title="WhatsApp conversations"
      description={`Threads for whatsapp-user / ${userId}. Newest thread is the active lane; create a new thread after compaction to reset context.`}
      fixedEntityType="whatsapp-user"
      fixedEntityId={userId}
      threadSource="session_threads"
      apiSegment="_session"
    />
  );
}
