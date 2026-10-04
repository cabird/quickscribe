import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ComponentProps } from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import { format } from "date-fns";
import { isAxiosError } from "axios";
import { toast } from "react-toastify";
import { AlertTriangle, Loader2, ScrollText } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useGenerateMinutes, useRecording } from "@/lib/queries";
import { parseTimestampMs } from "@/lib/transcript";

// The detail payload is large (transcript JSON), so poll gently.
const POLL_INTERVAL_MS = 10_000;
// After a start request, keep polling this long even if the server has not
// reported 'generating' yet (409 race, or a refetch already in flight).
const START_GRACE_MS = 30_000;
const TIME_LINK_PREFIX = "#t=";

// "[mm:ss]" or "[h:mm:ss]" inside a text node. Markdown already parses these as
// plain text (no link reference defined), so the brackets are in the value.
const TIMESTAMP_RE = /\[((?:\d+:)?\d{1,3}:\d{2})\]/g;

// Minimal mdast shapes; text inside code/inlineCode is a `value`, not a text
// child, so code spans are never visited.
interface MdText { type: "text"; value: string }
interface MdLink { type: "link"; url: string; children: MdText[] }
interface MdParent { type: string; children?: MdNode[] }
type MdNode = MdText | MdLink | MdParent;

function splitTimestamps(text: MdText): MdNode[] | null {
  const out: MdNode[] = [];
  let last = 0;
  for (const match of text.value.matchAll(TIMESTAMP_RE)) {
    const ms = parseTimestampMs(match[1]);
    if (ms == null) continue;
    const start = match.index ?? 0;
    if (start > last) out.push({ type: "text", value: text.value.slice(last, start) });
    out.push({
      type: "link",
      url: `${TIME_LINK_PREFIX}${ms}`,
      children: [{ type: "text", value: match[1] }],
    });
    last = start + match[0].length;
  }
  if (out.length === 0) return null;
  if (last < text.value.length) out.push({ type: "text", value: text.value.slice(last) });
  return out;
}

function linkifyNode(node: MdParent): void {
  if (!node.children || node.type === "link" || node.type === "linkReference") return;
  const next: MdNode[] = [];
  for (const child of node.children) {
    if (child.type === "text") {
      next.push(...(splitTimestamps(child as MdText) ?? [child]));
    } else {
      linkifyNode(child as MdParent);
      next.push(child);
    }
  }
  node.children = next;
}

/** Remark plugin: turn [mm:ss] / [h:mm:ss] text into "#t=<ms>" links (never inside code). */
function remarkTimestampLinks() {
  return (tree: MdParent) => linkifyNode(tree);
}
const REMARK_PLUGINS = [remarkTimestampLinks];

function errorDetail(err: unknown): string {
  const detail = isAxiosError(err) ? err.response?.data?.detail : undefined;
  return typeof detail === "string" ? detail : "Could not start minutes generation";
}

/**
 * Action-bar button for a recording's detailed minutes: generates them
 * (background job, polled), shows progress/failure, and opens a viewer whose
 * [mm:ss] timestamps jump the audio and transcript to that point.
 */
