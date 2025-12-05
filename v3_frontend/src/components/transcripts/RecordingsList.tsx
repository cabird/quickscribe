import { makeStyles, Spinner, Text } from '@fluentui/react-components';
import type { Recording } from '../../types';
import { RecordingCard } from './RecordingCard';
import { APP_COLORS } from '../../config/styles';

const useStyles = makeStyles({
  container: {
    minHeight: 0,
    overflowY: 'auto',
    flexShrink: 0,
    backgroundColor: APP_COLORS.listBackground,
    paddingTop: '8px',
  },
  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
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

interface RecordingsListProps {
  recordings: Recording[];
  selectedRecordingId: string | null;
  onRecordingSelect: (recordingId: string) => void;
  loading: boolean;
  width: number;
}

export function RecordingsList({
  recordings,
  selectedRecordingId,
  onRecordingSelect,
  loading,
  width,
}: RecordingsListProps) {
  const styles = useStyles();

  if (loading) {
    return (
      <div className={styles.container} style={{ width: `${width}%` }}>
        <div className={styles.loadingContainer}>
          <Spinner label="Loading recordings..." />
        </div>
      </div>
    );
  }

  if (recordings.length === 0) {
    return (
      <div className={styles.container} style={{ width: `${width}%` }}>
        <div className={styles.emptyState}>
          <Text>No recordings found</Text>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container} style={{ width: `${width}%` }}>
      {recordings.map((recording) => (
        <RecordingCard
          key={recording.id}
          recording={recording}
          isSelected={selectedRecordingId === recording.id}
          onClick={() => onRecordingSelect(recording.id)}
        />
      ))}
    </div>
  );
}
