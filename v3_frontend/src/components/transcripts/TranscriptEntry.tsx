import { useState, useCallback } from 'react';
import { makeStyles, tokens, Tooltip } from '@fluentui/react-components';
import { Play16Regular, Pause16Regular, Edit16Regular } from '@fluentui/react-icons';
import { SpeakerDropdown } from './SpeakerDropdown';
import { SpeakerConfidenceBadge } from './SpeakerConfidenceBadge';
import type { TopCandidate } from '../../types';

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
  endTimeMs?: number;
  hasTimestamp?: boolean;
  isAudioPlaying?: boolean;  // Whether audio is currently playing
  currentTimeMs?: number;    // Current playback position in ms
  onPlayFromTime?: (timeMs: number) => void;
  onPause?: () => void;
  onSpeakerRename?: (speakerLabel: string, newName: string) => void;
  knownSpeakers?: string[];
  // Speaker identification props
  identificationStatus?: 'auto' | 'suggest' | 'unknown' | 'dismissed';
  confidence?: number;
  suggestedName?: string;
  topCandidates?: TopCandidate[];
  useForTraining?: boolean;
  onAcceptSuggestion?: (speakerLabel: string) => void;
  onRejectSuggestion?: (speakerLabel: string) => void;
  onSelectCandidate?: (speakerLabel: string, participantId: string) => void;
  onToggleTraining?: (speakerLabel: string) => void;
}

export function TranscriptEntry({
  speaker,
  speakerLabel,
  fullName,
  text,
  time,
  speakerIndex,
  startTimeMs = 0,
  endTimeMs = 0,
  hasTimestamp = false,
  isAudioPlaying = false,
  currentTimeMs = 0,
  onPlayFromTime,
  onPause,
  onSpeakerRename,
  knownSpeakers = [],
  identificationStatus,
  confidence,
  suggestedName,
  topCandidates,
  useForTraining,
  onAcceptSuggestion,
  onRejectSuggestion,
  onSelectCandidate,
  onToggleTraining,
}: TranscriptEntryProps) {
  const styles = useStyles();
  const colors = SPEAKER_COLORS[speakerIndex % 6];

  const [isHovered, setIsHovered] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // Check if this entry is currently being played
  const isThisEntryPlaying = isAudioPlaying &&
    currentTimeMs >= startTimeMs &&
    (endTimeMs === 0 || currentTimeMs < endTimeMs);

  // Memoize callback to prevent SpeakerDropdown useEffect from re-running on every render
  const handleDropdownClose = useCallback(() => {
    setIsDropdownOpen(false);
  }, []);

  const handlePlayPauseClick = () => {
    if (isThisEntryPlaying && onPause) {
      console.log(`[TranscriptEntry] Pause clicked for "${speakerLabel}"`);
      onPause();
    } else if (hasTimestamp && onPlayFromTime) {
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

          {/* Speaker identification badge */}
          {identificationStatus && (
            <SpeakerConfidenceBadge
              identificationStatus={identificationStatus}
              similarity={confidence}
              suggestedName={suggestedName}
              topCandidates={topCandidates}
              useForTraining={useForTraining}
              onAcceptSuggestion={onAcceptSuggestion ? () => onAcceptSuggestion(speakerLabel) : undefined}
              onRejectSuggestion={onRejectSuggestion ? () => onRejectSuggestion(speakerLabel) : undefined}
              onSelectCandidate={onSelectCandidate ? (pid) => onSelectCandidate(speakerLabel, pid) : undefined}
              onToggleTraining={onToggleTraining ? () => onToggleTraining(speakerLabel) : undefined}
            />
          )}

          {/* Hover icons */}
          <div className={`${styles.hoverIcons} ${(isHovered || isDropdownOpen) ? styles.hoverIconsVisible : ''}`}>
            {hasTimestamp && onPlayFromTime && (
              <Tooltip content={isThisEntryPlaying ? 'Pause' : 'Play from here'} relationship="label">
                <div className={styles.iconButton} onClick={handlePlayPauseClick}>
                  {isThisEntryPlaying ? <Pause16Regular /> : <Play16Regular />}
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
