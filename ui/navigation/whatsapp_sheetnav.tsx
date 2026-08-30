import { EllipsisVertical, Link2, MessageSquare, Settings } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { wlLogoUrl } from "@/lib/branding";

interface ToolMenuProps {
  portfolio: string;
  org: string;
  tool?: string;
  section?: string;
  onNavigate: (path: string) => void;
}

export default function WhatsappSheetNav({
  portfolio,
  org,
  tool,
  onNavigate,
}: ToolMenuProps) {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button size="icon" variant="outline" className="sm:hidden">
          <EllipsisVertical className="h-5 w-5" />
          <span className="sr-only">Toggle Menu</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="sm:max-w-xs">
        <nav className="grid gap-6 text-lg font-medium">
          <button
            onClick={() => {
              setOpen(false);
              onNavigate("/home");
            }}
            className="group flex h-11 w-11 shrink-0 items-center justify-center gap-2 md:h-8 md:w-8 md:text-base"
          >
            <img
              src={wlLogoUrl()}
              className="ml-auto h-12 w-12"
              alt="Logo"
            />
            <span className="sr-only">Logo</span>
          </button>

          <button
            onClick={() => {
              setOpen(false);
              onNavigate(`/${portfolio}/${org}/${tool}/channels`);
            }}
            className="flex items-center gap-4 px-2.5 text-muted-foreground hover:text-foreground"
          >
            <Link2 color="#059669" className="h-5 w-5" />
            Connect WhatsApp
          </button>

          <button
            onClick={() => {
              setOpen(false);
              onNavigate(`/${portfolio}/${org}/${tool}/conversations`);
            }}
            className="flex items-center gap-4 px-2.5 text-muted-foreground hover:text-foreground"
          >
            <MessageSquare color="#059669" className="h-5 w-5" />
            Chats
          </button>

          <button
            onClick={() => {
              setOpen(false);
              onNavigate(`/${portfolio}/${org}/${tool}/settings`);
            }}
            className="flex items-center gap-4 px-2.5 text-muted-foreground hover:text-foreground"
          >
            <Settings color="#059669" className="h-5 w-5" />
            Settings
          </button>
        </nav>
      </SheetContent>
    </Sheet>
  );
}
