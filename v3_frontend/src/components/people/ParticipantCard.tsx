import { useState } from 'react';
import {
  makeStyles,
  mergeClasses,
  Text,
  tokens,
  Persona,
  Badge,
  Checkbox,
} from '@fluentui/react-components';
import { Calendar20Regular } from '@fluentui/react-icons';
import type { Participant } from '../../types';
import { formatDate } from '../../utils/dateUtils';
import { APP_COLORS } from '../../config/styles';

/**
 * Get initials from first and last name.
 * Falls back to displayName if names aren't available.
 */
function getInitials(participant: Participant): string {
  const first = participant.firstName?.trim();
  const last = participant.lastName?.trim();

  if (first && last) {
    return `${first[0]}${last[0]}`.toUpperCase();
  }
  if (first) {
    return first[0].toUpperCase();
  }
  if (last) {
    return last[0].toUpperCase();
  }
  // Fallback to displayName initials (first two words)
  const words = participant.displayName.trim().split(/\s+/);
  if (words.length >= 2) {
    return `${words[0][0]}${words[1][0]}`.toUpperCase();
  }
  return words[0]?.[0]?.toUpperCase() || '?';
}

/**
 * Get full name if different from display name.
 */
function getFullName(participant: Participant): string | null {
  const first = participant.firstName?.trim();
  const last = participant.lastName?.trim();

  if (first && last) {
    const fullName = `${first} ${last}`;
    if (fullName !== participant.displayName) {
      return fullName;
    }
  }
  return null;
}

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
  fullName: {
    fontSize: '12px',
    color: tokens.colorNeutralForeground2,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    fontStyle: 'italic',
  },
});

interface ParticipantCardProps {
  participant: Participant;
  isSelected: boolean;
  isChecked: boolean;
  onCheckChange: (checked: boolean) => void;
  onClick: (e: React.MouseEvent) => void;
}

export function ParticipantCard({ participant, isSelected, isChecked, onCheckChange, onClick }: ParticipantCardProps) {
  const styles = useStyles();
  const [isHovered, setIsHovered] = useState(false);

  const initials = getInitials(participant);
  const fullName = getFullName(participant);

  // Build secondary text: full name if available, otherwise role or organization
  const secondaryText = fullName || participant.role || participant.organization || undefined;

  const handleClick = (e: React.MouseEvent) => {
    // Ctrl/Cmd + Click toggles selection
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      onCheckChange(!isChecked);
    } else {
      onClick(e);
    }
  };

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCheckChange(!isChecked);
  };

  return (
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
        onClick={handleCheckboxClick}
      >
        <Checkbox checked={isChecked} />
      </div>
      <Persona
        name={participant.displayName}
        secondaryText={secondaryText}
        presence={participant.isUser ? { status: 'available' } : undefined}
        avatar={{ color: 'colorful', initials }}
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

        {/* Show organization if we have it and it wasn't used as secondaryText */}
        {participant.organization && fullName && (
          <Text className={styles.groupText}>{participant.organization}</Text>
        )}
      </div>
    </div>
  );
}
