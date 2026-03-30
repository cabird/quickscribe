import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ClipboardPaste, Download, RefreshCw, Search, Upload, X } from "lucide-react";
import { RecordingCard } from "@/components/recordings/RecordingCard";
import { UploadDialog } from "@/components/recordings/UploadDialog";
import { PasteDialog } from "@/components/recordings/PasteDialog";
import RecordingDetailPage from "./RecordingDetailPage";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useRecordings, useTags } from "@/lib/queries";
import { cn } from "@/lib/utils";
import type { RecordingSummary, Tag } from "@/types/models";

export default function RecordingsPage() {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { id: selectedId } = useParams<{ id: string }>();

  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [dateRange, setDateRange] = useState("all");
  const [tagFilter, setTagFilter] = useState("all");
  const [showUpload, setShowUpload] = useState(false);
  const [showPaste, setShowPaste] = useState(false);

  // Multi-select state
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());

  // Resizable splitter state (percentage of container width for left panel)
  const [splitPercent, setSplitPercent] = useState(35);
  const containerRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const listRef = useRef<HTMLDivElement>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Calculate date_from based on dateRange
  const dateFrom = useMemo(() => {
    if (dateRange === "all") return undefined;
    const now = new Date();
    switch (dateRange) {
      case "week":
        now.setDate(now.getDate() - 7);
        break;
      case "month":
        now.setMonth(now.getMonth() - 1);
        break;
      case "quarter":
        now.setMonth(now.getMonth() - 3);
        break;
    }
    return now.toISOString();
  }, [dateRange]);

  const { data: recordingsResponse, isLoading, refetch } = useRecordings({
    search: debouncedSearch || undefined,
    tag_id: tagFilter !== "all" ? tagFilter : undefined,
    date_from: dateFrom,
  });

  const { data: tagsResponse } = useTags();

  const recordings: RecordingSummary[] = useMemo(
    () => recordingsResponse?.data ?? [],
    [recordingsResponse]
  );

  const tags: Tag[] = useMemo(
    () => tagsResponse ?? [],
    [tagsResponse]
  );

  const virtualizer = useVirtualizer({
    count: recordings.length,
    getScrollElement: () => listRef.current,
    estimateSize: () => 180,
    overscan: 10,
  });

  const handleSelectRecording = useCallback(
    (recording: RecordingSummary) => {
      if (isMobile) {
        navigate(`/recordings/${recording.id}`);
      } else {
        navigate(`/recordings/${recording.id}`, { replace: true });
      }
    },
    [isMobile, navigate]
  );

  // Multi-select handlers
  const handleCheckToggle = useCallback((recordingId: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(recordingId)) {
        next.delete(recordingId);
      } else {
        next.add(recordingId);
      }
      return next;
    });
  }, []);

  const handleDeselectAll = useCallback(() => {
    setCheckedIds(new Set());
  }, []);

  const anyChecked = checkedIds.size > 0;

  // Calculate total token count for checked recordings
  const selectionInfo = useMemo(() => {
    if (checkedIds.size === 0) return { count: 0, tokens: 0 };
    let tokens = 0;
    for (const rec of recordings) {
      if (checkedIds.has(rec.id)) {
        tokens += rec.token_count ?? 0;
      }
    }
    return { count: checkedIds.size, tokens };
  }, [checkedIds, recordings]);

  // Export selected transcripts
  const handleExportSelected = useCallback(() => {
    const selected = recordings.filter((r) => checkedIds.has(r.id));
    if (selected.length === 0) return;

    const lines = selected.map((rec) => {
      const title = rec.title || rec.original_filename;
      return `# ${title}\n(${rec.id})\n`;
    });

    const blob = new Blob([lines.join("\n---\n\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `selected-recordings-${selected.length}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }, [recordings, checkedIds]);

  // Splitter drag handlers
  const handleMouseDown = useCallback(() => {
    isDragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const percent = ((e.clientX - rect.left) / rect.width) * 100;
      // Clamp between 20% and 60%
      setSplitPercent(Math.min(60, Math.max(20, percent)));
    };

    const handleMouseUp = () => {
      if (isDragging.current) {
        isDragging.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  // On mobile, if we have a selectedId, show detail only
  if (isMobile && selectedId) {
    return <RecordingDetailPage />;
  }

  const listPanel = (
    <div className="flex h-full flex-col">
      {/* Action bar */}
      <div className="space-y-2 border-b p-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search recordings..."
              className="pl-9 h-9"
            />
          </div>
          <Button
            variant="outline"
            size="icon"
            className="h-9 w-9 shrink-0"
            onClick={() => refetch()}
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Select value={dateRange} onValueChange={(v) => { if (v !== null) setDateRange(v); }}>
            <SelectTrigger className="h-8 w-[130px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All time</SelectItem>
              <SelectItem value="week">Past week</SelectItem>
              <SelectItem value="month">Past month</SelectItem>
              <SelectItem value="quarter">Past quarter</SelectItem>
            </SelectContent>
          </Select>

          {tags.length > 0 && (
            <Select value={tagFilter} onValueChange={(v) => { if (v !== null) setTagFilter(v); }}>
              <SelectTrigger className="h-8 w-[130px] text-xs">
                <SelectValue placeholder="All tags" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All tags</SelectItem>
                {tags.map((tag) => (
                  <SelectItem key={tag.id} value={tag.id}>
                    {tag.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <div className="ml-auto flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1 text-xs"
              onClick={() => setShowUpload(true)}
            >
              <Upload className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Upload</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1 text-xs"
              onClick={() => setShowPaste(true)}
            >
              <ClipboardPaste className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Paste</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Selection info bar */}
      {anyChecked && (
        <div
          className={cn(
            "flex items-center gap-3 border-b px-3 py-2 text-sm",
            selectionInfo.tokens > 100_000
              ? "bg-amber-50 text-amber-800"
              : "bg-blue-50 text-blue-800"
          )}
        >
          <span className="font-medium">
            {selectionInfo.count} recording{selectionInfo.count !== 1 ? "s" : ""} selected
          </span>
          {selectionInfo.tokens > 0 && (
            <span className="text-xs">
              ({selectionInfo.tokens.toLocaleString()} tokens
              {selectionInfo.tokens > 100_000 && " -- large context"})
            </span>
          )}
          <div className="ml-auto flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={handleExportSelected}
            >
              <Download className="h-3 w-3" />
              Export
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-xs"
              onClick={handleDeselectAll}
            >
              <X className="h-3 w-3" />
              Deselect all
            </Button>
          </div>
        </div>
      )}

      {/* Recording list */}
      {isLoading ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : recordings.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
          <p>No recordings found</p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowUpload(true)}>
              Upload audio
            </Button>
            <Button variant="outline" size="sm" onClick={() => setShowPaste(true)}>
              Paste transcript
            </Button>
          </div>
        </div>
      ) : (
        <div ref={listRef} className="flex-1 overflow-auto">
          <div
            className="relative w-full"
            style={{ height: `${virtualizer.getTotalSize()}px` }}
          >
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const recording = recordings[virtualRow.index];
              return (
                <div
                  key={recording.id}
                  ref={virtualizer.measureElement}
                  data-index={virtualRow.index}
                  className="absolute left-0 top-0 w-full px-2 py-0.5"
                  style={{
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  <RecordingCard
                    recording={recording}
                    isSelected={recording.id === selectedId}
                    isChecked={checkedIds.has(recording.id)}
                    showCheckbox={anyChecked}
                    onClick={() => handleSelectRecording(recording)}
                    onCheckToggle={() => handleCheckToggle(recording.id)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );

  // Mobile: list only
  if (isMobile) {
    return (
      <>
        {listPanel}
        <UploadDialog open={showUpload} onOpenChange={setShowUpload} />
        <PasteDialog open={showPaste} onOpenChange={setShowPaste} />
      </>
    );
  }

  // Desktop: split view with resizable splitter
  return (
    <>
      <div ref={containerRef} className="flex h-full">
        {/* Left panel: recording list */}
        <div className="shrink-0 overflow-hidden" style={{ width: `${splitPercent}%` }}>
          {listPanel}
        </div>

        {/* Draggable splitter */}
        <div
          className="w-1 shrink-0 cursor-col-resize bg-border hover:bg-brand-300 active:bg-brand-400 transition-colors"
          onMouseDown={handleMouseDown}
          role="separator"
          aria-orientation="vertical"
          tabIndex={0}
        />

        {/* Right panel: detail */}
        <div className="min-w-0 flex-1 overflow-hidden">
          {selectedId ? (
            <RecordingDetailPage />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Select a recording to view
            </div>
          )}
        </div>
      </div>
      <UploadDialog open={showUpload} onOpenChange={setShowUpload} />
      <PasteDialog open={showPaste} onOpenChange={setShowPaste} />
    </>
  );
}
