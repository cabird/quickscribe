import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Check, HelpCircle, X, Brain } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TopCandidate } from "@/types/models";

interface SpeakerConfidenceBadgeProps {
  identificationStatus?: "auto" | "suggest" | "unknown" | "dismissed";
  similarity?: number | null;
  suggestedName?: string | null;
  topCandidates?: TopCandidate[];
  useForTraining?: boolean;
  onAcceptSuggestion?: () => void;
  onRejectSuggestion?: () => void;
  onSelectCandidate?: (participantId: string) => void;
  onToggleTraining?: () => void;
}

export function SpeakerConfidenceBadge({
  identificationStatus,
  similarity,
  suggestedName,
  topCandidates = [],
  useForTraining,
  onAcceptSuggestion,
  onRejectSuggestion,
  onSelectCandidate,
  onToggleTraining,
}: SpeakerConfidenceBadgeProps) {
  const [showCandidates, setShowCandidates] = useState(false);

  if (!identificationStatus || identificationStatus === "dismissed") {
    return null;
  }

  const pct = similarity ? `${Math.round(similarity * 100)}%` : "";

  if (identificationStatus === "auto") {
    return (
      <span className="inline-flex items-center gap-1">
        <Tooltip>
          <TooltipTrigger render={<span className="inline-flex items-center gap-0.5 rounded-full bg-green-100 px-1.5 py-px text-[11px] font-medium text-green-800" />}>
              <Check className="h-3 w-3" />
              {pct}
          </TooltipTrigger>
          <TooltipContent>Auto-identified ({pct})</TooltipContent>
        </Tooltip>
        {onToggleTraining && (
          <Tooltip>
            <TooltipTrigger render={
              <span
                className={cn(
                  "inline-flex cursor-pointer items-center gap-0.5 rounded-full px-1.5 py-px text-[11px] font-medium",
                  useForTraining
                    ? "bg-blue-100 text-blue-800"
                    : "bg-gray-100 text-gray-400"
                )}
                onClick={onToggleTraining}
              />
            }>
                <Brain className="h-3 w-3" />
            </TooltipTrigger>
            <TooltipContent>
              {useForTraining
                ? "Approved for voice training -- click to revoke"
                : "Not used for voice training -- click to approve"}
            </TooltipContent>
          </Tooltip>
        )}
      </span>
    );
  }

  if (identificationStatus === "suggest") {
    return (
      <span className="inline-flex flex-wrap items-center gap-1">
        <Tooltip>
          <TooltipTrigger render={
            <span
              className="inline-flex cursor-pointer items-center gap-0.5 rounded-full bg-amber-100 px-1.5 py-px text-[11px] font-medium text-amber-800"
              onClick={() => setShowCandidates(!showCandidates)}
            />
          }>
              <HelpCircle className="h-3 w-3" />
              {suggestedName || "?"}
          </TooltipTrigger>
          <TooltipContent>
            Suggested: {suggestedName || "unknown"} ({pct})
          </TooltipContent>
        </Tooltip>
        {onAcceptSuggestion && (
          <span className="inline-flex gap-0.5">
            <Tooltip>
              <TooltipTrigger render={
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5"
                  onClick={onAcceptSuggestion}
                />
              }>
                  <Check className="h-3 w-3" />
              </TooltipTrigger>
              <TooltipContent>Accept suggestion</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger render={
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5"
                  onClick={onRejectSuggestion}
                />
              }>
                  <X className="h-3 w-3" />
              </TooltipTrigger>
              <TooltipContent>Reject suggestion</TooltipContent>
            </Tooltip>
          </span>
        )}
        {showCandidates && topCandidates.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-0.5">
            {topCandidates.slice(0, 5).map((c) => (
              <span
                key={c.participantId}
                className="inline-flex cursor-pointer items-center gap-1 rounded-full border px-2 py-px text-[11px] font-medium transition-colors hover:bg-accent"
                onClick={() => onSelectCandidate?.(c.participantId)}
              >
                {c.displayName || c.participantId.substring(0, 8)}
                <span className="text-[10px] text-muted-foreground">
                  {Math.round(c.similarity * 100)}%
                </span>
              </span>
            ))}
          </div>
        )}
      </span>
    );
  }

  // unknown
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <Tooltip>
        <TooltipTrigger render={
          <span
            className="inline-flex cursor-pointer items-center gap-0.5 rounded-full bg-gray-100 px-1.5 py-px text-[11px] font-medium text-gray-500"
            onClick={() => setShowCandidates(!showCandidates)}
          />
        }>
            <HelpCircle className="h-3 w-3" />?
        </TooltipTrigger>
        <TooltipContent>Unknown speaker</TooltipContent>
      </Tooltip>
      {showCandidates && topCandidates.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-0.5">
          {topCandidates.slice(0, 5).map((c) => (
            <span
              key={c.participantId}
              className="inline-flex cursor-pointer items-center gap-1 rounded-full border px-2 py-px text-[11px] font-medium transition-colors hover:bg-accent"
              onClick={() => onSelectCandidate?.(c.participantId)}
            >
              {c.displayName || c.participantId.substring(0, 8)}
              <span className="text-[10px] text-muted-foreground">
                {Math.round(c.similarity * 100)}%
              </span>
            </span>
          ))}
        </div>
      )}
    </span>
  );
}
