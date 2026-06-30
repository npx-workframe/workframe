import { ScrollArea } from "@/components/ui/scroll-area";

export function SiteScrollRoot({ children }: { children: React.ReactNode }) {
  return (
    <ScrollArea
      axis="vertical"
      className="wf-scroll--viewport h-full min-h-0 w-full"
    >
      {children}
    </ScrollArea>
  );
}
