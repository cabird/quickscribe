import { makeStyles, Spinner, Text } from '@fluentui/react-components';
import type { Participant } from '../../types';
import { ParticipantCard } from './ParticipantCard';
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
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    padding: '24px',
    textAlign: 'center',
    gap: '8px',
  },
  countBadge: {
    padding: '4px 12px',
    fontSize: '12px',
    color: '#6B7280',
    backgroundColor: '#E5E7EB',
    borderRadius: '12px',
    marginLeft: '8px',
    marginRight: '8px',
    marginBottom: '8px',
  },
});

interface PeopleListProps {
  participants: Participant[];
  selectedParticipantId: string | null;
  onParticipantSelect: (participantId: string) => void;
  loading: boolean;
  width: number;
  totalCount: number;
  checkedParticipantIds: Set<string>;
  onCheckChange: (participantId: string, checked: boolean) => void;
}

export function PeopleList({
  participants,
  selectedParticipantId,
  onParticipantSelect,
  loading,
  width,
  totalCount,
  checkedParticipantIds,
  onCheckChange,
}: PeopleListProps) {
  const styles = useStyles();

  if (loading) {
    return (
      <div className={styles.container} style={{ width: `${width}%` }}>
        <div className={styles.loadingContainer}>
          <Spinner label="Loading people..." />
        </div>
      </div>
    );
  }

  if (participants.length === 0) {
    return (
      <div className={styles.container} style={{ width: `${width}%` }}>
        <div className={styles.emptyState}>
          <Text weight="semibold">No people found</Text>
          <Text size={200}>Try adjusting your search or filters</Text>
        </div>
      </div>
    );
  }

  const showingFiltered = participants.length !== totalCount;

  return (
    <div className={styles.container} style={{ width: `${width}%` }}>
      {showingFiltered && (
        <div className={styles.countBadge}>
          Showing {participants.length} of {totalCount}
        </div>
      )}
      {participants.map((participant) => (
        <ParticipantCard
          key={participant.id}
          participant={participant}
          isSelected={selectedParticipantId === participant.id}
          isChecked={checkedParticipantIds.has(participant.id)}
          onCheckChange={(checked) => onCheckChange(participant.id, checked)}
          onClick={() => onParticipantSelect(participant.id)}
        />
      ))}
    </div>
  );
}
