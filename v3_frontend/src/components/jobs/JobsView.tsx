import { useState, useMemo, useCallback } from 'react';
import { makeStyles } from '@fluentui/react-components';
import { JobsFilterBar } from './JobsFilterBar';
import { JobsList } from './JobsList';
import { JobViewer } from './JobViewer';
import { ResizableSplitter } from '../layout/ResizableSplitter';
import { useJobs } from '../../hooks/useJobs';
import { useJobDetails } from '../../hooks/useJobDetails';
import { jobsService } from '../../services/jobsService';
import { showToast } from '../../utils/toast';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minHeight: 0,
  },
  viewContainer: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
    minHeight: 0,
  },
});

export function JobsView() {
  const styles = useStyles();
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [listPanelWidth, setListPanelWidth] = useState(35); // percentage

  // Filter state
  const [minDuration, setMinDuration] = useState<number | undefined>(undefined);
  const [hasActivity, setHasActivity] = useState(true);
  const [status, setStatus] = useState('');
  const [triggerSource, setTriggerSource] = useState('');
  const [isSyncing, setIsSyncing] = useState(false);

  // Build filters object
  const filters = useMemo(
    () => ({
      limit: 50,
      min_duration: minDuration,
      has_activity: hasActivity ? true : undefined, // undefined = show all jobs
      status: status || undefined,
      trigger_source: (triggerSource as 'scheduled' | 'manual' | undefined) || undefined,
      sort_by: 'startTime' as const,
      sort_order: 'desc' as const,
    }),
    [minDuration, hasActivity, status, triggerSource]
  );

  const { jobs, loading, hasMore, loadMore, refetch } = useJobs(filters);
  const { jobDetails, loading: jobLoading } = useJobDetails(selectedJobId);

  const handleResize = useCallback((delta: number) => {
    setListPanelWidth((prev) => {
      const containerWidth = window.innerWidth - 68; // Subtract nav rail width
      const deltaPercent = (delta / containerWidth) * 100;
      const newWidth = prev + deltaPercent;
      return Math.max(20, Math.min(60, newWidth));
    });
  }, []);

  const handleTriggerSync = useCallback(async () => {
    setIsSyncing(true);
    try {
      const response = await jobsService.triggerPlaudSync();
      if (response.status === 'success') {
        showToast.success(response.message || 'Plaud sync triggered successfully');
        // Refresh the job list after a short delay to allow the job to appear
        setTimeout(() => {
          refetch();
        }, 2000);
      } else {
        showToast.error(response.message || 'Failed to trigger Plaud sync');
      }
    } catch (error: unknown) {
      console.error('Failed to trigger Plaud sync:', error);
      // Extract error message from axios error response or fall back to generic message
      let errorMessage = 'Failed to trigger Plaud sync';
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { data?: { error?: string; message?: string } } };
        errorMessage = axiosError.response?.data?.error
          || axiosError.response?.data?.message
          || errorMessage;
      }
      showToast.error(errorMessage);
    } finally {
      setIsSyncing(false);
    }
  }, [refetch]);

  return (
    <div className={styles.container}>
      <JobsFilterBar
        minDuration={minDuration}
        hasActivity={hasActivity}
        status={status}
        triggerSource={triggerSource}
        onMinDurationChange={setMinDuration}
        onHasActivityChange={setHasActivity}
        onStatusChange={setStatus}
        onTriggerSourceChange={setTriggerSource}
        onRefresh={refetch}
        onTriggerSync={handleTriggerSync}
        isSyncing={isSyncing}
      />
      <div className={styles.viewContainer}>
        <JobsList
          jobs={jobs}
          selectedJobId={selectedJobId}
          onJobSelect={setSelectedJobId}
          loading={loading}
          hasMore={hasMore}
          onLoadMore={loadMore}
          width={listPanelWidth}
        />
        <ResizableSplitter onResize={handleResize} />
        <JobViewer job={jobDetails} loading={jobLoading} />
      </div>
    </div>
  );
}