export function MinutesButton({
  recordingId,
  hasTimedTranscript,
  onJumpToTime,
}: {
  recordingId: string;
  /** Minutes need timestamps; the button is hidden without them. */
  hasTimedTranscript: boolean;
  onJumpToTime: (timeMs: number) => void;
}) {
  const [open, setOpen] = useState(false);
  // Shares the page's recording query; this observer adds polling while a run is in progress.
  const pollUntilRef = useRef(0);
  const { data: recording } = useRecording(recordingId, {
    refetchInterval: (query) =>
      query.state.data?.detailed_minutes_status === "generating" ||
      Date.now() < pollUntilRef.current
        ? POLL_INTERVAL_MS
        : false,
  });
  const { mutate: generateMutate, isPending: generatePending } = useGenerateMinutes();

  const minutes = recording?.detailed_minutes ?? null;
  const status = recording?.detailed_minutes_status ?? null;
  const error = recording?.detailed_minutes_error ?? null;
  const generatedAt = recording?.detailed_minutes_generated_at ?? null;
  const isGenerating = status === "generating" || generatePending;
  const isFailed = status === "failed" && !isGenerating;

  // Toast when a run finishes while this page is open (not for states found on load).
  const prevStatusRef = useRef(status);
  useEffect(() => {
    const prev = prevStatusRef.current;
    prevStatusRef.current = status;
    if (prev !== "generating") return;
    if (status === "ready") toast.success("Detailed minutes are ready");
    else if (status === "failed") toast.error(`Minutes generation failed: ${error || "unknown error"}`);
  }, [status, error]);

  const startGeneration = useCallback(() => {
    generateMutate(recordingId, {
      onSuccess: () => {
        pollUntilRef.current = Date.now() + START_GRACE_MS;
      },
      onError: (err) => toast.error(errorDetail(err)),
    });
  }, [generateMutate, recordingId]);

  const handleClick = useCallback(() => {
    if (minutes) setOpen(true);
    else if (!isGenerating) startGeneration();
  }, [minutes, isGenerating, startGeneration]);

  const handleJump = useCallback(
    (timeMs: number) => {
      setOpen(false);
      onJumpToTime(timeMs);
    },
    [onJumpToTime]
  );

  const markdownComponents = useMemo<Components>(
    () => ({
      a: ({ href, children }: ComponentProps<"a">) => {
        if (href?.startsWith(TIME_LINK_PREFIX)) {
          const ms = Number(href.slice(TIME_LINK_PREFIX.length));
          if (!Number.isFinite(ms) || ms < 0) return <span>{children}</span>;
          return (
            <button
              type="button"
              onClick={() => handleJump(ms)}
              className="font-mono text-[0.9em] font-medium text-primary hover:underline"
              title="Jump to this point"
            >
              [{children}]
            </button>
          );
        }
        return (
          <a href={href} target="_blank" rel="noreferrer">
            {children}
          </a>
        );
      },
    }),
    [handleJump]
  );

  if (!hasTimedTranscript) return null;

  let tooltip: string;
  if (minutes) tooltip = "View detailed minutes";
  else if (isGenerating) tooltip = "Generating detailed minutes…";
  else if (isFailed) tooltip = `Minutes generation failed: ${error || "unknown error"} (click to retry)`;
  else tooltip = "Generate detailed minutes";

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        className={cn("relative h-8 w-8", isFailed && !minutes && "text-amber-500 hover:text-amber-600")}
        onClick={handleClick}
        title={tooltip}
        aria-label={tooltip}
      >
        {isGenerating && !minutes ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : isFailed && !minutes ? (
          <AlertTriangle className="h-4 w-4" />
        ) : (
          <ScrollText className="h-4 w-4" />
        )}
        {isGenerating && minutes && (
          <Loader2 className="absolute right-0.5 top-0.5 h-2.5 w-2.5 animate-spin text-primary" />
        )}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>Detailed Minutes</DialogTitle>
            <DialogDescription>
              {generatedAt
                ? `Generated ${format(new Date(generatedAt), "PPp")}. `
                : ""}
              Click a timestamp to jump to that point in the recording.
            </DialogDescription>
          </DialogHeader>

          {isFailed && error && (
            <p className="flex items-start gap-1.5 rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Last regeneration failed: {error}
            </p>
          )}

          <div className="min-h-0 flex-1 overflow-y-auto pr-2">
            {minutes && (
              <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:scroll-mt-4 prose-h3:mt-5 prose-h3:mb-1.5 prose-ul:my-1.5 prose-li:my-0.5">
                <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={markdownComponents}>
                  {minutes}
                </ReactMarkdown>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={startGeneration} disabled={isGenerating}>
              {isGenerating && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              {isGenerating ? "Regenerating…" : "Regenerate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
