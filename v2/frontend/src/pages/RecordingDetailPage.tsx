import { useCallback, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  ArrowLeft,
  Copy,
  Download,
  FileText,
  FlaskConical,
  Loader2,
  MessageSquare,
  FolderPlus,
  ScanFace,
  Trash2,
  X,
} from "lucide-react";
import { AudioPlayer } from "@/components/recordings/AudioPlayer";
import type { AudioPlayerHandle } from "@/components/recordings/AudioPlayer";
import { TranscriptView } from "@/components/recordings/TranscriptView";
import { ChatPanel } from "@/components/recordings/ChatPanel";
import { useIsMobile } from "@/hooks/useIsMobile";
import {
  useRecording,
  useDeleteRecording,
  useAssignSpeaker,
  useParticipants,
  useCreateParticipant,
  useAnalysisTemplates,
  useRunAnalysis,
  useCollections,
  useAddItemsToCollection,
  useCreateCollection,
} from "@/lib/queries";
import { fetchRecordingAudioUrl, generateSearchSummary } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { AnalysisTemplate, Participant } from "@/types/models";

export default function RecordingDetailPage() {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const audioPlayerRef = useRef<AudioPlayerHandle>(null);

  const [chatOpen, setChatOpen] = useState(false);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [highlightedEntryId, setHighlightedEntryId] = useState<string | null>(null);
  const highlightTimeoutRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [analysisTemplateName, setAnalysisTemplateName] = useState<string | null>(null);

  const { data: recording, isLoading, refetch } = useRecording(id!);

  const { data: audioUrlData } = useQuery({
    queryKey: ["recordings", "audio", id],
    queryFn: () => fetchRecordingAudioUrl(id!),
    enabled: !!recording && recording.source !== "paste" && !!recording.file_path,
  });
  const audioUrl = audioUrlData?.url ?? null;

  const { data: participantsData } = useParticipants();
  const participants: Participant[] = participantsData?.data ?? [];

  const { data: templatesData } = useAnalysisTemplates();
  const analysisTemplates: AnalysisTemplate[] = templatesData ?? [];

  const deleteMutation = useDeleteRecording();
  const assignSpeakerMutation = useAssignSpeaker();
  const createParticipantMutation = useCreateParticipant();
  const analysisMutation = useRunAnalysis();

  const handleBack = useCallback(() => {
    navigate("/recordings");
  }, [navigate]);

  const handleDelete = useCallback(async () => {
    if (!id) return;
    await deleteMutation.mutateAsync(id);
    navigate("/recordings");
  }, [id, deleteMutation, navigate]);

  const handleCopyTranscript = useCallback(() => {
    if (!recording) return;
    const text = recording.diarized_text || recording.transcript_text || "";
    navigator.clipboard.writeText(text).catch(() => {});
  }, [recording]);

  const handleExport = useCallback(() => {
    if (!recording) return;
    const title = recording.title || recording.original_filename;
    const date = recording.recorded_at
      ? format(new Date(recording.recorded_at), "PPp")
      : "";
    const duration = recording.duration_seconds
      ? `${Math.floor(recording.duration_seconds / 60)}m ${Math.floor(recording.duration_seconds % 60)}s`
      : "";

    const lines = [
      title,
      "=".repeat(title.length),
      "",
      date && `Date: ${date}`,
      duration && `Duration: ${duration}`,
      recording.description && `\n${recording.description}`,
      "",
      "---",
      "",
      recording.diarized_text || recording.transcript_text || "No transcript available",
    ]
      .filter(Boolean)
      .join("\n");

    const blob = new Blob([lines], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title.replace(/[^a-zA-Z0-9]/g, "_")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [recording]);

  const handleSpeakerRename = useCallback(
    async (speakerLabel: string, participant: Participant) => {
      if (!id) return;
      await assignSpeakerMutation.mutateAsync({
        recordingId: id,
        speakerLabel,
        body: { participant_id: participant.id },
      });
    },
    [id, assignSpeakerMutation]
  );

  const handleSpeakerCreate = useCallback(
    async (speakerLabel: string, name: string) => {
      if (!id) return;
      const newParticipant = await createParticipantMutation.mutateAsync({
        display_name: name,
      });
      await assignSpeakerMutation.mutateAsync({
        recordingId: id,
        speakerLabel,
        body: { participant_id: newParticipant.id },
      });
    },
    [id, createParticipantMutation, assignSpeakerMutation]
  );

  const handleAcceptSuggestion = useCallback(
    async (speakerLabel: string) => {
      if (!id || !recording?.speaker_mapping) return;
      const mapping = recording.speaker_mapping[speakerLabel];
      if (!mapping?.suggestedParticipantId) return;
      await assignSpeakerMutation.mutateAsync({
        recordingId: id,
        speakerLabel,
        body: { participant_id: mapping.suggestedParticipantId },
      });
    },
    [id, recording, assignSpeakerMutation]
  );

  const handleRejectSuggestion = useCallback(
    async (speakerLabel: string) => {
      if (!id) return;
      // Reject by assigning with empty/null - the backend handles clearing the suggestion
      await assignSpeakerMutation.mutateAsync({
        recordingId: id,
        speakerLabel,
        body: { participant_id: "" },
      });
    },
    [id, assignSpeakerMutation]
  );

  const handleSelectCandidate = useCallback(
    async (speakerLabel: string, participantId: string) => {
      if (!id) return;
      await assignSpeakerMutation.mutateAsync({
        recordingId: id,
        speakerLabel,
        body: { participant_id: participantId },
      });
    },
    [id, assignSpeakerMutation]
  );

  const handleToggleTraining = useCallback(
    async (_speakerLabel: string) => {
      // Training toggle would need a dedicated API endpoint
      // For now this is a placeholder
    },
    []
  );

  const handleAudioPlayStateChange = useCallback(
    (playing: boolean, timeMs: number) => {
      setIsAudioPlaying(playing);
      setCurrentTimeMs(timeMs);
    },
    []
  );

  const handleHighlightEntry = useCallback((entryId: string) => {
    setHighlightedEntryId(entryId);
    if (highlightTimeoutRef.current) clearTimeout(highlightTimeoutRef.current);
    highlightTimeoutRef.current = setTimeout(() => setHighlightedEntryId(null), 2000);
  }, []);

  const handleRunAnalysis = useCallback(
    async (template: AnalysisTemplate) => {
      if (!id) return;
      setAnalysisTemplateName(template.name);
      setAnalysisResult(null);
      try {
        const response = await analysisMutation.mutateAsync({
          recordingId: id,
          body: { template_id: template.id },
        });
        setAnalysisResult(response.result);
      } catch {
        setAnalysisResult("Analysis failed. Please try again.");
      }
    },
    [id, analysisMutation]
  );

  const [identifyingSpakers, setIdentifyingSpeakers] = useState(false);
  const handleIdentifySpeakers = useCallback(async () => {
    if (!id) return;
    setIdentifyingSpeakers(true);
    try {
      await import("@/lib/api").then((api) => api.identifySpeakers(id));
      // Refetch to get updated speaker_mapping
      refetch();
    } catch (e) {
      console.error("Speaker ID failed:", e);
    } finally {
      setIdentifyingSpeakers(false);
    }
  }, [id, refetch]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!recording) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Recording not found
      </div>
    );
  }

  const title = recording.title || recording.original_filename;
  const date = recording.recorded_at
    ? format(new Date(recording.recorded_at), "PPp")
    : format(new Date(recording.created_at), "PPp");
  const duration = recording.duration_seconds
    ? formatDuration(recording.duration_seconds)
    : null;

  const speakerNames = recording.speaker_mapping
    ? Object.values(recording.speaker_mapping)
        .map((s) => s.displayName)
        .filter(Boolean)
    : [];

  return (
    <div className="flex h-full min-w-0 overflow-hidden">
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden pr-2">
        {/* Header */}
        <div className="border-b px-4 py-3">
          <div className="flex items-start gap-3">
            {isMobile && (
              <Button
                variant="ghost"
                size="icon"
                className="mt-0.5 h-8 w-8 shrink-0"
                onClick={handleBack}
              >
                <ArrowLeft className="h-4 w-4" />
              </Button>
            )}

            <div className="min-w-0 flex-1">
              <h1 className="text-lg font-semibold leading-tight">{title}</h1>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <span>{date}</span>
                {duration && <span>{duration}</span>}
                {speakerNames.length > 0 && (
                  <span>{speakerNames.join(", ")}</span>
                )}
                {recording.status !== "ready" && (
                  <Badge variant="secondary" className="text-[10px]">
                    {recording.status}
                  </Badge>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex shrink-0 items-center gap-1">
              <SearchSummaryButton
                recordingId={id!}
                searchSummary={recording.search_summary}
                searchKeywords={recording.search_keywords}
              />
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handleIdentifySpeakers}
                disabled={identifyingSpakers || recording.source === "paste"}
                title="Identify speakers"
              >
                {identifyingSpakers ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ScanFace className="h-4 w-4" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setChatOpen(!chatOpen)}
                title="Chat with transcript"
              >
                <MessageSquare className="h-4 w-4" />
              </Button>
              {analysisTemplates.length > 0 && (
                <DropdownMenu>
                  <DropdownMenuTrigger render={
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Analyze transcript"
                      disabled={analysisMutation.isPending}
                    />
                  }>
                      <FlaskConical className="h-4 w-4" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {analysisTemplates.map((template) => (
                      <DropdownMenuItem
                        key={template.id}
                        onClick={() => handleRunAnalysis(template)}
                      >
                        {template.name}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
              <AddToCollectionButton recordingId={id!} />
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handleCopyTranscript}
                title="Copy transcript"
              >
                <Copy className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handleExport}
                title="Export transcript"
              >
                <Download className="h-4 w-4" />
              </Button>

              <AlertDialog>
                <AlertDialogTrigger
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-destructive hover:bg-accent hover:text-destructive"
                  title="Delete recording"
                >
                  <Trash2 className="h-4 w-4" />
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete recording?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will permanently delete &quot;{title}&quot; and its
                      transcript. This action cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleDelete}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      Delete
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>

          {/* Description */}
          {recording.description && (
            <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
              {recording.description}
            </p>
          )}

          {/* Tags */}
          {recording.tags && recording.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {recording.tags.map((tag) => (
                <Badge
                  key={tag.id}
                  variant="outline"
                  className="text-xs"
                  style={
                    tag.color
                      ? { borderColor: tag.color, color: tag.color }
                      : undefined
                  }
                >
                  {tag.name}
                </Badge>
              ))}
            </div>
          )}

          {/* Collections */}
          {recording.collections && recording.collections.length > 0 && (
            <div className="mt-1.5 flex flex-wrap items-center gap-1">
              <FolderPlus className="h-3 w-3 text-muted-foreground" />
              {recording.collections.map((col: { id: string; name: string }) => (
                <Badge
                  key={col.id}
                  variant="secondary"
                  className="cursor-pointer text-[10px] hover:bg-primary/20"
                  onClick={() => navigate(`/collections/${col.id}`)}
                >
                  {col.name}
                </Badge>
              ))}
            </div>
          )}

          {/* Search Summary */}
          {recording.search_summary && (
            <SearchSummarySection
              summary={recording.search_summary}
              keywords={recording.search_keywords}
            />
          )}
        </div>

        {/* Audio player */}
        {audioUrl && (
          <div className="shrink-0 overflow-hidden border-b px-4 py-2">
            <AudioPlayer
              ref={audioPlayerRef}
              src={audioUrl}
              onPlayStateChange={handleAudioPlayStateChange}
            />
          </div>
        )}

        {/* Analysis result */}
        {(analysisResult !== null || analysisMutation.isPending) && (
          <div className="border-b px-4 py-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">
                {analysisTemplateName ?? "Analysis"}
              </h3>
              {!analysisMutation.isPending && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => {
                    setAnalysisResult(null);
                    setAnalysisTemplateName(null);
                  }}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
            {analysisMutation.isPending ? (
              <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                Analyzing...
              </div>
            ) : (
              <p className="mt-2 whitespace-pre-wrap text-sm">{analysisResult}</p>
            )}
          </div>
        )}

        {/* Transcript */}
        <ScrollArea className="min-h-0 flex-1">
          <TranscriptView
            recording={recording}
            audioPlayerRef={audioPlayerRef}
            participants={participants}
            isAudioPlaying={isAudioPlaying}
            currentTimeMs={currentTimeMs}
            highlightedEntryId={highlightedEntryId}
            onSpeakerRename={handleSpeakerRename}
            onSpeakerCreate={handleSpeakerCreate}
            onAcceptSuggestion={handleAcceptSuggestion}
            onRejectSuggestion={handleRejectSuggestion}
            onSelectCandidate={handleSelectCandidate}
            onToggleTraining={handleToggleTraining}
          />
        </ScrollArea>
      </div>

      {/* Chat panel */}
      <ChatPanel
        recordingId={id!}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        onHighlightEntry={handleHighlightEntry}
      />
    </div>
  );
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}


function SearchSummaryButton({
  recordingId,
  searchSummary,
  searchKeywords,
}: {
  recordingId: string;
  searchSummary: string | null;
  searchKeywords: string[] | null;
}) {
  const [open, setOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [localSummary, setLocalSummary] = useState<string | null>(searchSummary ?? null);
  const [localKeywords, setLocalKeywords] = useState<string[] | null>(searchKeywords ?? null);

  const handleGenerate = useCallback(async () => {
    setIsGenerating(true);
    try {
      const result = await generateSearchSummary(recordingId);
      setLocalSummary(result.summary);
      setLocalKeywords(result.keywords);
    } catch {
      // ignore
    } finally {
      setIsGenerating(false);
    }
  }, [recordingId]);

  const hasSummary = !!localSummary;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            title={hasSummary ? "View search summary" : "Generate search summary"}
          />
        }
      >
        <FileText className="h-4 w-4" />
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg max-h-[80vh] overflow-auto">
        <DialogHeader>
          <DialogTitle>Search Summary</DialogTitle>
          <DialogDescription>
            {hasSummary
              ? "AI-generated summary used for deep search."
              : "No search summary exists yet. Generate one to improve deep search results."}
          </DialogDescription>
        </DialogHeader>

        {hasSummary && (
          <div className="space-y-3">
            <p className="whitespace-pre-wrap text-sm text-muted-foreground leading-relaxed">
              {localSummary}
            </p>
            {localKeywords && localKeywords.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {localKeywords.map((kw, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {kw}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            variant={hasSummary ? "outline" : "default"}
            onClick={handleGenerate}
            disabled={isGenerating}
          >
            {isGenerating && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
            {hasSummary ? "Regenerate" : "Generate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


function SearchSummarySection({
  summary,
  keywords,
}: {
  summary: string;
  keywords: string[] | null;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
      >
        <span>{expanded ? "Hide" : "Show"} search summary</span>
      </button>

      {expanded && (
        <div className="mt-2 rounded-md border bg-muted/30 p-3">
          <p className="whitespace-pre-wrap text-xs text-muted-foreground leading-relaxed">
            {summary}
          </p>
          {keywords && keywords.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {keywords.map((kw, i) => (
                <Badge key={i} variant="secondary" className="text-[10px]">
                  {kw}
                </Badge>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function AddToCollectionButton({ recordingId }: { recordingId: string }) {
  const { data: collectionsData } = useCollections();
  const addItems = useAddItemsToCollection();
  const createCollection = useCreateCollection();
  const [added, setAdded] = useState<string | null>(null);

  const collections = collectionsData ?? [];

  const handleAddTo = useCallback(
    async (collectionId: string, collectionName: string) => {
      try {
        await addItems.mutateAsync({ collectionId, recordingIds: [recordingId] });
        setAdded(collectionName);
        setTimeout(() => setAdded(null), 2000);
      } catch {
        // ignore duplicate
      }
    },
    [recordingId, addItems]
  );

  const handleCreateNew = useCallback(async () => {
    try {
      const newCol = await createCollection.mutateAsync({ name: "New Collection" });
      await addItems.mutateAsync({ collectionId: newCol.id, recordingIds: [recordingId] });
      setAdded("New Collection");
      setTimeout(() => setAdded(null), 2000);
    } catch {
      // ignore
    }
  }, [recordingId, createCollection, addItems]);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          title={added ? `Added to ${added}` : "Add to collection"}
        />
      }>
          <FolderPlus className={cn("h-4 w-4", added && "text-green-500")} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {collections.length > 0 ? (
          collections.map((col) => (
            <DropdownMenuItem
              key={col.id}
              onClick={() => handleAddTo(col.id, col.name)}
            >
              {col.name}
              {col.item_count > 0 && (
                <span className="ml-auto text-xs text-muted-foreground">{col.item_count}</span>
              )}
            </DropdownMenuItem>
          ))
        ) : (
          <DropdownMenuItem disabled className="text-xs text-muted-foreground">
            No collections yet
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onClick={handleCreateNew}>
          <FolderPlus className="mr-2 h-3.5 w-3.5" />
          New Collection
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
