import { useCallback, useEffect, useMemo } from "react";
import { TranscriptEntry } from "./TranscriptEntry";
import { useTranscriptParser } from "@/hooks/use-transcript-parser";
import type { AudioPlayerHandle } from "./AudioPlayer";
import type { Participant, Recording, SpeakerMappingEntry } from "@/types/models";

interface TranscriptViewProps {
  recording: Recording;
  audioPlayerRef?: React.RefObject<AudioPlayerHandle | null>;
  participants?: Participant[];
  isAudioPlaying?: boolean;
  currentTimeMs?: number;
  highlightedEntryId?: string | null;
  onSpeakerRename?: (speakerLabel: string, participant: Participant) => void;
  onSpeakerCreate?: (speakerLabel: string, name: string) => void;
  onAcceptSuggestion?: (speakerLabel: string) => void;
  onRejectSuggestion?: (speakerLabel: string) => void;
  onSelectCandidate?: (speakerLabel: string, participantId: string) => void;
  onToggleTraining?: (speakerLabel: string) => void;
}

export function TranscriptView({
  recording,
  audioPlayerRef,
  participants = [],
  isAudioPlaying = false,
  currentTimeMs = 0,
  highlightedEntryId: externalHighlightedEntryId = null,
  onSpeakerRename,
  onSpeakerCreate,
  onAcceptSuggestion,
  onRejectSuggestion,
  onSelectCandidate,
  onToggleTraining,
}: TranscriptViewProps) {
  const highlightedEntryId = externalHighlightedEntryId;

  const speakerMapping = useMemo(() => {
    if (!recording.speaker_mapping) return null;
    try {
      return typeof recording.speaker_mapping === "string"
        ? JSON.parse(recording.speaker_mapping)
        : recording.speaker_mapping;
    } catch {
      return null;
    }
  }, [recording.speaker_mapping]);

  const transcriptJsonStr =
    typeof recording.transcript_json === "string"
      ? recording.transcript_json
      : recording.transcript_json != null
        ? JSON.stringify(recording.transcript_json)
        : null;

  const entries = useTranscriptParser(
    transcriptJsonStr,
    recording.diarized_text,
    recording.transcript_text,
    speakerMapping,
  );

  // Build speaker index map for consistent coloring
  const speakerIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    let idx = 0;
    for (const entry of entries) {
      if (entry.speakerLabel && !map.has(entry.speakerLabel)) {
        map.set(entry.speakerLabel, idx++);
      }
    }
    return map;
  }, [entries]);

  // Find currently playing entry
  const playingEntryId = useMemo(() => {
    if (!isAudioPlaying) return null;
    for (const entry of entries) {
      if (
        entry.startTimeMs != null &&
        entry.endTimeMs != null &&
        currentTimeMs >= entry.startTimeMs &&
        currentTimeMs < entry.endTimeMs
      ) {
        return entry.id;
      }
    }
    return null;
  }, [entries, currentTimeMs, isAudioPlaying]);

  // Auto-scroll to currently playing entry
  useEffect(() => {
    if (!playingEntryId) return;
    const el = document.getElementById(playingEntryId);
    el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [playingEntryId]);

  const handleSeek = useCallback(
    (timeMs: number) => {
      audioPlayerRef?.current?.seekTo(timeMs);
    },
    [audioPlayerRef]
  );

  const handlePause = useCallback(() => {
    audioPlayerRef?.current?.pause();
  }, [audioPlayerRef]);

  // Scroll to externally highlighted entry
  useEffect(() => {
    if (externalHighlightedEntryId) {
      const el = document.getElementById(externalHighlightedEntryId);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [externalHighlightedEntryId]);

  if (entries.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        No transcript available
      </div>
    );
  }

  return (
    <div className="divide-y">
      {entries.map((entry) => {
        const mapping: SpeakerMappingEntry | undefined =
          speakerMapping?.[entry.speakerLabel];
        return (
          <TranscriptEntry
            key={entry.id}
            entry={entry}
            speakerIndex={speakerIndexMap.get(entry.speakerLabel) ?? 0}
            isPlaying={playingEntryId === entry.id}
            isHighlighted={highlightedEntryId === entry.id}
            participants={participants}
            speakerMapping={mapping}
            onSeek={handleSeek}
            onPause={handlePause}
            onSpeakerRename={onSpeakerRename}
            onSpeakerCreate={onSpeakerCreate}
            onAcceptSuggestion={onAcceptSuggestion}
            onRejectSuggestion={onRejectSuggestion}
            onSelectCandidate={onSelectCandidate}
            onToggleTraining={onToggleTraining}
          />
        );
      })}
    </div>
  );
}
