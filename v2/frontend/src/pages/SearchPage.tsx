import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ChevronRight, ChevronDown, Clock, FolderOpen, Loader2, Search, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { deepSearch } from "@/lib/api";
import { authEnabled, getAccessToken } from "@/lib/auth";
import { useCreateCollectionFromCandidates, useSearchHistory } from "@/lib/queries";
import type { DeepSearchResult, DeepSearchTagMapEntry, SearchHistoryItem } from "@/types/models";

type SearchPhase = "idle" | "searching" | "extracting" | "synthesizing" | "done" | "error";

// ---------------------------------------------------------------------------
// Trace types
// ---------------------------------------------------------------------------

interface TraceEntry {
  tier: string;
  step: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  duration_ms: number;
  input_preview: string;
  output_preview: string;
  output_raw?: string;
}

interface TraceSummary {
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_duration_ms: number;
  traces: TraceEntry[];
}

// ---------------------------------------------------------------------------
// Session storage helpers
// ---------------------------------------------------------------------------

const SESSION_KEY = "quickscribe_search_state";

interface PersistedSearchState {
  question: string;
  result: DeepSearchResult | null;
  tagMap: Record<string, DeepSearchTagMapEntry>;
  candidates: Array<{tag: string; title: string; date: string; score: number; why: string; recording_id: string}>;
  extracts: Array<{tag: string; title: string; date: string; answer: string}>;
  traces: TraceEntry[];
  traceSummary: TraceSummary | null;
}

function saveSearchState(state: PersistedSearchState): void {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(state));
  } catch { /* quota exceeded — ignore */ }
}

function loadSearchState(): PersistedSearchState | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedSearchState;
  } catch {
    return null;
  }
}

