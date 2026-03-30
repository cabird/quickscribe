import { formatDistanceToNow } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Participant } from "@/types/models";

interface ParticipantCardProps {
  participant: Participant;
  isSelected?: boolean;
  onClick?: () => void;
}

export function ParticipantCard({ participant, isSelected, onClick }: ParticipantCardProps) {
  const initials = getInitials(participant.display_name);
  const lastSeen = participant.last_seen
    ? formatDistanceToNow(new Date(participant.last_seen), { addSuffix: true })
    : null;

  return (
    <Card
      className={cn(
        "cursor-pointer px-3 py-2.5 transition-colors hover:bg-accent/50",
        isSelected && "border-l-2 border-l-primary bg-accent"
      )}
      tabIndex={0}
      role="button"
      onClick={onClick}
      onKeyDown={(e: React.KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.();
        }
      }}
    >
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
          {initials}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium">{participant.display_name}</span>
            {participant.is_user && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                Me
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            {participant.organization && (
              <span className="truncate">{participant.organization}</span>
            )}
            {participant.organization && lastSeen && <span aria-hidden="true">·</span>}
            {lastSeen && <span className="shrink-0">{lastSeen}</span>}
          </div>
        </div>
      </div>
    </Card>
  );
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}
