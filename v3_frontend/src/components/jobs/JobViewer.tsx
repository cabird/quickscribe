import { makeStyles, Text, Spinner, Divider, tokens, Button, Tooltip } from '@fluentui/react-components';
import { Copy24Regular } from '@fluentui/react-icons';
import type { JobExecution } from '../../types';
import { JobLogEntry } from './JobLogEntry';
import { formatDate, formatTime } from '../../utils/dateUtils';
import { showToast } from '../../utils/toast';

const useStyles = makeStyles({
  container: {
    flex: 1,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: 'hidden',
  },
  header: {
    padding: '24px',
    flexShrink: 0,
  },
  headerTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '12px',
  },
  jobId: {
    fontSize: tokens.fontSizeBase500,
    fontWeight: tokens.fontWeightSemibold,
    fontFamily: 'monospace',
  },
  meta: {
    display: 'flex',
    gap: '16px',
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
    marginBottom: '12px',
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
    gap: '8px 24px',
    marginTop: '12px',
  },
  statItem: {
    display: 'flex',
    gap: '8px',
    fontSize: tokens.fontSizeBase200,
  },
  statLabel: {
    color: tokens.colorNeutralForeground2,
  },
  statValue: {
    fontWeight: tokens.fontWeightSemibold,
  },
  divider: {
    flexShrink: 0,
    flexGrow: 0,
    flexBasis: 'auto',
  },
  logsArea: {
    flex: 1,
    minHeight: 0,
    overflowY: 'auto',
    padding: '16px 24px',
    backgroundColor: tokens.colorNeutralBackground2,
  },
  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    padding: '24px',
    textAlign: 'center',
    gap: '12px',
  },
});

interface JobViewerProps {
  job: JobExecution | null;
  loading: boolean;
}

export function JobViewer({ job, loading }: JobViewerProps) {
  const styles = useStyles();

  const handleCopyLogs = async () => {
    if (!job?.logs || job.logs.length === 0) {
      showToast.warning('No logs to copy');
      return;
    }

    try {
      const logsText = job.logs
        .map((log) => `[${log.timestamp}] ${log.level.toUpperCase()}: ${log.message}`)
        .join('\n');
      await navigator.clipboard.writeText(logsText);
      showToast.success('Logs copied to clipboard');
    } catch (error) {
      showToast.error('Failed to copy logs');
    }
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingContainer}>
          <Spinner label="Loading job details..." />
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <Text size={400}>Select a job to view details</Text>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerTop}>
          <Text className={styles.jobId}>{job.id}</Text>
          <Tooltip content="Copy logs to clipboard" relationship="label">
            <Button
              appearance="subtle"
              icon={<Copy24Regular />}
              onClick={handleCopyLogs}
              disabled={!job.logs || job.logs.length === 0}
            />
          </Tooltip>
        </div>

        <div className={styles.meta}>
          <Text>Status: {job.status}</Text>
          <Text>•</Text>
          <Text>Source: {job.triggerSource}</Text>
          <Text>•</Text>
          <Text>
            Started: {formatDate(job.startTime)} {formatTime(job.startTime)}
          </Text>
          {job.endTime && (
            <>
              <Text>•</Text>
              <Text>
                Ended: {formatDate(job.endTime)} {formatTime(job.endTime)}
              </Text>
            </>
          )}
          {job.durationFormatted && (
            <>
              <Text>•</Text>
              <Text>Duration: {job.durationFormatted}</Text>
            </>
          )}
        </div>

        {job.errorMessage && (
          <Text style={{ color: tokens.colorPaletteRedForeground1, marginTop: '8px' }}>
            Error: {job.errorMessage}
          </Text>
        )}

        <div className={styles.statsGrid}>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Transcriptions Checked:</Text>
            <Text className={styles.statValue}>{job.stats.transcriptions_checked}</Text>
          </div>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Transcriptions Completed:</Text>
            <Text className={styles.statValue}>{job.stats.transcriptions_completed}</Text>
          </div>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Recordings Found:</Text>
            <Text className={styles.statValue}>{job.stats.recordings_found}</Text>
          </div>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Recordings Downloaded:</Text>
            <Text className={styles.statValue}>{job.stats.recordings_downloaded}</Text>
          </div>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Recordings Transcoded:</Text>
            <Text className={styles.statValue}>{job.stats.recordings_transcoded}</Text>
          </div>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Recordings Uploaded:</Text>
            <Text className={styles.statValue}>{job.stats.recordings_uploaded}</Text>
          </div>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Recordings Skipped:</Text>
            <Text className={styles.statValue}>{job.stats.recordings_skipped}</Text>
          </div>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Transcriptions Submitted:</Text>
            <Text className={styles.statValue}>{job.stats.transcriptions_submitted}</Text>
          </div>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Errors:</Text>
            <Text
              className={styles.statValue}
              style={{ color: job.stats.errors > 0 ? tokens.colorPaletteRedForeground1 : undefined }}
            >
              {job.stats.errors}
            </Text>
          </div>
          <div className={styles.statItem}>
            <Text className={styles.statLabel}>Chunks Created:</Text>
            <Text className={styles.statValue}>{job.stats.chunks_created}</Text>
          </div>
        </div>
      </div>

      <Divider className={styles.divider} />

      <div className={styles.logsArea}>
        {job.logs && job.logs.length > 0 ? (
          job.logs.map((log, index) => <JobLogEntry key={index} log={log} />)
        ) : (
          <div className={styles.emptyState}>
            <Text>No logs available</Text>
          </div>
        )}
      </div>
    </div>
  );
}
