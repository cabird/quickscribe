import { formatDistanceToNow } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { parseRunStats, summarizeRunStats } from "@/lib/jobs";
import { cn } from "@/lib/utils";
import type { SyncRunSummary, SyncRunType } from "@/types/models";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  completed: "default",
  running: "secondary",
  failed: "destructive",
};

const TRIGGER_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  scheduled: "outline",
  manual: "secondary",
};

const TYPE_LABELS: Record<SyncRunType, string> = {
  plaud_sync: "Sync",
  speaker_id: "Speaker ID",
  profile_rebuild: "Rebuild",
  transcription_poll: "Poll",
};

const TYPE_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  plaud_sync: "outline",
  speaker_id: "secondary",
  profile_rebuild: "secondary",
  transcription_poll: "outline",
};

interface JobCardProps {
  job: SyncRunSummary;
  isSelected?: boolean;
  onClick?: () => void;
}

export function JobCard({ job, isSelected, onClick }: JobCardProps) {
  const startDate = new Date(job.started_at);
  const duration = job.finished_at
    ? formatDurationMs(new Date(job.finished_at).getTime() - startDate.getTime())
    : "running...";

  const stats = parseRunStats(job.stats_json);
  const statParts = stats && job.type ? summarizeRunStats(job.type, stats) : [];

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
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs text-muted-foreground">
          {job.id.slice(0, 8)}
        </span>
        <div className="flex items-center gap-1.5">
          {job.type && (
            <Badge variant={TYPE_VARIANT[job.type] ?? "outline"} className="text-[10px]">
              {TYPE_LABELS[job.type] ?? job.type}
            </Badge>
          )}
          <Badge variant={TRIGGER_VARIANT[job.trigger] ?? "outline"} className="text-[10px]">
            {job.trigger}
          </Badge>
          <Badge variant={STATUS_VARIANT[job.status] ?? "secondary"} className="text-[10px]">
            {job.status}
          </Badge>
        </div>
      </div>

      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
        <span>{formatDistanceToNow(startDate, { addSuffix: true })}</span>
        <span aria-hidden="true">·</span>
        <span>{duration}</span>
      </div>

      {statParts.length > 0 && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs">
          {statParts.map((part) => (
            <span
              key={part.label}
              className={cn(
                "text-muted-foreground",
                part.tone === "success" && "text-emerald-600 dark:text-emerald-400",
                part.tone === "destructive" && "text-destructive"
              )}
            >
              {part.label}
            </span>
          ))}
        </div>
      )}
    </Card>
  );
}

function formatDurationMs(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}
