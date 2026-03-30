import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ArrowLeft } from "lucide-react";
import { LogViewer } from "@/components/jobs/LogViewer";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useSyncRun } from "@/lib/queries";
import { fetchRunLogs } from "@/lib/api";
import type { RunLogEntry, SyncRunStats, SyncRunType } from "@/types/models";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  completed: "default",
  running: "secondary",
  failed: "destructive",
};

const TYPE_LABELS: Record<SyncRunType, string> = {
  plaud_sync: "Plaud Sync",
  speaker_id: "Speaker ID",
  profile_rebuild: "Profile Rebuild",
  transcription_poll: "Transcription Poll",
};

const TYPE_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  plaud_sync: "outline",
  speaker_id: "secondary",
  profile_rebuild: "secondary",
  transcription_poll: "outline",
};

export default function JobDetailPage() {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();

  const { data: job, isLoading, refetch: refetchJob } = useSyncRun(id!);

  // Log polling state
  const [logs, setLogs] = useState<RunLogEntry[]>([]);
  const lastLogIdRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevRunIdRef = useRef<string | null>(null);

  const isRunning = job?.status === "running";

  // Reset logs when selected run changes
  useEffect(() => {
    if (id !== prevRunIdRef.current) {
      setLogs([]);
      lastLogIdRef.current = 0;
      prevRunIdRef.current = id ?? null;
    }
  }, [id]);

  // Fetch logs: once for completed runs, poll for running runs
  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    const fetchAndAppendLogs = async () => {
      try {
        const result = await fetchRunLogs(id, lastLogIdRef.current);
        if (cancelled) return;
        if (result.logs.length > 0) {
          setLogs((prev) => [...prev, ...result.logs]);
          lastLogIdRef.current = result.logs[result.logs.length - 1].id;
        }
      } catch {
        // Silently ignore fetch errors during polling
      }
    };

    const fetchAllLogs = async () => {
      try {
        const result = await fetchRunLogs(id, 0);
        if (cancelled) return;
        setLogs(result.logs);  // Replace, don't append
        if (result.logs.length > 0) {
          lastLogIdRef.current = result.logs[result.logs.length - 1].id;
        }
      } catch {
        // ignore
      }
    };

    if (isRunning) {
      // For running jobs: initial fetch + poll for new logs
      fetchAndAppendLogs();
      intervalRef.current = setInterval(() => {
        fetchAndAppendLogs();
        refetchJob();
      }, 1500);
    } else if (job) {
      // For completed jobs: fetch all logs once (replace, don't append)
      fetchAllLogs();
    }

    return () => {
      cancelled = true;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [id, isRunning, refetchJob]);

  const handleBack = useCallback(() => {
    navigate("/jobs");
  }, [navigate]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Job not found
      </div>
    );
  }

  const startDate = new Date(job.started_at);
  const endDate = job.finished_at ? new Date(job.finished_at) : null;
  const durationMs = endDate
    ? endDate.getTime() - startDate.getTime()
    : null;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Fixed header area */}
      <div className="shrink-0 space-y-4 border-b p-4 md:p-6 md:pb-4">
        {/* Header */}
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
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-mono text-sm font-medium">{job.id.slice(0, 8)}</h1>
              <Badge variant={STATUS_VARIANT[job.status] ?? "secondary"}>
                {job.status}
              </Badge>
              <Badge variant="outline">{job.trigger}</Badge>
              <Badge variant={TYPE_VARIANT[job.type] ?? "outline"}>
                {TYPE_LABELS[job.type] ?? job.type}
              </Badge>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>Started: {format(startDate, "PPp")}</span>
              {endDate && <span>Ended: {format(endDate, "PPp")}</span>}
              {durationMs != null && (
                <span>Duration: {formatDurationMs(durationMs)}</span>
              )}
            </div>
          </div>
        </div>

        {/* Error message */}
        {job.error_message && (
          <Card className="border-destructive bg-destructive/5 p-3">
            <p className="text-sm font-medium text-destructive">Error</p>
            <p className="mt-1 text-sm">{job.error_message}</p>
          </Card>
        )}

        {/* Stats grid */}
        {job.stats && <StatsGrid stats={job.stats} />}
      </div>

      {/* Scrollable log viewer fills remaining space */}
      <div className="min-h-0 flex-1 p-4 md:px-6">
        <h2 className="mb-2 text-sm font-semibold">Logs</h2>
        <Card className="h-[calc(100%-2rem)] overflow-hidden">
          <LogViewer
            logs={logs}
            isLive={isRunning}
          />
        </Card>
      </div>
    </div>
  );
}

function StatsGrid({ stats }: { stats: SyncRunStats }) {
  const entries = Object.entries(stats).filter(
    ([key]) => typeof stats[key] === "number"
  );

  if (entries.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
      {entries.map(([key, value]) => (
        <Card key={key} className="p-3 text-center">
          <p className="text-2xl font-bold tabular-nums">{value}</p>
          <p className="text-xs text-muted-foreground">
            {formatStatLabel(key)}
          </p>
        </Card>
      ))}
    </div>
  );
}

function formatStatLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDurationMs(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}