function clearSearchState(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

export default function SearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const questionFromUrl = searchParams.get("q") ?? "";
  const [inputValue, setInputValue] = useState(questionFromUrl);
  const [phase, setPhase] = useState<SearchPhase>("idle");
  const [statusMessage, setStatusMessage] = useState("");
  const [result, setResult] = useState<DeepSearchResult | null>(null);
  const [tagMap, setTagMap] = useState<Record<string, DeepSearchTagMapEntry>>({});
  const [errorMessage, setErrorMessage] = useState("");
  const [searchId, setSearchId] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<Array<{tag: string; title: string; date: string; score: number; why: string; recording_id: string}>>([]);
  const [extracts, setExtracts] = useState<Array<{tag: string; title: string; date: string; answer: string}>>([]);
  const [showDetails, setShowDetails] = useState(false);
  const [traces, setTraces] = useState<TraceEntry[]>([]);
  const [traceSummary, setTraceSummary] = useState<TraceSummary | null>(null);
  const closeRef = useRef<(() => void) | null>(null);

  // Refine as Collection dialog state
  const [showCollectionDialog, setShowCollectionDialog] = useState(false);
  const [collectionName, setCollectionName] = useState("");
  const createCollectionMutation = useCreateCollectionFromCandidates();

  // Search history
  const [historyOpen, setHistoryOpen] = useState(false);
  const { data: historyData } = useSearchHistory({ enabled: historyOpen });

  // Restore from sessionStorage on mount if q param matches
  useEffect(() => {
    if (!questionFromUrl) return;
    const saved = loadSearchState();
    if (saved && saved.question === questionFromUrl && saved.result) {
      setResult(saved.result);
      setTagMap(saved.tagMap);
      setCandidates(saved.candidates);
      setExtracts(saved.extracts);
      setTraces(saved.traces ?? []);
      setTraceSummary(saved.traceSummary ?? null);
      setPhase("done");
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const q = inputValue.trim();
      if (!q) return;

      // Cancel any in-progress search
      closeRef.current?.();

      // Clear persisted state for the new search
      clearSearchState();

      setSearchParams({ q });
      setPhase("searching");
      setStatusMessage("Searching recording summaries...");
      setResult(null);
      setTagMap({});
      setErrorMessage("");
      setCandidates([]);
      setExtracts([]);
      setTraces([]);
      setTraceSummary(null);

      const getToken = authEnabled ? getAccessToken : undefined;

      const { close } = deepSearch(
        q,
        (event) => {
          switch (event.event) {
            case "status":
              setStatusMessage(event.data);
              // Detect phase from message content
              if (event.data.includes("Extracting")) setPhase("extracting");
              else if (event.data.includes("Synthesizing")) setPhase("synthesizing");
              break;
            case "candidates":
              try {
                const parsed = JSON.parse(event.data);
                setCandidates(parsed);
                setPhase("extracting");
              } catch { /* ignore */ }
              break;
            case "extract":
              try {
                const parsed = JSON.parse(event.data);
                setExtracts((prev) => [...prev, parsed]);
              } catch { /* ignore */ }
              break;
            case "tag_map":
              try {
                const parsed = JSON.parse(event.data);
                setTagMap(parsed);
              } catch { /* ignore parse errors */ }
              break;
            case "trace":
              try {
                const traceEntry: TraceEntry = JSON.parse(event.data);
                setTraces((prev) => [...prev, traceEntry]);
              } catch { /* ignore */ }
              break;
            case "trace_summary":
              try {
                const summary: TraceSummary = JSON.parse(event.data);
                setTraceSummary(summary);
              } catch { /* ignore */ }
              break;
            case "result":
              try {
                const parsed: DeepSearchResult = JSON.parse(event.data);
                setResult(parsed);
                if (parsed.tag_map) setTagMap(parsed.tag_map);
                if (parsed.search_id) setSearchId(parsed.search_id);
                setPhase("done");
              } catch { /* ignore parse errors */ }
              break;
            case "error":
              setErrorMessage(event.data || "An error occurred");
              setPhase("error");
              break;
            case "done":
              if (phase !== "error") setPhase("done");
              break;
          }
        },
        getToken,
      );

      closeRef.current = close;
    },
    [inputValue, setSearchParams, phase],
  );

  // Persist search state to sessionStorage when results arrive
  useEffect(() => {
    if (phase === "done" && result && questionFromUrl) {
      saveSearchState({
        question: questionFromUrl,
        result,
        tagMap,
        candidates,
        extracts,
        traces,
        traceSummary,
      });
    }
  }, [phase, result, tagMap, candidates, extracts, traces, traceSummary, questionFromUrl]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSearch(e as unknown as React.FormEvent);
      }
    },
    [handleSearch],
  );

  const loadHistoryItem = useCallback(
    (item: SearchHistoryItem) => {
      setHistoryOpen(false);
      setInputValue(item.question);
      setSearchParams({ q: item.question });
      setPhase("done");
      setResult({
        answer: item.answer || "",
        tag_map: {},
        sources: [],
        search_id: item.search_id,
      });
      setTagMap({});
      setCandidates([]);
      setExtracts([]);
      setTraces([]);
      setTraceSummary(null);
      setErrorMessage("");
      setStatusMessage("");
    },
    [setSearchParams],
  );

  const isSearching = phase === "searching" || phase === "extracting" || phase === "synthesizing";

  return (
    <div className="flex h-full flex-col">
      {/* Search bar */}
      <div className="border-b p-4">
        <form onSubmit={handleSearch} className="mx-auto flex max-w-3xl gap-2">
          <div className="relative flex-1">
            <Sparkles className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question across all your recordings..."
              className="w-full rounded-md border border-input bg-background px-10 py-2.5 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 min-h-[42px] max-h-[120px] resize-none"
              rows={1}
              autoFocus
            />
          </div>
          <Button type="submit" disabled={!inputValue.trim() || isSearching}>
            {isSearching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            <span className="ml-1.5">Search</span>
          </Button>
          <Popover open={historyOpen} onOpenChange={setHistoryOpen}>
            <PopoverTrigger render={<Button variant="outline" size="icon" type="button" title="Search history" />}>
                <Clock className="h-4 w-4" />
            </PopoverTrigger>
            <PopoverContent align="end" className="w-96 p-0">
              <div className="border-b px-3 py-2">
                <h4 className="text-sm font-medium">Search History</h4>
              </div>
              <ScrollArea className="max-h-80">
                {historyData?.data && historyData.data.length > 0 ? (
                  <div className="divide-y">
                    {historyData.data.map((item) => (
                      <button
                        key={item.search_id}
                        onClick={() => loadHistoryItem(item)}
                        className="flex w-full flex-col gap-1 px-3 py-2.5 text-left hover:bg-muted/50 transition-colors"
                      >
                        <p className="text-sm font-medium leading-tight line-clamp-2">
                          {item.question}
                        </p>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>
                            {formatDistanceToNow(new Date(item.created_at + "Z"), {
                              addSuffix: true,
                            })}
                          </span>
                          <span>·</span>
                          <span>
                            {(
                              (item.total_prompt_tokens ?? 0) +
                              (item.total_completion_tokens ?? 0)
                            ).toLocaleString()}{" "}
                            tokens
                          </span>
                          {!item.answer && (
                            <>
                              <span>·</span>
                              <span className="text-amber-500">no answer</span>
                            </>
                          )}
                        </div>
                        {item.answer_preview && (
                          <p className="text-xs text-muted-foreground line-clamp-1">
                            {item.answer_preview}
                          </p>
                        )}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                    No search history yet
                  </p>
                )}
              </ScrollArea>
            </PopoverContent>
          </Popover>
        </form>
      </div>

      {/* Content area */}
      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl space-y-4 p-4">
          {/* Empty state */}
          {phase === "idle" && !result && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Sparkles className="mb-4 h-12 w-12 text-muted-foreground/30" />
              <h2 className="text-lg font-medium">Deep Search</h2>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Ask natural language questions across all your recordings.
                The AI will search through summaries, drill into relevant transcripts,
                and synthesize an answer with citations.
              </p>
              <div className="mt-6 space-y-1.5 text-left text-xs text-muted-foreground/80">
                <p>Try questions like:</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>"When did we decide to change the deployment strategy?"</li>
                  <li>"What action items came out of last week's meetings?"</li>
                  <li>"Summarize all discussions about Project Aurora"</li>
                </ul>
              </div>
            </div>
          )}

          {/* Progress indicator */}
          {isSearching && (
            <div className="flex items-center gap-3 rounded-lg border border-dashed p-4">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <div>
                <p className="text-sm font-medium">{phaseLabel(phase)}</p>
                <p className="text-xs text-muted-foreground">{statusMessage}</p>
              </div>
            </div>
          )}

          {/* Error */}
          {phase === "error" && (
            <Card className="border-destructive p-4">
              <p className="text-sm text-destructive">Search failed: {errorMessage}</p>
            </Card>
          )}

          {/* Result */}
          {result && (
            <div className="space-y-4">
              {/* Answer */}
              <Card className="p-5">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <MarkdownWithCitations
                    content={result.answer}
                    tagMap={result.tag_map || tagMap}
                    onTagClick={(recordingId) => navigate(`/recordings/${recordingId}`)}
                  />
                </div>
              </Card>

              {/* Sources */}
              {Object.keys(result.tag_map || tagMap).length > 0 && (
                <div>
                  <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Sources
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(result.tag_map || tagMap).map(([tag, entry]) => (
                      <SourceBadge
                        key={tag}
                        tag={tag}
                        entry={entry}
                        onClick={() => navigate(`/recordings/${entry.recording_id}`)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Pipeline Details (collapsible) */}
              {(candidates.length > 0 || extracts.length > 0 || traces.length > 0) && (
                <div>
                  <button
                    onClick={() => setShowDetails(!showDetails)}
                    className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", showDetails && "rotate-90")} />
                    Pipeline Details
                  </button>

                  {showDetails && (
                    <div className="mt-3 space-y-4">
                      {/* Candidates from Tier 1 */}
                      {candidates.length > 0 && (
                        <div>
                          <h4 className="mb-2 text-xs font-semibold text-muted-foreground">
                            Tier 1 — Candidate Recordings ({candidates.length})
                          </h4>
                          <div className="space-y-1">
                            {candidates.map((c) => (
                              <div
                                key={c.tag}
                                className="flex items-start gap-2 rounded border px-3 py-2 text-xs cursor-pointer hover:bg-muted/50"
                                onClick={() => c.recording_id && navigate(`/recordings/${c.recording_id}`)}
                              >
                                <Badge variant="outline" className="shrink-0 font-mono text-[10px]">
                                  {c.tag}
                                </Badge>
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center gap-2">
                                    <span className="font-medium truncate">{c.title}</span>
                                    <span className="shrink-0 text-muted-foreground">{c.date}</span>
                                  </div>
                                  <p className="mt-0.5 text-muted-foreground">{c.why}</p>
                                </div>
                                <span className="shrink-0 font-mono font-semibold text-primary">
                                  {Math.round(c.score * 100)}%
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Extracts from Tier 2 */}
                      {extracts.length > 0 && (
                        <div>
                          <h4 className="mb-2 text-xs font-semibold text-muted-foreground">
                            Tier 2 — Per-Recording Extracts ({extracts.length})
                          </h4>
                          <div className="space-y-2">
                            {extracts.map((ext) => (
                              <Card key={ext.tag} className="p-3">
                                <div className="flex items-center gap-2 text-xs">
                                  <Badge variant="outline" className="font-mono text-[10px]">
                                    {ext.tag}
                                  </Badge>
                                  <span className="font-medium">{ext.title}</span>
                                  <span className="text-muted-foreground">{ext.date}</span>
                                </div>
                                <p className="mt-2 text-xs text-muted-foreground whitespace-pre-wrap">
                                  {ext.answer}
                                </p>
                              </Card>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Trace Log */}
                      {traces.length > 0 && (
                        <TraceLogSection traces={traces} traceSummary={traceSummary} searchId={searchId} />
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Refine as Collection button */}
              {candidates.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setCollectionName(
                      inputValue.trim().slice(0, 60) || "New collection",
                    );
                    setShowCollectionDialog(true);
                  }}
                >
                  <FolderOpen className="h-3.5 w-3.5 mr-1.5" />
                  Refine as Collection
                </Button>
              )}
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Refine as Collection dialog */}
      <Dialog open={showCollectionDialog} onOpenChange={setShowCollectionDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save as Collection</DialogTitle>
            <DialogDescription>
              Create a collection from the {candidates.length} candidate recording
              {candidates.length !== 1 ? "s" : ""} found in this search.
              You can refine the collection and run targeted searches on it.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <Input
              value={collectionName}
              onChange={(e) => setCollectionName(e.target.value)}
              placeholder="Collection name"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCollectionDialog(false)}
            >
              Cancel
            </Button>
            <Button
              disabled={!collectionName.trim() || createCollectionMutation.isPending}
              onClick={() => {
                const recordingIds = candidates
                  .map((c) => c.recording_id)
                  .filter(Boolean);
                createCollectionMutation.mutate(
                  { name: collectionName.trim(), recordingIds },
                  {
                    onSuccess: (collection) => {
                      setShowCollectionDialog(false);
                      navigate(`/collections/${collection.id}`);
                    },
                  },
                );
              }}
            >
              {createCollectionMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-1" />
              ) : (
                <FolderOpen className="h-4 w-4 mr-1" />
              )}
              Create Collection
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Trace Log UI
// ---------------------------------------------------------------------------

const TIER_COLORS: Record<string, string> = {
  tier1: "text-blue-600 dark:text-blue-400",
  tier2: "text-green-600 dark:text-green-400",
  tier3: "text-purple-600 dark:text-purple-400",
};

const TIER_BG: Record<string, string> = {
  tier1: "border-blue-300 dark:border-blue-700",
  tier2: "border-green-300 dark:border-green-700",
  tier3: "border-purple-300 dark:border-purple-700",
};

function TraceLogSection({
  traces,
  traceSummary,
  searchId,
}: {
  traces: TraceEntry[];
  traceSummary: TraceSummary | null;
  searchId?: string | null;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-3">
        <h4 className="text-xs font-semibold text-muted-foreground">
          Trace Log ({traces.length} LLM calls)
        </h4>
        {searchId && (
          <span
            className="cursor-pointer font-mono text-[10px] text-muted-foreground/60 hover:text-muted-foreground"
            title="Click to copy search ID"
            onClick={() => navigator.clipboard.writeText(searchId)}
          >
            {searchId.slice(0, 8)}...
          </span>
        )}
      </div>
      <div className="space-y-1.5">
        {traces.map((t, i) => (
          <TraceEntryRow key={i} trace={t} />
        ))}
      </div>

      {/* Summary */}
      {traceSummary && (
        <div className="mt-3 rounded border border-dashed p-3 text-xs text-muted-foreground">
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <span>
              <span className="font-semibold">{traceSummary.total_calls}</span> calls
            </span>
            <span>
              <span className="font-semibold">{traceSummary.total_input_tokens.toLocaleString()}</span> input tokens
            </span>
            <span>
              <span className="font-semibold">{traceSummary.total_output_tokens.toLocaleString()}</span> output tokens
            </span>
            <span>
              <span className="font-semibold">{(traceSummary.total_duration_ms / 1000).toFixed(1)}s</span> total
            </span>
            <span>
              ~$
              {(
                (traceSummary.total_input_tokens * 0.00015 +
                  traceSummary.total_output_tokens * 0.0006) /
                1000
              ).toFixed(4)}{" "}
              est. cost
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function TraceEntryRow({ trace }: { trace: TraceEntry }) {
  const [expanded, setExpanded] = useState(false);
  const tierColor = TIER_COLORS[trace.tier] ?? "text-muted-foreground";
  const tierBorder = TIER_BG[trace.tier] ?? "";

  return (
    <div className={cn("rounded border px-3 py-2 text-xs", tierBorder)}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 text-left"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0" />
        )}
        <span className={cn("font-semibold", tierColor)}>{trace.tier}</span>
        <span className="font-medium">{trace.step}</span>
        <span className="text-muted-foreground">{trace.model}</span>
        <span className="ml-auto flex gap-3 shrink-0 text-muted-foreground">
          <span>{trace.prompt_tokens.toLocaleString()} in</span>
          <span>{trace.completion_tokens.toLocaleString()} out</span>
          <span>{(trace.duration_ms / 1000).toFixed(1)}s</span>
        </span>
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          <div>
            <p className="mb-1 font-semibold text-muted-foreground">Input preview:</p>
            <pre className="whitespace-pre-wrap rounded bg-muted/50 p-2 font-mono text-[11px] max-h-48 overflow-auto">
              {trace.input_preview}
            </pre>
          </div>
          <div>
            <p className="mb-1 font-semibold text-muted-foreground">Output:</p>
            <pre className="whitespace-pre-wrap rounded bg-muted/50 p-2 font-mono text-[11px] max-h-64 overflow-auto">
              {trace.output_raw || trace.output_preview}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}


function phaseLabel(phase: SearchPhase): string {
  switch (phase) {
    case "searching": return "Searching summaries...";
    case "extracting": return "Extracting from transcripts...";
    case "synthesizing": return "Synthesizing answer...";
    default: return "";
  }
}


/**
 * Render Markdown content and replace [[TAG]] citations with clickable badges.
 */
function MarkdownWithCitations({
  content,
}: {
  content: string;
  tagMap: Record<string, DeepSearchTagMapEntry>;
  onTagClick: (recordingId: string) => void;
}) {
  // Strip [[TAG]] citations for now, render clean markdown
  const cleaned = content.replace(/\s*\[\[[A-Z]{2}\d{2}\]\]\s*/g, " ");
  return <ReactMarkdown>{cleaned}</ReactMarkdown>;
}


function SourceBadge({
  tag: _tag,
  entry,
  onClick,
}: {
  tag: string;
  entry: DeepSearchTagMapEntry;
  onClick: () => void;
}) {
  const date = entry.date
    ? formatDistanceToNow(new Date(entry.date), { addSuffix: true })
    : null;
  const speakers = entry.speakers?.join(", ");

  return (
    <Card
      className="cursor-pointer p-3 transition-colors hover:bg-accent/50 max-w-xs"
      onClick={onClick}
    >
      <p className="text-sm font-medium leading-tight">
        {entry.title}
      </p>
      <div className="mt-1 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
        {date && <span>{date}</span>}
        {speakers && (
          <>
            <span>·</span>
            <span>{speakers}</span>
          </>
        )}
      </div>
    </Card>
  );
}
