import { makeStyles, mergeClasses, Text, tokens, Tooltip } from '@fluentui/react-components';
import { Calendar20Regular, Clock20Regular, Timer20Regular, People20Regular } from '@fluentui/react-icons';
import type { Recording } from '../../types';
import { formatDate, formatTime, formatDuration } from '../../utils/dateUtils';
import { truncateText, formatSpeakersList } from '../../utils/formatters';
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
  title: {
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase300,
    marginBottom: '8px',
  },
  metaRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    marginBottom: '4px',
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
  },
  description: {
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground2,
    marginTop: '8px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  tooltipContent: {
    maxWidth: '300px',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  icon: {
    fontSize: '16px',
  },
});

interface RecordingCardProps {
  recording: Recording;
  isSelected: boolean;
  onClick: () => void;
}

export function RecordingCard({ recording, isSelected, onClick }: RecordingCardProps) {
  const styles = useStyles();

  const card = (
    <div
      className={mergeClasses(styles.card, isSelected && styles.cardSelected)}
      onClick={onClick}
    >
      <Text className={styles.title}>
        {recording.title || recording.original_filename}
      </Text>

      {recording.recorded_timestamp && (
        <div className={styles.metaRow}>
          <Calendar20Regular className={styles.icon} />
          <Text>{formatDate(recording.recorded_timestamp)}</Text>
          <Clock20Regular className={styles.icon} />
          <Text>{formatTime(recording.recorded_timestamp)}</Text>
        </div>
      )}

      {recording.duration && (
        <div className={styles.metaRow}>
          <Timer20Regular className={styles.icon} />
          <Text>{formatDuration(recording.duration)}</Text>
        </div>
      )}

      {recording.participants && recording.participants.length > 0 && (
        <div className={styles.metaRow}>
          <People20Regular className={styles.icon} />
          <Text>{formatSpeakersList(recording.participants)}</Text>
        </div>
      )}

      {recording.description && (
        <Text className={styles.description}>
          {truncateText(recording.description, 100)}
        </Text>
      )}
    </div>
  );

  // Wrap card in tooltip if there's a description to show
  if (recording.description) {
    return (
      <Tooltip
        content={<div className={styles.tooltipContent}>{recording.description}</div>}
        relationship="description"
        showDelay={1000}
        positioning="after"
      >
        {card}
      </Tooltip>
    );
  }

  return card;
}
