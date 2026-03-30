import { format } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Calendar, Clock, Timer, Hash, Users } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RecordingSummary } from "@/types/models";

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  ready: "default",
  pending: "secondary",
  transcoding: "secondary",
  transcribing: "secondary",
  processing: "secondary",
  failed: "destructive",
};

interface RecordingCardProps {
  recording: RecordingSummary;
  isSelected?: boolean;
  isChecked?: boolean;
  showCheckbox?: boolean;
  onClick?: () => void;
  onCheckToggle?: () => void;
}

export function RecordingCard({
  recording,
  isSelected,
  isChecked,
  showCheckbox,
  onClick,
  onCheckToggle,
}: RecordingCardProps) {
  const title = recording.title || recording.original_filename;
  const date = recording.recorded_at
    ? new Date(recording.recorded_at)
    : new Date(recording.created_at);

  const durationFormatted = recording.duration_seconds
    ? formatDuration(recording.duration_seconds)
    : null;

  const speakers = recording.speaker_names ?? [];

  const description = recording.description ?? null;

  const handleClick = (e: React.MouseEvent) => {
    // Ctrl/Cmd+Click toggles checkbox
    if ((e.ctrlKey || e.metaKey) && onCheckToggle) {
      e.preventDefault();
      onCheckToggle();
      return;
    }
    onClick?.();
  };

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCheckToggle?.();
  };

  return (
    <Card
      className={cn(
        "group/card relative cursor-pointer px-3 py-1.5 transition-all shadow-sm hover:bg-gray-50 hover:shadow-md",
        isSelected && "border-l-4 border-l-brand-300 bg-brand-50 shadow-md",
        isChecked && "ring-2 ring-primary/40 bg-primary/5"
      )}
      tabIndex={0}
      role="button"
      onClick={handleClick}
      onKeyDown={(e: React.KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.();
        }
      }}
    >
      {/* Checkbox overlay */}
      {(showCheckbox || isChecked) && onCheckToggle && (
        <div
          className={cn(
            "absolute left-1 top-1 z-10",
            !isChecked && "opacity-0 group-hover/card:opacity-100 transition-opacity"
          )}
          onClick={handleCheckboxClick}
        >
          <div
            className={cn(
              "flex h-5 w-5 items-center justify-center rounded border-2 transition-colors",
              isChecked
                ? "border-primary bg-primary text-primary-foreground"
                : "border-gray-300 bg-white hover:border-primary/50"
            )}
          >
            {isChecked && (
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            )}
          </div>
        </div>
      )}

      {/* Title + Status */}
      <div className={cn("flex items-start justify-between gap-2", (showCheckbox || isChecked) && "pl-5")}>
        <h3 className="text-[15px] font-bold leading-tight line-clamp-1 text-gray-900">{title}</h3>
        {recording.status !== "ready" && (
          <Badge variant={STATUS_VARIANTS[recording.status] ?? "secondary"} className="shrink-0 text-xs">
            {recording.status}
          </Badge>
        )}
      </div>

      {/* Date + Time row */}
      <div className={cn("mt-0.5 flex items-center gap-3 text-[13px] text-gray-500", (showCheckbox || isChecked) && "pl-5")}>
        <span className="inline-flex items-center gap-1">
          <Calendar className="h-3.5 w-3.5" />
          {format(date, "MMM d, yyyy")}
        </span>
        <span className="inline-flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" />
          {format(date, "h:mm a")}
        </span>
      </div>

      {/* Duration + Token Count row */}
      {(durationFormatted || recording.token_count) && (
        <div className={cn("flex items-center gap-3 text-[13px] text-gray-500", (showCheckbox || isChecked) && "pl-5")}>
          {durationFormatted && (
            <span className="inline-flex items-center gap-1">
              <Timer className="h-3.5 w-3.5" />
              {durationFormatted}
            </span>
          )}
          {recording.token_count != null && (
            <span className="inline-flex items-center gap-1">
              <Hash className="h-3.5 w-3.5" />
              {recording.token_count.toLocaleString()} tokens
            </span>
          )}
        </div>
      )}

      {/* Speaker Names row */}
      {speakers.length > 0 && (
        <div className={cn("flex items-center gap-1 text-[13px] text-gray-500", (showCheckbox || isChecked) && "pl-5")}>
          <Users className="h-3.5 w-3.5 shrink-0" />
          <span className="line-clamp-1">{speakers.join(", ")}</span>
        </div>
      )}

      {/* Description */}
      {description && (
        <Tooltip>
          <TooltipTrigger render={<p className={cn("mt-0.5 text-[13px] text-gray-600 line-clamp-2", (showCheckbox || isChecked) && "pl-5")} />}>{description}</TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-xs">
            <p className="text-sm">{description}</p>
          </TooltipContent>
        </Tooltip>
      )}

      {/* Tag IDs (placeholder — full tag display needs tag lookup) */}
    </Card>
  );
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}
