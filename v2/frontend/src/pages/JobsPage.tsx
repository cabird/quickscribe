import { useCallback, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Play, RefreshCw, Radio } from "lucide-react";
import { JobCard } from "@/components/jobs/JobCard";
import JobDetailPage from "./JobDetailPage";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useSyncRuns, useTriggerSync, usePollTranscriptions } from "@/lib/queries";
import type { SyncRunStatus, SyncRunTrigger, SyncRunType, SyncRunSummary } from "@/types/models";

export default function JobsPage() {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { id: selectedId } = useParams<{ id: string }>();

  const [statusFilter, setStatusFilter] = useState("all");
  const [triggerFilter, setTriggerFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const filters = useMemo(() => {
    const f: { status?: SyncRunStatus; trigger?: SyncRunTrigger; type?: SyncRunType } = {};
    if (statusFilter !== "all") f.status = statusFilter as SyncRunStatus;
    if (triggerFilter !== "all") f.trigger = triggerFilter as SyncRunTrigger;
    if (typeFilter !== "all") f.type = typeFilter as SyncRunType;
    return f;
  }, [statusFilter, triggerFilter, typeFilter]);

  const { data: syncRunsResponse, isLoading, refetch } = useSyncRuns(filters);
  const triggerSyncMutation = useTriggerSync();
  const pollMutation = usePollTranscriptions();

  const jobs: SyncRunSummary[] = useMemo(
    () => syncRunsResponse?.data ?? [],
    [syncRunsResponse],
  );

  const handleSelectJob = useCallback(
    (job: SyncRunSummary) => {
      if (isMobile) {
        navigate(`/jobs/${job.id}`);
      } else {
        navigate(`/jobs/${job.id}`, { replace: true });
      }
    },
    [isMobile, navigate]
  );

  const handleSyncNow = useCallback(async () => {
    await triggerSyncMutation.mutateAsync();
    // Refetch at multiple intervals to catch the job once it starts
    setTimeout(() => refetch(), 2000);
    setTimeout(() => refetch(), 5000);
    setTimeout(() => refetch(), 10000);
  }, [triggerSyncMutation, refetch]);

  const handlePollNow = useCallback(async () => {
    await pollMutation.mutateAsync();
    setTimeout(() => refetch(), 2000);
  }, [pollMutation, refetch]);

  // On mobile, if we have a selectedId, show detail only
  if (isMobile && selectedId) {
    return <JobDetailPage />;
  }

  const listPanel = (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Action buttons */}
      <div className="flex items-center gap-1.5 border-b px-3 py-2">
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1 text-xs"
          onClick={handleSyncNow}
          disabled={triggerSyncMutation.isPending}
        >
          <Play className="h-3.5 w-3.5" />
          Sync Now
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-1 text-xs"
          onClick={handlePollNow}
          disabled={pollMutation.isPending}
        >
          <Radio className="h-3.5 w-3.5" />
          Poll Now
        </Button>
        <div className="flex-1" />
        <Button
          variant="outline"
          size="icon"
          className="h-8 w-8"
          onClick={() => refetch()}
          title="Refresh"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-1.5 border-b px-3 py-2">
        <Select value={statusFilter} onValueChange={(v) => { if (v !== null) setStatusFilter(v); }}>
          <SelectTrigger className="h-7 w-[110px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All status</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="aborted">Aborted</SelectItem>
          </SelectContent>
        </Select>

        <Select value={triggerFilter} onValueChange={(v) => { if (v !== null) setTriggerFilter(v); }}>
          <SelectTrigger className="h-7 w-[110px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All triggers</SelectItem>
            <SelectItem value="scheduled">Scheduled</SelectItem>
            <SelectItem value="manual">Manual</SelectItem>
          </SelectContent>
        </Select>

        <Select value={typeFilter} onValueChange={(v) => { if (v !== null) setTypeFilter(v); }}>
          <SelectTrigger className="h-7 w-[110px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            <SelectItem value="plaud_sync">Plaud Sync</SelectItem>
            <SelectItem value="speaker_id">Speaker ID</SelectItem>
            <SelectItem value="profile_rebuild">Profile Rebuild</SelectItem>
            <SelectItem value="transcription_poll">Transcription Poll</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Job list */}
      {isLoading ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : jobs.length === 0 ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          No sync jobs found
        </div>
      ) : (
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-0.5 p-2">
            {jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                isSelected={job.id === selectedId}
                onClick={() => handleSelectJob(job)}
              />
            ))}
          </div>
        </ScrollArea>
      )}
    </div>
  );

  // Mobile: list only
  if (isMobile) {
    return listPanel;
  }

  // Desktop: split view
  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex h-full w-[380px] shrink-0 flex-col overflow-hidden border-r">{listPanel}</div>
      <div className="min-w-0 flex-1 overflow-hidden">
        {selectedId ? (
          <JobDetailPage />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Select a job to view details
          </div>
        )}
      </div>
    </div>
  );
}
