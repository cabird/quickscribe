import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RunLogEntry } from "@/types/models";

const LEVEL_COLORS: Record<string, string> = {
  debug: "text-blue-500",
  info: "text-muted-foreground",
  warning: "text-amber-500",
  warn: "text-amber-500",
  error: "text-red-500",
  critical: "text-red-600 font-semibold",
};

interface LogViewerProps {
  logs: RunLogEntry[];
  isLive?: boolean;
  className?: string;
}

export function LogViewer({ logs, isLive, className }: LogViewerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);

  const handleCopy = useCallback(() => {
    const text = logs
      .map((l) => `${formatTimestamp(l.timestamp)} [${l.level.toUpperCase()}] ${l.message}`)
      .join("\n");
    navigator.clipboard.writeText(text).catch(() => {});
  }, [logs]);

  // Auto-scroll to bottom when new logs arrive (unless user scrolled up)
  useEffect(() => {
    if (!userScrolledUp && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs.length, userScrolledUp]);

  // Detect if user has scrolled up from the bottom
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setUserScrolledUp(!atBottom);
  }, []);

  if (logs.length === 0 && !isLive) {
    return (
      <div className={cn("flex items-center justify-center py-8 text-sm text-muted-foreground", className)}>
        No log entries
      </div>
    );
  }

  return (
    <div className={cn("flex h-full flex-col overflow-hidden", className)}>
      <div className="flex shrink-0 items-center justify-between border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">
            {logs.length} log entries
          </span>
          {isLive && (
            <span className="flex items-center gap-1.5 text-xs text-green-600">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
              </span>
              Streaming...
            </span>
          )}
        </div>
        <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs" onClick={handleCopy}>
          <Copy className="h-3 w-3" />
          Copy
        </Button>
      </div>

      <div
        ref={containerRef}
        className="min-h-0 flex-1 overflow-y-auto p-2 font-mono text-xs leading-5"
        onScroll={handleScroll}
      >
          {logs.length === 0 && isLive && (
            <div className="py-4 text-center text-xs text-muted-foreground">
              Waiting for log entries...
            </div>
          )}
          {logs.map((entry) => (
            <div key={entry.id} className="flex gap-2 px-1 hover:bg-accent/30">
              <span className="shrink-0 text-muted-foreground/60">
                {formatTimestamp(entry.timestamp)}
              </span>
              <span
                className={cn(
                  "w-[52px] shrink-0 text-right uppercase",
                  LEVEL_COLORS[entry.level.toLowerCase()] ?? "text-muted-foreground"
                )}
              >
                {entry.level}
              </span>
              <span className="min-w-0 break-all">{entry.message}</span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
    </div>
  );
}

function formatTimestamp(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString("en-US", { hour12: false });
  } catch {
    return ts;
  }
}
