import { formatDistanceToNow } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
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

  const stats = job.stats ? parseSummary(job.stats) : null;

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

      {stats && (stats.downloaded > 0 || stats.transcribed > 0 || stats.errors > 0) && (
        <div className="mt-1.5 flex items-center gap-3 text-xs">
          {stats.downloaded > 0 && (
            <span className="text-muted-foreground">
              {stats.downloaded} downloaded
            </span>
          )}
          {stats.transcribed > 0 && (
            <span className="text-muted-foreground">
              {stats.transcribed} transcribed
            </span>
          )}
          {stats.errors > 0 && (
            <span className="text-destructive">
              {stats.errors} errors
            </span>
          )}
        </div>
      )}
    </Card>
  );
}

function parseSummary(
  stats: Record<string, number>
): { downloaded: number; transcribed: number; errors: number } {
  return {
    downloaded: stats.recordings_downloaded ?? 0,
    transcribed: stats.recordings_transcribed ?? 0,
    errors: stats.recordings_failed ?? 0,
  };
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
