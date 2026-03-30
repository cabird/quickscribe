import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
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
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  FolderOpen,
  Loader2,
  Plus,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { searchToAdd, searchCollection, downloadCollectionUrl } from "@/lib/api";
import { authEnabled, getAccessToken } from "@/lib/auth";
import {
  useCollections,
  useCollection,
  useCollectionSearches,
  useCreateCollection,
  useUpdateCollection,
  useDeleteCollection,
  useAddItemsToCollection,
  useRemoveItemFromCollection,
} from "@/lib/queries";
import { useIsMobile } from "@/hooks/useIsMobile";
import type {
  SearchToAddResult,
  DeepSearchTagMapEntry,
  DeepSearchResult,
} from "@/types/models";

// ---------------------------------------------------------------------------
// Search phase types (reused from SearchPage)
// ---------------------------------------------------------------------------

type SearchPhase = "idle" | "searching" | "extracting" | "synthesizing" | "done" | "error";

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
// CollectionsPage
// ---------------------------------------------------------------------------

export default function CollectionsPage() {
  const { id: routeId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const isMobile = useIsMobile();

  // -- Collection list state --
  const { data: collections, isLoading: collectionsLoading } = useCollections();
  const [selectedId, setSelectedId] = useState<string | null>(routeId ?? null);

  // Sync route param
  useEffect(() => {
    if (routeId) setSelectedId(routeId);
  }, [routeId]);

  // -- Active collection detail --
  const { data: collectionDetail } = useCollection(selectedId ?? "");
  const { data: searchHistory } = useCollectionSearches(selectedId ?? "");

  // -- Mutations --
  const createMutation = useCreateCollection();
  const updateMutation = useUpdateCollection();
  const deleteMutation = useDeleteCollection();
  const addItemsMutation = useAddItemsToCollection();
  const removeItemMutation = useRemoveItemFromCollection();

  // -- Inline editing --
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [descValue, setDescValue] = useState("");

  useEffect(() => {
    if (collectionDetail) {
      setNameValue(collectionDetail.name);
      setDescValue(collectionDetail.description ?? "");
    }
  }, [collectionDetail]);

  // -- Search-to-add state --
  const [searchQuery, setSearchQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [speakerFilter, setSpeakerFilter] = useState("");
  const [searchResults, setSearchResults] = useState<SearchToAddResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // -- Collection search (deep search) state --
  const [collSearchQuestion, setCollSearchQuestion] = useState("");
  const [collSearchPhase, setCollSearchPhase] = useState<SearchPhase>("idle");
  const [collSearchStatus, setCollSearchStatus] = useState("");
  const [collSearchResult, setCollSearchResult] = useState<DeepSearchResult | null>(null);
  const [collSearchTagMap, setCollSearchTagMap] = useState<Record<string, DeepSearchTagMapEntry>>({});
  const [collSearchError, setCollSearchError] = useState("");
  const [collSearchTraces, setCollSearchTraces] = useState<TraceEntry[]>([]);
  const [collSearchTraceSummary, setCollSearchTraceSummary] = useState<TraceSummary | null>(null);
  const [showCollSearchDetails, setShowCollSearchDetails] = useState(false);
  const closeRef = useRef<(() => void) | null>(null);

  // -- Mobile sidebar visibility --
  const [showSidebar, setShowSidebar] = useState(!isMobile);

  // -- Handlers --

  const handleSelectCollection = useCallback(
    (id: string) => {
      setSelectedId(id);
      navigate(`/collections/${id}`, { replace: true });
      // Reset search state
      setSearchResults([]);
      setCollSearchResult(null);
      setCollSearchPhase("idle");
      if (isMobile) setShowSidebar(false);
    },
    [navigate, isMobile],
  );

  const handleCreateCollection = useCallback(async () => {
    const result = await createMutation.mutateAsync({
      name: "Untitled collection",
    });
    handleSelectCollection(result.id);
  }, [createMutation, handleSelectCollection]);

  const handleSaveName = useCallback(() => {
    if (!selectedId || !nameValue.trim()) return;
    updateMutation.mutate({ id: selectedId, body: { name: nameValue.trim() } });
    setEditingName(false);
  }, [selectedId, nameValue, updateMutation]);

  const handleSaveDescription = useCallback(() => {
    if (!selectedId) return;
    updateMutation.mutate({ id: selectedId, body: { description: descValue.trim() || undefined } });
  }, [selectedId, descValue, updateMutation]);

  const handleDeleteCollection = useCallback(() => {
    if (!selectedId) return;
    deleteMutation.mutate(selectedId, {
      onSuccess: () => {
        setSelectedId(null);
        navigate("/collections", { replace: true });
      },
    });
  }, [selectedId, deleteMutation, navigate]);

  const handleSearchToAdd = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!selectedId) return;
      setIsSearching(true);
      try {
        const results = await searchToAdd(selectedId, {
          query: searchQuery || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          speaker: speakerFilter || undefined,
        });
        setSearchResults(results);
      } catch {
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    },
    [selectedId, searchQuery, dateFrom, dateTo, speakerFilter],
  );

  const handleToggleItem = useCallback(
    (resultItem: SearchToAddResult) => {
      if (!selectedId) return;
      if (resultItem.in_collection) {
        removeItemMutation.mutate(
          { collectionId: selectedId, recordingId: resultItem.id },
          {
            onSuccess: () => {
              setSearchResults((prev) =>
                prev.map((r) =>
                  r.id === resultItem.id ? { ...r, in_collection: false } : r,
                ),
              );
            },
          },
        );
      } else {
        addItemsMutation.mutate(
          { collectionId: selectedId, recordingIds: [resultItem.id] },
          {
            onSuccess: () => {
              setSearchResults((prev) =>
                prev.map((r) =>
                  r.id === resultItem.id ? { ...r, in_collection: true } : r,
                ),
              );
            },
          },
        );
      }
    },
    [selectedId, addItemsMutation, removeItemMutation],
  );

  const handleAddAll = useCallback(() => {
    if (!selectedId) return;
    const idsToAdd = searchResults.filter((r) => !r.in_collection).map((r) => r.id);
    if (idsToAdd.length === 0) return;
    addItemsMutation.mutate(
      { collectionId: selectedId, recordingIds: idsToAdd },
      {
        onSuccess: () => {
          setSearchResults((prev) =>
            prev.map((r) => (idsToAdd.includes(r.id) ? { ...r, in_collection: true } : r)),
          );
        },
      },
    );
  }, [selectedId, searchResults, addItemsMutation]);

  const handleRemoveItem = useCallback(
    (recordingId: string) => {
      if (!selectedId) return;
      removeItemMutation.mutate({ collectionId: selectedId, recordingId });
    },
    [selectedId, removeItemMutation],
  );

  const handleCollectionSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!selectedId || !collSearchQuestion.trim()) return;

      closeRef.current?.();

      setCollSearchPhase("searching");
      setCollSearchStatus("Searching collection recordings...");
      setCollSearchResult(null);
      setCollSearchTagMap({});
      setCollSearchError("");
      setCollSearchTraces([]);
      setCollSearchTraceSummary(null);

      const getToken = authEnabled ? getAccessToken : undefined;

      const { close } = searchCollection(
        selectedId,
        collSearchQuestion.trim(),
        (event) => {
          switch (event.event) {
            case "status":
              setCollSearchStatus(event.data);
              if (event.data.includes("Extracting")) setCollSearchPhase("extracting");
              else if (event.data.includes("Synthesizing")) setCollSearchPhase("synthesizing");
              break;
            case "tag_map":
              try {
                setCollSearchTagMap(JSON.parse(event.data));
              } catch { /* ignore */ }
              break;
            case "trace":
              try {
                setCollSearchTraces((prev) => [...prev, JSON.parse(event.data)]);
              } catch { /* ignore */ }
              break;
            case "trace_summary":
              try {
                setCollSearchTraceSummary(JSON.parse(event.data));
              } catch { /* ignore */ }
              break;
            case "result":
              try {
                const parsed: DeepSearchResult = JSON.parse(event.data);
                setCollSearchResult(parsed);
                if (parsed.tag_map) setCollSearchTagMap(parsed.tag_map);
                setCollSearchPhase("done");
              } catch { /* ignore */ }
              break;
            case "error":
              setCollSearchError(event.data || "An error occurred");
              setCollSearchPhase("error");
              break;
            case "done":
              setCollSearchPhase((prev) => (prev === "error" ? prev : "done"));
              break;
          }
        },
        getToken,
      );

      closeRef.current = close;
    },
    [selectedId, collSearchQuestion],
  );

  const handleCollSearchKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleCollectionSearch(e as unknown as React.FormEvent);
      }
    },
    [handleCollectionSearch],
  );

  const isCollSearching =
    collSearchPhase === "searching" ||
    collSearchPhase === "extracting" ||
    collSearchPhase === "synthesizing";

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const sidebar = (
    <div
      className={cn(
        "flex flex-col border-r bg-muted/30",
        isMobile ? "w-full" : "w-[300px] shrink-0",
      )}
      style={{ height: "100%" }}
    >
      {/* Top: Collection selector */}
      <div className="p-3 space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Collections</h2>
          <Button
            size="sm"
            variant="outline"
            onClick={handleCreateCollection}
            disabled={createMutation.isPending}
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            New
          </Button>
        </div>

        {collectionsLoading && (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        )}

        {collections && collections.length === 0 && (
          <p className="text-xs text-muted-foreground py-2">
            No collections yet. Create one to get started.
          </p>
        )}

        <ScrollArea className="max-h-[160px]">
          <div className="space-y-1">
            {collections?.map((c) => (
              <button
                key={c.id}
                onClick={() => handleSelectCollection(c.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-sm transition-colors hover:bg-accent",
                  selectedId === c.id && "bg-accent font-medium",
                )}
              >
                <FolderOpen className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="truncate flex-1">{c.name}</span>
                <Badge variant="secondary" className="text-[10px] shrink-0">
                  {c.item_count}
                </Badge>
              </button>
            ))}
          </div>
        </ScrollArea>
      </div>

      <Separator />

      {/* Active collection details */}
      {collectionDetail ? (
        <>
          <div className="p-3 space-y-2">
            {/* Editable name */}
            {editingName ? (
              <div className="flex items-center gap-1">
                <Input
                  value={nameValue}
                  onChange={(e) => setNameValue(e.target.value)}
                  onBlur={handleSaveName}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSaveName();
                    if (e.key === "Escape") setEditingName(false);
                  }}
                  className="h-7 text-sm font-semibold"
                  autoFocus
                />
              </div>
            ) : (
              <button
                onClick={() => setEditingName(true)}
                className="text-sm font-semibold hover:underline text-left w-full truncate"
                title="Click to edit"
              >
                {collectionDetail.name}
              </button>
            )}

            {/* Description */}
            <Textarea
              value={descValue}
              onChange={(e) => setDescValue(e.target.value)}
              onBlur={handleSaveDescription}
              placeholder="Add a description..."
              rows={2}
              className="text-xs resize-none"
            />

            {/* Stats + download + delete */}
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {collectionDetail.items.length} item{collectionDetail.items.length !== 1 ? "s" : ""}
              </span>
              <div className="flex items-center gap-0.5">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-1.5"
                  title="Download transcripts as zip"
                  disabled={collectionDetail.items.length === 0}
                  onClick={() => window.open(downloadCollectionUrl(collectionDetail.id), "_blank")}
                >
                  <Download className="h-3 w-3" />
                </Button>
              <AlertDialog>
                <AlertDialogTrigger render={<Button variant="ghost" size="sm" className="h-6 px-1.5 text-destructive hover:text-destructive" />}>
                    <Trash2 className="h-3 w-3" />
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete collection?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will permanently delete "{collectionDetail.name}" and remove all items from it.
                      The recordings themselves will not be deleted.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={handleDeleteCollection}>Delete</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
              </div>
            </div>
          </div>

          <Separator />

          {/* Collection items */}
          <div className="flex-1 min-h-0">
            <ScrollArea className="h-full">
              <div className="p-2 space-y-1">
                {collectionDetail.items.length === 0 && (
                  <p className="text-xs text-muted-foreground px-2 py-4 text-center">
                    Add recordings from the search panel
                  </p>
                )}
                {collectionDetail.items.map((item) => (
                  <div
                    key={item.recording_id}
                    className="group flex items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-accent"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">
                        {item.title || "Untitled"}
                      </p>
                      {item.date && (
                        <p className="text-[10px] text-muted-foreground">
                          {formatDistanceToNow(new Date(item.date), { addSuffix: true })}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => handleRemoveItem(item.recording_id)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded hover:bg-destructive/10"
                      title="Remove from collection"
                    >
                      <X className="h-3 w-3 text-destructive" />
                    </button>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>

          <Separator />

          {/* Collection search (sticky bottom) */}
          <div className="p-3 space-y-2">
            <form onSubmit={handleCollectionSearch}>
              <Textarea
                value={collSearchQuestion}
                onChange={(e) => setCollSearchQuestion(e.target.value)}
                onKeyDown={handleCollSearchKeyDown}
                placeholder="Ask a question about this collection..."
                rows={2}
                className="text-xs resize-none"
              />
              <Button
                type="submit"
                size="sm"
                className="w-full mt-2"
                disabled={
                  !collSearchQuestion.trim() ||
                  collectionDetail.items.length === 0 ||
                  isCollSearching
                }
              >
                {isCollSearching ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5 mr-1" />
                )}
                Search Collection
              </Button>
            </form>

            {/* Query history */}
            {searchHistory && searchHistory.length > 0 && (
              <div className="space-y-1">
                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                  History
                </p>
                <ScrollArea className="max-h-[100px]">
                  {searchHistory.map((h) => (
                    <button
                      key={h.id}
                      onClick={() => setCollSearchQuestion(h.question)}
                      className="w-full text-left text-[11px] text-muted-foreground hover:text-foreground px-1 py-0.5 truncate block"
                      title={h.question}
                    >
                      {h.question}
                    </button>
                  ))}
                </ScrollArea>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-xs text-muted-foreground text-center">
            {collections && collections.length > 0
              ? "Select a collection"
              : "Create a collection to get started"}
          </p>
        </div>
      )}
    </div>
  );

  const mainPane = (
    <div className="flex-1 flex flex-col min-w-0 h-full">
      {!selectedId ? (
        <div className="flex flex-col items-center justify-center flex-1 py-16 text-center px-4">
          <FolderOpen className="mb-4 h-12 w-12 text-muted-foreground/30" />
          <h2 className="text-lg font-medium">Collections</h2>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            Select or create a collection to get started. Collections let you group
            recordings together and run targeted deep searches across them.
          </p>
        </div>
      ) : (
        <>
          {/* Search bar */}
          <div className="border-b p-4">
            <form onSubmit={handleSearchToAdd} className="space-y-2">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search recordings to add..."
                    className="pl-10"
                  />
                </div>
                <Button type="submit" disabled={isSearching}>
                  {isSearching ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                  <span className="ml-1.5 hidden sm:inline">Search</span>
                </Button>
              </div>
              <div className="flex gap-2 flex-wrap">
                <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  placeholder="From"
                  className="h-8 text-xs w-[140px]"
                />
                <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  placeholder="To"
                  className="h-8 text-xs w-[140px]"
                />
                <Input
                  value={speakerFilter}
                  onChange={(e) => setSpeakerFilter(e.target.value)}
                  placeholder="Speaker..."
                  className="h-8 text-xs w-[140px]"
                />
              </div>
            </form>
          </div>

          {/* Results or collection search results */}
          <ScrollArea className="flex-1">
            <div className="p-4 space-y-4">
              {/* Collection search progress */}
              {isCollSearching && (
                <div className="flex items-center gap-3 rounded-lg border border-dashed p-4">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                  <div>
                    <p className="text-sm font-medium">{phaseLabel(collSearchPhase)}</p>
                    <p className="text-xs text-muted-foreground">{collSearchStatus}</p>
                  </div>
                </div>
              )}

              {/* Collection search error */}
              {collSearchPhase === "error" && (
                <Card className="border-destructive p-4">
                  <p className="text-sm text-destructive">Search failed: {collSearchError}</p>
                </Card>
              )}

              {/* Collection search result */}
              {collSearchResult && (
                <div className="space-y-4">
                  <Card className="p-5">
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                      <MarkdownWithCitations
                        content={collSearchResult.answer}
                        tagMap={collSearchResult.tag_map || collSearchTagMap}
                        onTagClick={(recordingId) => navigate(`/recordings/${recordingId}`)}
                      />
                    </div>
                  </Card>

                  {/* Sources */}
                  {Object.keys(collSearchResult.tag_map || collSearchTagMap).length > 0 && (
                    <div>
                      <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Sources
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(collSearchResult.tag_map || collSearchTagMap).map(
                          ([tag, entry]) => (
                            <SourceBadge
                              key={tag}
                              entry={entry}
                              onClick={() => navigate(`/recordings/${entry.recording_id}`)}
                            />
                          ),
                        )}
                      </div>
                    </div>
                  )}

                  {/* Pipeline Details */}
                  {collSearchTraces.length > 0 && (
                    <div>
                      <button
                        onClick={() => setShowCollSearchDetails(!showCollSearchDetails)}
                        className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <ChevronRight
                          className={cn(
                            "h-3.5 w-3.5 transition-transform",
                            showCollSearchDetails && "rotate-90",
                          )}
                        />
                        Pipeline Details
                      </button>

                      {showCollSearchDetails && (
                        <div className="mt-3 space-y-4">
                          <TraceLogSection
                            traces={collSearchTraces}
                            traceSummary={collSearchTraceSummary}
                          />
                        </div>
                      )}
                    </div>
                  )}

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setCollSearchResult(null);
                      setCollSearchPhase("idle");
                      setCollSearchQuestion("");
                    }}
                  >
                    New Question
                  </Button>
                </div>
              )}

              {/* Search-to-add results */}
              {searchResults.length > 0 && !collSearchResult && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      {searchResults.length} recording{searchResults.length !== 1 ? "s" : ""} found
                    </p>
                    <Button variant="outline" size="sm" onClick={handleAddAll}>
                      <Plus className="h-3.5 w-3.5 mr-1" />
                      Add all
                    </Button>
                  </div>
                  {searchResults.map((r) => (
                    <SearchResultCard
                      key={r.id}
                      result={r}
                      onToggle={() => handleToggleItem(r)}
                    />
                  ))}
                </div>
              )}

              {/* Empty states */}
              {searchResults.length === 0 &&
                !collSearchResult &&
                !isCollSearching &&
                collSearchPhase !== "error" && (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <Search className="mb-3 h-8 w-8 text-muted-foreground/30" />
                    <p className="text-sm text-muted-foreground">
                      Search for recordings to add to this collection, or ask a question
                      about the recordings already in it.
                    </p>
                  </div>
                )}
            </div>
          </ScrollArea>
        </>
      )}
    </div>
  );

  if (isMobile) {
    return (
      <div className="flex h-full flex-col">
        {/* Mobile toggle */}
        <div className="flex items-center gap-2 border-b p-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowSidebar(!showSidebar)}
          >
            <FolderOpen className="h-4 w-4 mr-1" />
            {collectionDetail?.name || "Collections"}
            <ChevronDown className="h-3 w-3 ml-1" />
          </Button>
        </div>
        {showSidebar ? sidebar : mainPane}
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {sidebar}
      {mainPane}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SearchResultCard({
  result,
  onToggle,
}: {
  result: SearchToAddResult;
  onToggle: () => void;
}) {
  const date = result.recorded_at
    ? formatDistanceToNow(new Date(result.recorded_at), { addSuffix: true })
    : null;

  return (
    <Card className="p-3 flex items-start gap-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-tight truncate">
          {result.title || result.original_filename}
        </p>
        <div className="mt-1 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
          {date && <span>{date}</span>}
          {result.speaker_names && result.speaker_names.length > 0 && (
            <>
              <span>·</span>
              <span>{result.speaker_names.join(", ")}</span>
            </>
          )}
        </div>
        {result.search_summary_snippet && (
          <p className="mt-1.5 text-xs text-muted-foreground line-clamp-2">
            {result.search_summary_snippet}
          </p>
        )}
      </div>
      <Button
        variant={result.in_collection ? "secondary" : "outline"}
        size="sm"
        onClick={onToggle}
        className={cn(
          "shrink-0",
          result.in_collection && "text-green-600 border-green-200 bg-green-50 hover:bg-green-100 dark:bg-green-950 dark:hover:bg-green-900 dark:border-green-800",
        )}
      >
        {result.in_collection ? (
          <>
            <Check className="h-3.5 w-3.5 mr-1" />
            Added
          </>
        ) : (
          <>
            <Plus className="h-3.5 w-3.5 mr-1" />
            Add
          </>
        )}
      </Button>
    </Card>
  );
}

function SourceBadge({
  entry,
  onClick,
}: {
  entry: DeepSearchTagMapEntry;
  onClick: () => void;
}) {
  const date = entry.date
    ? formatDistanceToNow(new Date(entry.date), { addSuffix: true })
    : null;

  return (
    <Card
      className="cursor-pointer p-3 transition-colors hover:bg-accent/50 max-w-xs"
      onClick={onClick}
    >
      <p className="text-sm font-medium leading-tight">{entry.title}</p>
      <div className="mt-1 flex flex-wrap gap-1.5 text-xs text-muted-foreground">
        {date && <span>{date}</span>}
        {entry.speakers && entry.speakers.length > 0 && (
          <>
            <span>·</span>
            <span>{entry.speakers.join(", ")}</span>
          </>
        )}
      </div>
    </Card>
  );
}

function MarkdownWithCitations({
  content,
  tagMap,
  onTagClick,
}: {
  content: string;
  tagMap: Record<string, DeepSearchTagMapEntry>;
  onTagClick: (recordingId: string) => void;
}) {
  const TAG_REGEX = /\[\[([A-Z]{2}\d{2})\]\]/g;

  const parts: (string | { tag: string; entry: DeepSearchTagMapEntry | undefined })[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = TAG_REGEX.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index));
    }
    parts.push({ tag: match[1], entry: tagMap[match[1]] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex));
  }

  return (
    <>
      {parts.map((part, i) => {
        if (typeof part === "string") {
          return <ReactMarkdown key={i}>{part}</ReactMarkdown>;
        }
        const { tag, entry } = part;
        return (
          <Badge
            key={i}
            variant="secondary"
            className="mx-0.5 cursor-pointer text-xs hover:bg-primary/20 inline"
            title={entry ? `${entry.title}${entry.date ? ` (${entry.date})` : ""}` : tag}
            onClick={() => entry && onTagClick(entry.recording_id)}
          >
            {entry ? entry.title.slice(0, 30) + (entry.title.length > 30 ? "..." : "") : tag}
          </Badge>
        );
      })}
    </>
  );
}

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
}: {
  traces: TraceEntry[];
  traceSummary: TraceSummary | null;
}) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold text-muted-foreground">
        Trace Log ({traces.length} LLM calls)
      </h4>
      <div className="space-y-1.5">
        {traces.map((t, i) => (
          <TraceEntryRow key={i} trace={t} />
        ))}
      </div>
      {traceSummary && (
        <div className="mt-3 rounded border border-dashed p-3 text-xs text-muted-foreground">
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <span>
              <span className="font-semibold">{traceSummary.total_calls}</span> calls
            </span>
            <span>
              <span className="font-semibold">{traceSummary.total_input_tokens.toLocaleString()}</span>{" "}
              input tokens
            </span>
            <span>
              <span className="font-semibold">{traceSummary.total_output_tokens.toLocaleString()}</span>{" "}
              output tokens
            </span>
            <span>
              <span className="font-semibold">{(traceSummary.total_duration_ms / 1000).toFixed(1)}s</span>{" "}
              total
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
    case "searching":
      return "Searching collection...";
    case "extracting":
      return "Extracting from transcripts...";
    case "synthesizing":
      return "Synthesizing answer...";
    default:
      return "";
  }
}
