import { makeStyles, mergeClasses, Text, tokens, Badge } from '@fluentui/react-components';
import { Clock20Regular, Timer20Regular, ErrorCircle20Regular, Checkmark20Regular, DocumentText20Regular, Mic20Regular } from '@fluentui/react-icons';
import type { JobExecution } from '../../types';
import { formatDate, formatTime } from '../../utils/dateUtils';
import { APP_COLORS } from '../../config/styles';

const useStyles = makeStyles({
  card: {
    padding: '12px 16px',
    cursor: 'pointer',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    transition: 'background-color 0.2s',
    ':hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  cardSelected: {
    backgroundColor: tokens.colorNeutralBackground1Selected,
    borderLeft: `4px solid ${APP_COLORS.selectionBorder}`,
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  jobId: {
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase300,
    fontFamily: 'monospace',
  },
  metaRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    marginBottom: '4px',
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
  },
  statsRow: {
    display: 'flex',
    gap: '12px',
    marginTop: '8px',
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground2,
  },
  icon: {
    fontSize: '16px',
  },
  errorMessage: {
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorPaletteRedForeground1,
    marginTop: '8px',
  },
});

interface JobCardProps {
  job: JobExecution;
  isSelected: boolean;
  onClick: () => void;
}

export function JobCard({ job, isSelected, onClick }: JobCardProps) {
  const styles = useStyles();

  const getStatusBadge = () => {
    switch (job.status) {
      case 'completed':
        return <Badge appearance="outline" color="success" icon={<Checkmark20Regular />}>Completed</Badge>;
      case 'failed':
        return <Badge appearance="filled" color="danger" icon={<ErrorCircle20Regular />}>Failed</Badge>;
      case 'running':
        return <Badge appearance="filled" color="informative">Running</Badge>;
      default:
        return null;
    }
  };

  const getTriggerBadge = () => {
    return job.triggerSource === 'scheduled' ? (
      <Badge appearance="outline">Scheduled</Badge>
    ) : (
      <Badge appearance="outline">Manual</Badge>
    );
  };

  const hasActivity =
    job.stats.recordings_uploaded > 0 ||
    job.stats.transcriptions_completed > 0 ||
    job.stats.errors > 0;

  return (
    <div
      className={mergeClasses(styles.card, isSelected && styles.cardSelected)}
      onClick={onClick}
    >
      <div className={styles.header}>
        <Text className={styles.jobId}>{job.id.substring(0, 8)}</Text>
        <div style={{ display: 'flex', gap: '8px' }}>
          {getTriggerBadge()}
          {getStatusBadge()}
        </div>
      </div>

      <div className={styles.metaRow}>
        <Clock20Regular className={styles.icon} />
        <Text>{formatDate(job.startTime)}</Text>
        <Text>{formatTime(job.startTime)}</Text>
      </div>

      {job.durationFormatted && (
        <div className={styles.metaRow}>
          <Timer20Regular className={styles.icon} />
          <Text>{job.durationFormatted}</Text>
        </div>
      )}

      {hasActivity && (
        <div className={styles.statsRow}>
          {job.stats.recordings_uploaded > 0 && (
            <div className={styles.metaRow}>
              <Mic20Regular className={styles.icon} />
              <Text>
                {job.stats.recordings_uploaded} {job.stats.recordings_uploaded === 1 ? 'recording' : 'recordings'} processed
              </Text>
            </div>
          )}
          {job.stats.transcriptions_completed > 0 && (
            <div className={styles.metaRow}>
              <DocumentText20Regular className={styles.icon} />
              <Text>
                {job.stats.transcriptions_completed} {job.stats.transcriptions_completed === 1 ? 'transcription' : 'transcriptions'} processed
              </Text>
            </div>
          )}
          {job.stats.errors > 0 && (
            <div className={styles.metaRow}>
              <ErrorCircle20Regular className={styles.icon} />
              <Text style={{ color: tokens.colorPaletteRedForeground1 }}>
                {job.stats.errors} {job.stats.errors === 1 ? 'error' : 'errors'}
              </Text>
            </div>
          )}
        </div>
      )}

      {job.errorMessage && (
        <Text className={styles.errorMessage}>{job.errorMessage}</Text>
      )}
    </div>
  );
}
