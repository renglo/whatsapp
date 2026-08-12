import { Link2, MessageSquare, Settings } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ToolMenuProps {
  portfolio: string;
  org: string;
  tool?: string;
  section?: string;
  onNavigate: (path: string) => void;
}

export default function WhatsappSideNav({
  portfolio,
  org,
  tool,
  section,
  onNavigate,
}: ToolMenuProps) {
  return (
    <nav
      className={
        !org || org === "settings"
          ? "hidden"
          : "flex flex-col items-center gap-1 px-1 sm:py-4"
      }
    >
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex flex-col items-center">
              <button
                onClick={() => onNavigate(`/${portfolio}/${org}/${tool}/channels`)}
                className={
                  section === "channels"
                    ? "group flex h-9 w-9 shrink-0 items-center justify-center gap-2 rounded-full bg-gray-200 text-lg font-semibold text-muted-foreground md:h-12 md:w-12 md:text-base"
                    : "flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:text-foreground md:h-8 md:w-8"
                }
              >
                <Link2 className="h-5 w-5" color="#059669" />
                <span className="sr-only">Channels</span>
              </button>
              <span className="text-xxs">Link</span>
            </div>
          </TooltipTrigger>
          <TooltipContent side="right">Connect WhatsApp</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex flex-col items-center">
              <button
                onClick={() => onNavigate(`/${portfolio}/${org}/${tool}/conversations`)}
                className={
                  section === "conversations"
                    ? "group flex h-9 w-9 shrink-0 items-center justify-center gap-2 rounded-full bg-gray-200 text-lg font-semibold text-muted-foreground md:h-12 md:w-12 md:text-base"
                    : "flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:text-foreground md:h-8 md:w-8"
                }
              >
                <MessageSquare className="h-5 w-5" color="#059669" />
                <span className="sr-only">Chats</span>
              </button>
              <span className="text-xxs">Chats</span>
            </div>
          </TooltipTrigger>
          <TooltipContent side="right">Your WhatsApp agent session</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex flex-col items-center">
              <button
                onClick={() => onNavigate(`/${portfolio}/${org}/${tool}/settings`)}
                className={
                  section === "settings"
                    ? "group flex h-9 w-9 shrink-0 items-center justify-center gap-2 rounded-full bg-gray-200 text-lg font-semibold text-muted-foreground md:h-12 md:w-12 md:text-base"
                    : "flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:text-foreground md:h-8 md:w-8"
                }
              >
                <Settings className="h-5 w-5" color="#059669" />
                <span className="sr-only">Settings</span>
              </button>
              <span className="text-xxs">Config</span>
            </div>
          </TooltipTrigger>
          <TooltipContent side="right">WhatsApp Meta credentials</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </nav>
  );
}
