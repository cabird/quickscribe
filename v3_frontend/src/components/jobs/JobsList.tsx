import { useEffect, useRef } from 'react';
import { makeStyles, Spinner, Text } from '@fluentui/react-components';
import type { JobExecution } from '../../types';
import { JobCard } from './JobCard';

const useStyles = makeStyles({
  container: {
    minHeight: 0,
    overflowY: 'auto',
    flexShrink: 0,
  },
  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: '24px',
  },
  emptyState: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    padding: '24px',
    textAlign: 'center',
  },
});

interface JobsListProps {
  jobs: JobExecution[];
  selectedJobId: string | null;
  onJobSelect: (jobId: string) => void;
  loading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
  width: number;
}

export function JobsList({
  jobs,
  selectedJobId,
  onJobSelect,
  loading,
  hasMore,
  onLoadMore,
  width,
}: JobsListProps) {
  const styles = useStyles();
  const containerRef = useRef<HTMLDivElement>(null);

  // Infinite scroll handler
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      // Load more when within 100px of bottom
      if (scrollHeight - scrollTop - clientHeight < 100 && hasMore && !loading) {
        onLoadMore();
      }
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [hasMore, loading, onLoadMore]);

  if (jobs.length === 0 && !loading) {
    return (
      <div className={styles.container} style={{ width: `${width}%` }}>
        <div className={styles.emptyState}>
          <Text>No jobs found</Text>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container} style={{ width: `${width}%` }} ref={containerRef}>
      {jobs.map((job) => (
        <JobCard
          key={job.id}
          job={job}
          isSelected={selectedJobId === job.id}
          onClick={() => onJobSelect(job.id)}
        />
      ))}
      {loading && (
        <div className={styles.loadingContainer}>
          <Spinner size="small" label="Loading..." />
        </div>
      )}
    </div>
  );
}
