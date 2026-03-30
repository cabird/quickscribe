import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Pencil, Play, Pause } from "lucide-react";
import { SpeakerDropdown } from "./SpeakerDropdown";
import { SpeakerConfidenceBadge } from "./SpeakerConfidenceBadge";
import type { TranscriptEntryData } from "@/hooks/use-transcript-parser";
import type { Participant, SpeakerMappingEntry } from "@/types/models";

const SPEAKER_COLORS = [
  { border: "border-l-blue-500", text: "text-blue-600 dark:text-blue-400" },
  { border: "border-l-purple-500", text: "text-purple-600 dark:text-purple-400" },
  { border: "border-l-green-500", text: "text-green-600 dark:text-green-400" },
  { border: "border-l-amber-500", text: "text-amber-600 dark:text-amber-400" },
  { border: "border-l-red-500", text: "text-red-600 dark:text-red-400" },
  { border: "border-l-indigo-500", text: "text-indigo-600 dark:text-indigo-400" },
];

interface TranscriptEntryProps {
  entry: TranscriptEntryData;
  speakerIndex: number;
  isPlaying?: boolean;
  isHighlighted?: boolean;
  participants?: Participant[];
  speakerMapping?: SpeakerMappingEntry;
  onSeek?: (timeMs: number) => void;
  onPause?: () => void;
  onSpeakerRename?: (speakerLabel: string, participant: Participant) => void;
  onSpeakerCreate?: (speakerLabel: string, name: string) => void;
  onAcceptSuggestion?: (speakerLabel: string) => void;
  onRejectSuggestion?: (speakerLabel: string) => void;
  onSelectCandidate?: (speakerLabel: string, participantId: string) => void;
  onToggleTraining?: (speakerLabel: string) => void;
}

export function TranscriptEntry({
  entry,
  speakerIndex,
  isPlaying,
  isHighlighted,
  participants = [],
  speakerMapping,
  onSeek,
  onPause,
  onSpeakerRename,
  onSpeakerCreate,
  onAcceptSuggestion,
  onRejectSuggestion,
  onSelectCandidate,
  onToggleTraining,
}: TranscriptEntryProps) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const color = SPEAKER_COLORS[speakerIndex % SPEAKER_COLORS.length];
  const hasTimestamps = entry.startTimeMs != null;

  const handlePlayClick = useCallback(() => {
    if (isPlaying) {
      onPause?.();
    } else if (entry.startTimeMs != null) {
      onSeek?.(entry.startTimeMs);
    }
  }, [isPlaying, entry.startTimeMs, onSeek, onPause]);

  const handleSelectParticipant = useCallback(
    (participant: Participant) => {
      onSpeakerRename?.(entry.speakerLabel, participant);
      setShowDropdown(false);
    },
    [entry.speakerLabel, onSpeakerRename]
  );

  const handleCreateParticipant = useCallback(
    (name: string) => {
      onSpeakerCreate?.(entry.speakerLabel, name);
      setShowDropdown(false);
    },
    [entry.speakerLabel, onSpeakerCreate]
  );

  // Determine identification status from speaker mapping
  const idStatus = speakerMapping?.identificationStatus;

  return (
    <div
      id={entry.id}
      className={cn(
        "group relative border-l-2 py-1.5 pl-3 pr-2 transition-colors",
        color.border,
        isHighlighted && "bg-yellow-50 dark:bg-yellow-900/20",
        isPlaying && "bg-accent/30"
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="flex items-start gap-2">
        <div className="relative flex-1 min-w-0">
          {entry.displayName && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className={cn("text-xs font-semibold", color.text)}>
                {entry.displayName}
              </span>
              {idStatus && (
                <SpeakerConfidenceBadge
                  identificationStatus={idStatus}
                  similarity={speakerMapping?.similarity}
                  suggestedName={speakerMapping?.suggestedDisplayName}
                  topCandidates={speakerMapping?.topCandidates}
                  useForTraining={speakerMapping?.useForTraining}
                  onAcceptSuggestion={
                    onAcceptSuggestion
                      ? () => onAcceptSuggestion(entry.speakerLabel)
                      : undefined
                  }
                  onRejectSuggestion={
                    onRejectSuggestion
                      ? () => onRejectSuggestion(entry.speakerLabel)
                      : undefined
                  }
                  onSelectCandidate={
                    onSelectCandidate
                      ? (pid) => onSelectCandidate(entry.speakerLabel, pid)
                      : undefined
                  }
                  onToggleTraining={
                    onToggleTraining
                      ? () => onToggleTraining(entry.speakerLabel)
                      : undefined
                  }
                />
              )}
            </div>
          )}

          <p className="text-sm leading-relaxed">{entry.text}</p>
        </div>

        {/* Hover actions */}
        {isHovered && (
          <div className="flex shrink-0 items-center gap-0.5">
            {hasTimestamps && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={handlePlayClick}
                title={isPlaying ? "Pause" : "Play from here"}
              >
                {isPlaying ? (
                  <Pause className="h-3 w-3" />
                ) : (
                  <Play className="h-3 w-3" />
                )}
              </Button>
            )}
            {(onSpeakerRename || onSpeakerCreate) && entry.speakerLabel && (
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => setShowDropdown(!showDropdown)}
                title="Rename speaker"
              >
                <Pencil className="h-3 w-3" />
              </Button>
            )}
          </div>
        )}
      </div>

      {showDropdown && (
        <SpeakerDropdown
          participants={participants}
          currentName={entry.displayName}
          onSelect={handleSelectParticipant}
          onCreateNew={handleCreateParticipant}
          onClose={() => setShowDropdown(false)}
          className="left-4 top-full mt-1"
        />
      )}
    </div>
  );
}
