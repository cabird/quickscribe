import { useState, useCallback } from 'react';
import { makeStyles, tokens, Tooltip } from '@fluentui/react-components';
import { Play16Regular, Edit16Regular } from '@fluentui/react-icons';
import { SpeakerDropdown } from './SpeakerDropdown';

// 6 distinct speaker colors - border and name colors
const SPEAKER_COLORS = [
  { border: '#3B82F6', name: '#2563EB' },  // Blue
  { border: '#8B5CF6', name: '#7C3AED' },  // Purple
  { border: '#10B981', name: '#059669' },  // Green
  { border: '#F59E0B', name: '#D97706' },  // Amber
  { border: '#EF4444', name: '#DC2626' },  // Red
  { border: '#6366F1', name: '#4F46E5' },  // Indigo
];

const useStyles = makeStyles({
  entry: {
    display: 'flex',
    gap: '16px',
    marginBottom: '20px',
    paddingLeft: '12px',
    borderLeft: '2px solid #D1D5DB',
    position: 'relative',
  },
  time: {
    width: '50px',
    flexShrink: 0,
    color: '#6B7280',
    fontSize: '13px',
  },
  content: {
    flex: 1,
  },
  speakerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '4px',
  },
  speaker: {
    fontWeight: 600,
    fontSize: '13px',
    cursor: 'default',
  },
  hoverIcons: {
    display: 'flex',
    gap: '4px',
    opacity: 0,
    transition: 'opacity 0.15s',
  },
  hoverIconsVisible: {
    opacity: 1,
  },
  iconButton: {
    padding: '2px',
    cursor: 'pointer',
    color: '#9CA3AF',
    borderRadius: '4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    ':hover': {
      color: '#374151',
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  text: {
    lineHeight: '1.7',
    fontSize: '15px',
    color: '#1f1f1f',
  },
});

interface TranscriptEntryProps {
  speaker: string;           // Display name
  speakerLabel: string;      // Original label (e.g., "Speaker 1")
  fullName?: string;         // Full name for tooltip (e.g., "John Smith")
  text: string;
  time?: string;
  speakerIndex: number;
  startTimeMs?: number;
  hasTimestamp?: boolean;
  onPlayFromTime?: (timeMs: number) => void;
  onSpeakerRename?: (speakerLabel: string, newName: string) => void;
  knownSpeakers?: string[];
}

export function TranscriptEntry({
  speaker,
  speakerLabel,
  fullName,
  text,
  time,
  speakerIndex,
  startTimeMs = 0,
  hasTimestamp = false,
  onPlayFromTime,
  onSpeakerRename,
  knownSpeakers = [],
}: TranscriptEntryProps) {
  const styles = useStyles();
  const colors = SPEAKER_COLORS[speakerIndex % 6];

  const [isHovered, setIsHovered] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // Memoize callback to prevent SpeakerDropdown useEffect from re-running on every render
  const handleDropdownClose = useCallback(() => {
    setIsDropdownOpen(false);
  }, []);

  const handlePlayClick = () => {
    if (hasTimestamp && onPlayFromTime) {
      console.log(`[TranscriptEntry] Play clicked for "${speakerLabel}" at ${startTimeMs}ms`);
      onPlayFromTime(startTimeMs);
    }
  };

  const handleEditClick = () => {
    console.log(`[TranscriptEntry] Edit clicked for "${speakerLabel}"`);
    setIsDropdownOpen(true);
  };

  const handleSelectSpeaker = (name: string) => {
    console.log(`[TranscriptEntry] Selected speaker "${name}" for "${speakerLabel}"`);
    if (onSpeakerRename) {
      onSpeakerRename(speakerLabel, name);
    }
  };

  return (
    <div
      className={styles.entry}
      style={{ borderLeftColor: colors.border }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {time && <div className={styles.time}>{time}</div>}
      <div className={styles.content}>
        <div className={styles.speakerRow}>
          {fullName && fullName !== speaker ? (
            <Tooltip content={fullName} relationship="label">
              <div
                className={styles.speaker}
                style={{ color: colors.name }}
              >
                {speaker}
              </div>
            </Tooltip>
          ) : (
            <div
              className={styles.speaker}
              style={{ color: colors.name }}
            >
              {speaker}
            </div>
          )}

          {/* Hover icons */}
          <div className={`${styles.hoverIcons} ${(isHovered || isDropdownOpen) ? styles.hoverIconsVisible : ''}`}>
            {hasTimestamp && onPlayFromTime && (
              <Tooltip content="Play from here" relationship="label">
                <div className={styles.iconButton} onClick={handlePlayClick}>
                  <Play16Regular />
                </div>
              </Tooltip>
            )}
            {onSpeakerRename && (
              <SpeakerDropdown
                isOpen={isDropdownOpen}
                onClose={handleDropdownClose}
                onSelect={handleSelectSpeaker}
                knownSpeakers={knownSpeakers}
              >
                <Tooltip content="Rename speaker" relationship="label">
                  <div className={styles.iconButton} onClick={handleEditClick}>
                    <Edit16Regular />
                  </div>
                </Tooltip>
              </SpeakerDropdown>
            )}
          </div>
        </div>
        <div className={styles.text}>{text}</div>
      </div>
    </div>
  );
}
