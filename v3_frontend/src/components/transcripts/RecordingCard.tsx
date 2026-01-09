import { useState } from 'react';
import { makeStyles, mergeClasses, Text, tokens, Tooltip, Checkbox } from '@fluentui/react-components';
import { Calendar20Regular, Clock20Regular, Timer20Regular, People20Regular, NumberSymbol20Regular } from '@fluentui/react-icons';
import type { Recording } from '../../types';
import { formatDate, formatTime, formatDuration } from '../../utils/dateUtils';
import { truncateText, formatSpeakersList, formatTokenCount } from '../../utils/formatters';
import { APP_COLORS } from '../../config/styles';

const useStyles = makeStyles({
  card: {
    position: 'relative',
    padding: '14px 16px',
    margin: '0 8px 8px 8px',
    cursor: 'pointer',
    backgroundColor: APP_COLORS.cardBackground,
    borderRadius: '8px',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08)',
    transition: 'background-color 0.15s, box-shadow 0.15s, transform 0.15s',
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
  cardChecked: {
    backgroundColor: '#EBF5FF',
    borderLeft: `4px solid ${APP_COLORS.selectionBorder}`,
    boxShadow: '0 2px 6px rgba(0, 0, 0, 0.1)',
    ':hover': {
      backgroundColor: '#E0F0FF',
    },
  },
  checkboxContainer: {
    position: 'absolute',
    top: '8px',
    right: '8px',
    zIndex: 1,
    opacity: 0,
    transition: 'opacity 0.15s',
  },
  checkboxVisible: {
    opacity: 1,
  },
  title: {
    fontWeight: 600,
    fontSize: '15px',
    color: '#111827',
    marginBottom: '10px',
    lineHeight: '1.3',
  },
  metaRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    marginBottom: '6px',
    fontSize: '13px',
    color: '#6B7280',
  },
  description: {
    fontSize: '13px',
    color: '#4B5563',
    marginTop: '10px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    lineHeight: '1.5',
  },
  tooltipContent: {
    maxWidth: '300px',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  icon: {
    fontSize: '14px',
    color: '#9CA3AF',
  },
});

interface RecordingCardProps {
  recording: Recording;
  isSelected: boolean;  // For viewer selection (single)
  isChecked: boolean;   // For multi-select
  onCheckChange: (checked: boolean) => void;
  onClick: (e: React.MouseEvent) => void;
}

export function RecordingCard({ recording, isSelected, isChecked, onCheckChange, onClick }: RecordingCardProps) {
  const styles = useStyles();
  const [isHovered, setIsHovered] = useState(false);

  const handleClick = (e: React.MouseEvent) => {
    // Ctrl/Cmd + Click toggles selection
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      onCheckChange(!isChecked);
    } else {
      onClick(e);
    }
  };

  const handleCheckboxChange = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCheckChange(!isChecked);
  };

  const card = (
    <div
      className={mergeClasses(
        styles.card,
        isSelected && styles.cardSelected,
        isChecked && styles.cardChecked
      )}
      onClick={handleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Checkbox - visible on hover or when checked */}
      <div
        className={mergeClasses(
          styles.checkboxContainer,
          (isHovered || isChecked) && styles.checkboxVisible
        )}
        onClick={handleCheckboxChange}
      >
        <Checkbox checked={isChecked} />
      </div>
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

      {(recording.duration || recording.token_count) && (
        <div className={styles.metaRow}>
          {recording.duration && (
            <>
              <Timer20Regular className={styles.icon} />
              <Text>{formatDuration(recording.duration)}</Text>
            </>
          )}
          {recording.token_count && (
            <>
              {recording.duration && <Text style={{ margin: '0 4px' }}>•</Text>}
              <NumberSymbol20Regular className={styles.icon} />
              <Text>{formatTokenCount(recording.token_count)}</Text>
            </>
          )}
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
