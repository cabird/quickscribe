import { makeStyles, Text, tokens } from '@fluentui/react-components';
import { People24Regular } from '@fluentui/react-icons';

const useStyles = makeStyles({
  container: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    backgroundColor: tokens.colorNeutralBackground1,
  },
  emptyState: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    gap: '16px',
    color: tokens.colorNeutralForeground3,
  },
  emptyIcon: {
    fontSize: '48px',
    color: tokens.colorNeutralForeground4,
  },
});

interface ParticipantDetailPanelProps {
  selectedParticipantId: string | null;
}

export function ParticipantDetailPanel({ selectedParticipantId }: ParticipantDetailPanelProps) {
  const styles = useStyles();

  // Phase 1: Just show empty state
  // Phase 2 will implement full detail view
  if (!selectedParticipantId) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <People24Regular className={styles.emptyIcon} />
          <Text size={400}>Select a person to view details</Text>
        </div>
      </div>
    );
  }

  // Placeholder for Phase 2 implementation
  return (
    <div className={styles.container}>
      <div className={styles.emptyState}>
        <Text size={400}>Person details coming in Phase 2</Text>
        <Text size={200}>ID: {selectedParticipantId}</Text>
      </div>
    </div>
  );
}
