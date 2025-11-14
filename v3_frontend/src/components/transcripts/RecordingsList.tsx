import { makeStyles, Spinner, Text } from '@fluentui/react-components';
import type { Recording } from '../../types';
import { RecordingCard } from './RecordingCard';

const useStyles = makeStyles({
  container: {
    width: '35%',
    height: '100%',
    overflowY: 'auto',
    borderRight: '1px solid #e0e0e0',
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
}

export function RecordingsList({
  recordings,
  selectedRecordingId,
  onRecordingSelect,
  loading,
}: RecordingsListProps) {
  const styles = useStyles();

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingContainer}>
          <Spinner label="Loading recordings..." />
        </div>
      </div>
    );
  }

  if (recordings.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <Text>No recordings found</Text>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
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
