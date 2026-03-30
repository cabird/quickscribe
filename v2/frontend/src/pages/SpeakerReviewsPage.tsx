import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Check, HelpCircle, Pause, Play, X } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { useIsMobile } from "@/hooks/useIsMobile";
import {
  useAssignSpeaker,
  useDismissSpeaker,
  useParticipants,
} from "@/lib/queries";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import { SpeakerDropdown } from "@/components/recordings/SpeakerDropdown";
import type {
  RecordingDetail,
  Participant,
  SpeakerMappingEntry,
  TopCandidate,
} from "@/types/models";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ReviewableRecording {
  recording: RecordingDetail;
  pendingSpeakers: {
    label: string;
    entry: SpeakerMappingEntry;
  }[];
  suggestCount: number;
  unknownCount: number;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ReviewRecordingCard({
  item,
  isSelected,
  onClick,
}: {
  item: ReviewableRecording;
  isSelected: boolean;
  onClick: () => void;
}) {
  const title = item.recording.title || item.recording.original_filename;
  return (
    <Card
      className={cn(
        "cursor-pointer px-3 py-2.5 transition-all hover:bg-gray-50",
        isSelected && "border-l-4 border-l-brand-300 bg-brand-50"
      )}
      onClick={onClick}
    >
      <h3 className="text-sm font-semibold line-clamp-1">{title}</h3>
      <div className="mt-1 flex items-center gap-2">
        {item.suggestCount > 0 && (
          <Badge
            variant="outline"
            className="border-amber-300 text-amber-700 text-[10px]"
          >
            {item.suggestCount} suggested
          </Badge>
        )}
        {item.unknownCount > 0 && (
          <Badge
            variant="outline"
            className="border-gray-300 text-gray-500 text-[10px]"
          >
            {item.unknownCount} unknown
          </Badge>
        )}
      </div>
    </Card>
  );
}

function SpeakerReviewCard({
  speakerLabel,
  entry,
  participants,
  recordingId,
  audioUrl,
  segment,
  onAction,
}: {
  speakerLabel: string;
  entry: SpeakerMappingEntry;
  participants: Participant[];
  recordingId: string;
  audioUrl?: string | null;
  segment?: { start_s: number; end_s: number } | null;
  onAction: () => void;
}) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionDone, setActionDone] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [selectedParticipantId, setSelectedParticipantId] = useState<string | null>(
    entry.suggestedParticipantId ?? null
  );
  const [selectedDisplayName, setSelectedDisplayName] = useState<string | null>(
    entry.suggestedDisplayName ?? null
  );
  const [useForTraining, setUseForTraining] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const assignSpeaker = useAssignSpeaker();
  const dismissSpeaker = useDismissSpeaker();

  const handlePlaySegment = useCallback(() => {
    if (!audioUrl || !segment) return;
    if (isPlaying) {
      audioRef.current?.pause();
      setIsPlaying(false);
      return;
    }
    if (!audioRef.current) {
      audioRef.current = new Audio(audioUrl);
      audioRef.current.addEventListener("ended", () => setIsPlaying(false));
      audioRef.current.addEventListener("pause", () => setIsPlaying(false));
      audioRef.current.addEventListener("timeupdate", () => {
        if (audioRef.current && segment && audioRef.current.currentTime >= segment.end_s) {
          audioRef.current.pause();
          setIsPlaying(false);
        }
      });
    }
    audioRef.current.currentTime = segment.start_s;
    audioRef.current.play().catch(() => {});
    setIsPlaying(true);
  }, [audioUrl, segment, isPlaying]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, []);

  const handleAccept = useCallback(async () => {
    if (!selectedParticipantId) return;
    setSaving(true);
    try {
      await assignSpeaker.mutateAsync({
        recordingId,
        speakerLabel,
        body: {
          participant_id: selectedParticipantId,
          use_for_training: useForTraining,
        },
      });
      setActionDone("Confirmed");
      onAction();
    } finally {
      setSaving(false);
    }
  }, [recordingId, speakerLabel, selectedParticipantId, useForTraining, assignSpeaker, onAction]);

  const handleDismiss = useCallback(async () => {
    setSaving(true);
    try {
      await dismissSpeaker.mutateAsync({
        recordingId,
        speakerLabel,
      });
      setActionDone("Dismissed");
      onAction();
    } finally {
      setSaving(false);
    }
  }, [recordingId, speakerLabel, dismissSpeaker, onAction]);

  const handleSelectCandidate = useCallback(
    (participantId: string, displayName: string) => {
      setSelectedParticipantId(participantId);
      setSelectedDisplayName(displayName);
      setShowDropdown(false);
    },
    []
  );

  const handleSelectParticipant = useCallback(
    (participant: Participant) => {
      setSelectedParticipantId(participant.id);
      setSelectedDisplayName(participant.display_name);
      setShowDropdown(false);
    },
    []
  );

  const queryClient = useQueryClient();
  const handleCreateNew = useCallback(
    async (name: string) => {
      setShowDropdown(false);
      try {
        const newParticipant = await api.createParticipant({ display_name: name });
        setSelectedParticipantId(newParticipant.id);
        setSelectedDisplayName(newParticipant.display_name);
        // Invalidate participants cache so the new person shows up in other cards
        queryClient.invalidateQueries({ queryKey: ["participants"] });
      } catch (e) {
        console.error("Failed to create participant:", e);
      }
    },
    [queryClient]
  );

  const handleClearSelection = useCallback(() => {
    setSelectedParticipantId(null);
    setSelectedDisplayName(null);
  }, []);

  if (actionDone) {
    return (
      <Card className={cn(
        "px-4 py-3",
        actionDone === "Confirmed"
          ? "border-green-200 bg-green-50"
          : "border-gray-200 bg-gray-50"
      )}>
        <div className={cn(
          "flex items-center gap-2 text-sm",
          actionDone === "Confirmed" ? "text-green-700" : "text-gray-500"
        )}>
          <Check className="h-4 w-4" />
          <span className="font-medium">{speakerLabel}</span>
          <span>-- {actionDone}</span>
        </div>
      </Card>
    );
  }

  const isSuggest = entry.identificationStatus === "suggest";
  const topCandidates: TopCandidate[] = entry.topCandidates ?? [];

  return (
    <Card className="px-4 py-3 space-y-3">
      {/* 1. Header row */}
      <div className="flex items-center gap-2 flex-wrap">
        {audioUrl && segment && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={handlePlaySegment}
            title={`Play ${speakerLabel} segment (${Math.round(segment.end_s - segment.start_s)}s)`}
          >
            {isPlaying ? (
              <Pause className="h-3.5 w-3.5" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
          </Button>
        )}
        <span className="text-sm font-semibold">{speakerLabel}</span>
        {entry.displayName && (
          <span className="text-xs text-muted-foreground">
            {entry.displayName}
          </span>
        )}
        {isSuggest ? (
          <Badge
            variant="outline"
            className="border-amber-300 text-amber-700 text-[10px]"
          >
            <HelpCircle className="mr-0.5 h-3 w-3" />
            suggest
          </Badge>
        ) : (
          <Badge
            variant="outline"
            className="border-gray-300 text-gray-500 text-[10px]"
          >
            <HelpCircle className="mr-0.5 h-3 w-3" />
            unknown
          </Badge>
        )}
        {saving && (
          <span className="ml-auto text-xs text-muted-foreground">Saving...</span>
        )}
      </div>

      {/* 2. Candidate pills */}
      {topCandidates.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {topCandidates.slice(0, 5).map((c) => {
            const isSelected = selectedParticipantId === c.participantId;
            return (
              <Tooltip key={c.participantId}>
                <TooltipTrigger render={
                  <button
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
                      isSelected
                        ? "border-brand-400 bg-brand-100 text-brand-800"
                        : "hover:bg-accent"
                    )}
                    onClick={() =>
                      handleSelectCandidate(
                        c.participantId,
                        c.displayName || c.participantId.substring(0, 8)
                      )
                    }
                    disabled={saving}
                  />
                }>
                    {c.displayName || c.participantId.substring(0, 8)}
                    <span className="text-[10px] text-muted-foreground">
                      {Math.round(c.similarity * 100)}%
                    </span>
                </TooltipTrigger>
                <TooltipContent>Select {c.displayName}</TooltipContent>
              </Tooltip>
            );
          })}
        </div>
      )}

      {/* 3. Assign dropdown */}
      <div className="relative">
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs"
          onClick={() => setShowDropdown(!showDropdown)}
          disabled={saving}
        >
          Assign speaker...
        </Button>
        {showDropdown && (
          <SpeakerDropdown
            participants={participants}
            currentName={entry.displayName ?? ""}
            onSelect={handleSelectParticipant}
            onCreateNew={handleCreateNew}
            onClose={() => setShowDropdown(false)}
            className="left-0 top-full mt-1"
          />
        )}
      </div>

      {/* 4. Preview area */}
      {selectedParticipantId && selectedDisplayName && (
        <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-1.5 text-sm text-green-800">
          <Check className="h-3.5 w-3.5 shrink-0" />
          <span>Selected: <span className="font-medium">{selectedDisplayName}</span></span>
          <button
            className="ml-auto inline-flex items-center rounded-full p-0.5 text-green-600 hover:bg-green-200 transition-colors"
            onClick={handleClearSelection}
            title="Clear selection"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* 5. Use for training toggle */}
      <div className="space-y-0.5">
        <div className="flex items-center gap-2">
          <Switch
            size="sm"
            checked={useForTraining}
            onCheckedChange={setUseForTraining}
            id={`training-${speakerLabel}`}
          />
          <Label htmlFor={`training-${speakerLabel}`} className="text-xs font-medium cursor-pointer">
            Use for training
          </Label>
        </div>
        <p className="text-[11px] text-muted-foreground pl-8">
          Check if audio quality is good for voice profile training.
        </p>
      </div>

      {/* 6. Action buttons */}
      <div className="flex items-center gap-2 pt-1 border-t">
        <Button
          variant="default"
          size="sm"
          className="h-7 gap-1 text-xs"
          onClick={handleAccept}
          disabled={saving || !selectedParticipantId}
        >
          <Check className="h-3 w-3" />
          Accept
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-7 gap-1 text-xs"
          onClick={handleDismiss}
          disabled={saving}
        >
          Dismiss
        </Button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Audit log sub-view
// ---------------------------------------------------------------------------

function AuditLogView({ recordings }: { recordings: ReviewableRecording[] }) {
  const allHistory = useMemo(() => {
    const entries: {
      recordingTitle: string;
      speakerLabel: string;
      action: string;
      displayName?: string;
      similarity?: number;
      timestamp: string;
      source?: string;
    }[] = [];

    for (const item of recordings) {
      const title =
        item.recording.title || item.recording.original_filename;
      if (!item.recording.speaker_mapping) continue;
      for (const [label, mapping] of Object.entries(
        item.recording.speaker_mapping
      )) {
        if (mapping.identificationHistory) {
          for (const h of mapping.identificationHistory) {
            entries.push({
              recordingTitle: title,
              speakerLabel: label,
              action: h.action,
              displayName: h.displayName,
              similarity: h.similarity,
              timestamp: h.timestamp,
              source: h.source,
            });
          }
        }
      }
    }

    entries.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
    return entries;
  }, [recordings]);

  if (allHistory.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
        No audit history available
      </div>
    );
  }

  const actionColors: Record<string, string> = {
    auto_assigned: "bg-green-100 text-green-800",
    accepted: "bg-blue-100 text-blue-800",
    rejected: "bg-red-100 text-red-800",
    dismissed: "bg-gray-100 text-gray-600",
    training_approved: "bg-purple-100 text-purple-800",
    training_revoked: "bg-orange-100 text-orange-800",
    manual_assigned: "bg-blue-100 text-blue-800",
    reidentified: "bg-teal-100 text-teal-800",
  };

  return (
    <div className="space-y-2 p-4">
      {allHistory.map((entry, i) => (
        <div
          key={`${entry.timestamp}-${i}`}
          className="flex items-center gap-3 rounded-md border px-3 py-2 text-sm"
        >
          <Badge
            variant="outline"
            className={cn(
              "text-[10px] shrink-0",
              actionColors[entry.action] || "bg-gray-100 text-gray-600"
            )}
          >
            {entry.action.replace(/_/g, " ")}
          </Badge>
          <div className="min-w-0 flex-1">
            <span className="font-medium">{entry.speakerLabel}</span>
            {entry.displayName && (
              <span className="text-muted-foreground">
                {" "}
                -- {entry.displayName}
              </span>
            )}
            {entry.similarity != null && (
              <span className="text-muted-foreground">
                {" "}
                ({Math.round(entry.similarity * 100)}%)
              </span>
            )}
          </div>
          <span className="shrink-0 text-xs text-muted-foreground">
            {new Date(entry.timestamp).toLocaleString()}
          </span>
          {entry.source && (
            <span className="shrink-0 text-[10px] text-muted-foreground">
              {entry.source}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function SpeakerReviewsPage() {
  const isMobile = useIsMobile();
  const [selectedRecordingId, setSelectedRecordingId] = useState<string | null>(
    null
  );
  const [activeView, setActiveView] = useState<"pending" | "audit">("pending");

  const { data: recordingsResponse, refetch } = useQuery({
    queryKey: ["speaker-reviews"],
    queryFn: () => api.fetchSpeakerReviews(),
  });
  const { data: participantsData } = useParticipants();
  const participants: Participant[] = participantsData?.data ?? [];

  const reviewableRecordings: ReviewableRecording[] = useMemo(() => {
    if (!recordingsResponse?.data) return [];
    const items: ReviewableRecording[] = [];

    for (const rec of recordingsResponse.data) {
      if (!rec.speaker_mapping) continue;
      const pendingSpeakers: ReviewableRecording["pendingSpeakers"] = [];
      let suggestCount = 0;
      let unknownCount = 0;

      for (const [label, entry] of Object.entries(rec.speaker_mapping)) {
        if (
          entry.identificationStatus === "suggest" ||
          entry.identificationStatus === "unknown"
        ) {
          pendingSpeakers.push({ label, entry });
          if (entry.identificationStatus === "suggest") suggestCount++;
          else unknownCount++;
        }
      }

      if (pendingSpeakers.length > 0) {
        items.push({
          recording: rec,
          pendingSpeakers,
          suggestCount,
          unknownCount,
        });
      }
    }

    return items;
  }, [recordingsResponse]);

  // Check if any recordings have audit history
  const hasAuditData = useMemo(() => {
    if (!recordingsResponse?.data) return false;
    return recordingsResponse.data.some((rec) => {
      if (!rec.speaker_mapping) return false;
      return Object.values(rec.speaker_mapping).some(
        (m) => m.identificationHistory && m.identificationHistory.length > 0
      );
    });
  }, [recordingsResponse]);

  const selectedItem = useMemo(
    () =>
      reviewableRecordings.find(
        (r) => r.recording.id === selectedRecordingId
      ) ?? null,
    [reviewableRecordings, selectedRecordingId]
  );

  // Fetch audio URL for the selected recording
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!selectedItem) {
      setAudioUrl(null);
      return;
    }
    let cancelled = false;
    api.fetchRecordingAudioUrl(selectedItem.recording.id)
      .then((res) => { if (!cancelled) setAudioUrl(res.url || null); })
      .catch(() => { if (!cancelled) setAudioUrl(null); });
    return () => { cancelled = true; };
  }, [selectedItem?.recording.id]);

  const handleAction = useCallback(() => {
    void refetch();
  }, [refetch]);

  // Auto-select first if nothing selected
  if (
    !selectedRecordingId &&
    reviewableRecordings.length > 0 &&
    !isMobile
  ) {
    setSelectedRecordingId(reviewableRecordings[0].recording.id);
  }

  const listPanel = (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b p-3">
        <h2 className="text-lg font-semibold">Speaker Reviews</h2>
        <div className="mt-2 flex items-center gap-2">
          <Button
            variant={activeView === "pending" ? "default" : "outline"}
            size="sm"
            className="h-7 text-xs"
            onClick={() => setActiveView("pending")}
          >
            Pending Reviews
            {reviewableRecordings.length > 0 && (
              <Badge variant="secondary" className="ml-1 text-[10px]">
                {reviewableRecordings.length}
              </Badge>
            )}
          </Button>
          {hasAuditData && (
            <Button
              variant={activeView === "audit" ? "default" : "outline"}
              size="sm"
              className="h-7 text-xs"
              onClick={() => setActiveView("audit")}
            >
              Audit Log
            </Button>
          )}
        </div>
      </div>

      {activeView === "pending" ? (
        <ScrollArea className="min-h-0 flex-1">
          {reviewableRecordings.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
              No speakers pending review
            </div>
          ) : (
            <div className="space-y-1 p-2">
              {reviewableRecordings.map((item) => (
                <ReviewRecordingCard
                  key={item.recording.id}
                  item={item}
                  isSelected={item.recording.id === selectedRecordingId}
                  onClick={() => {
                    setSelectedRecordingId(item.recording.id);
                  }}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      ) : (
        <ScrollArea className="min-h-0 flex-1">
          <AuditLogView recordings={reviewableRecordings} />
        </ScrollArea>
      )}
    </div>
  );

  const detailPanel = selectedItem ? (
    <ScrollArea className="h-full">
      <div className="space-y-3 p-4">
        <h3 className="text-base font-semibold">
          {selectedItem.recording.title ||
            selectedItem.recording.original_filename}
        </h3>
        {selectedItem.pendingSpeakers.map(({ label, entry }) => (
          <SpeakerReviewCard
            key={label}
            speakerLabel={label}
            entry={entry}
            participants={participants}
            recordingId={selectedItem.recording.id}
            audioUrl={audioUrl}
            segment={((selectedItem.recording as unknown as Record<string, unknown>).speaker_segments as Record<string, { start_s: number; end_s: number }> | undefined)?.[label]}
            onAction={handleAction}
          />
        ))}
      </div>
    </ScrollArea>
  ) : (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
      Select a recording to review speakers
    </div>
  );

  // Mobile: list or detail
  if (isMobile) {
    if (selectedRecordingId && selectedItem) {
      return (
        <div className="flex h-full flex-col">
          <div className="border-b p-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedRecordingId(null)}
            >
              Back to list
            </Button>
          </div>
          {detailPanel}
        </div>
      );
    }
    return listPanel;
  }

  // Desktop: split view
  return (
    <div className="flex h-full">
      <div className="w-[380px] shrink-0 border-r overflow-hidden">
        {listPanel}
      </div>
      <div className="flex-1 overflow-hidden">{detailPanel}</div>
    </div>
  );
}
