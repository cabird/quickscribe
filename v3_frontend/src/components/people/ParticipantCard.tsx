import {
  makeStyles,
  mergeClasses,
  Text,
  tokens,
  Persona,
  Badge,
} from '@fluentui/react-components';
import { Calendar20Regular } from '@fluentui/react-icons';
import type { Participant } from '../../types';
import { formatDate } from '../../utils/dateUtils';
import { APP_COLORS } from '../../config/styles';

const useStyles = makeStyles({
  card: {
    position: 'relative',
    padding: '12px 16px',
    margin: '0 8px 8px 8px',
    cursor: 'pointer',
    backgroundColor: APP_COLORS.cardBackground,
    borderRadius: '8px',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08)',
    transition: 'background-color 0.15s, box-shadow 0.15s',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    ':hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
      boxShadow: '0 2px 6px rgba(0, 0, 0, 0.12)',
    },
  },
  cardSelected: {
    backgroundColor: '#EBF5FF',
    borderLeft: `4px solid ${APP_COLORS.selectionBorder}`,
    boxShadow: '0 2px 6px rgba(0, 0, 0, 0.1)',
    ':hover': {
      backgroundColor: '#E0F0FF',
    },
  },
  contentWrapper: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  topRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  meBadge: {
    backgroundColor: tokens.colorBrandBackground,
    color: tokens.colorNeutralForegroundOnBrand,
  },
  metaRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
  },
  icon: {
    fontSize: '14px',
    color: '#9CA3AF',
  },
  groupText: {
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
});

interface ParticipantCardProps {
  participant: Participant;
  isSelected: boolean;
  onClick: () => void;
}

export function ParticipantCard({ participant, isSelected, onClick }: ParticipantCardProps) {
  const styles = useStyles();

  // Build secondary text: role or organization
  const secondaryText = participant.role || participant.organization || undefined;

  return (
    <div
      className={mergeClasses(
        styles.card,
        isSelected && styles.cardSelected
      )}
      onClick={onClick}
    >
      <Persona
        name={participant.displayName}
        secondaryText={secondaryText}
        presence={participant.isUser ? { status: 'available' } : undefined}
        avatar={{ color: 'colorful' }}
        size="medium"
      />

      <div className={styles.contentWrapper}>
        <div className={styles.topRow}>
          {participant.isUser && (
            <Badge className={styles.meBadge} size="small" appearance="filled">
              Me
            </Badge>
          )}
        </div>

        <div className={styles.metaRow}>
          <Calendar20Regular className={styles.icon} />
          <Text size={200}>Last seen: {formatDate(participant.lastSeen)}</Text>
        </div>

        {participant.organization && participant.organization !== secondaryText && (
          <Text className={styles.groupText}>{participant.organization}</Text>
        )}
      </div>
    </div>
  );
}
