import { useState } from 'react';
import { makeStyles, mergeClasses, tokens, Tooltip, Button } from '@fluentui/react-components';
import {
  Checkmark12Regular,
  QuestionCircle12Regular,
  Dismiss12Regular,
  BrainCircuit20Regular,
} from '@fluentui/react-icons';
import type { TopCandidate } from '../../types';

const useStyles = makeStyles({
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '3px',
    padding: '1px 6px',
    borderRadius: '10px',
    fontSize: '11px',
    fontWeight: 500,
    cursor: 'default',
    lineHeight: '16px',
    verticalAlign: 'middle',
  },
  auto: {
    backgroundColor: '#DCFCE7',
    color: '#166534',
  },
  suggest: {
    backgroundColor: '#FEF3C7',
    color: '#92400E',
    cursor: 'pointer',
  },
  unknown: {
    backgroundColor: '#F3F4F6',
    color: '#6B7280',
    cursor: 'pointer',
  },
  candidateChips: {
    display: 'flex',
    gap: '4px',
    flexWrap: 'wrap',
    marginTop: '2px',
  },
  candidateChip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '3px',
    padding: '1px 8px',
    borderRadius: '12px',
    fontSize: '11px',
    fontWeight: 500,
    cursor: 'pointer',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
    transition: 'all 0.15s',
    ':hover': {
      backgroundColor: tokens.colorBrandBackground2,
    },
  },
  candidateSim: {
    fontSize: '10px',
    color: tokens.colorNeutralForeground3,
  },
  actions: {
    display: 'inline-flex',
    gap: '2px',
    marginLeft: '4px',
  },
  actionButton: {
    minWidth: '20px',
    width: '20px',
    height: '20px',
    padding: '2px',
  },
  trainingBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '2px',
    padding: '1px 5px',
    borderRadius: '10px',
    fontSize: '11px',
    fontWeight: 500,
    cursor: 'pointer',
    lineHeight: '16px',
  },
  trainingEnabled: {
    backgroundColor: '#DBEAFE',
    color: '#1E40AF',
  },
  trainingDisabled: {
    backgroundColor: '#F3F4F6',
    color: '#9CA3AF',
  },
});

interface SpeakerConfidenceBadgeProps {
  identificationStatus?: 'auto' | 'suggest' | 'unknown' | 'dismissed';
  similarity?: number;
  suggestedName?: string;
  topCandidates?: TopCandidate[];
  useForTraining?: boolean;
  onAcceptSuggestion?: () => void;
  onRejectSuggestion?: () => void;
  onSelectCandidate?: (participantId: string) => void;
  onToggleTraining?: () => void;
}

export function SpeakerConfidenceBadge({
  identificationStatus,
  similarity,
  suggestedName,
  topCandidates = [],
  useForTraining,
  onAcceptSuggestion,
  onRejectSuggestion,
  onSelectCandidate,
  onToggleTraining,
}: SpeakerConfidenceBadgeProps) {
  const styles = useStyles();
  const [showCandidates, setShowCandidates] = useState(false);

  if (!identificationStatus) return null;

  const pct = similarity ? `${Math.round(similarity * 100)}%` : '';

  if (identificationStatus === 'auto') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
        <Tooltip content={`Auto-identified (${pct})`} relationship="label">
          <span className={mergeClasses(styles.badge, styles.auto)}>
            <Checkmark12Regular />
            {pct}
          </span>
        </Tooltip>
        {onToggleTraining && (
          <Tooltip
            content={useForTraining ? 'Approved for voice training — click to revoke' : 'Not used for voice training — click to approve'}
            relationship="label"
          >
            <span
              className={mergeClasses(
                styles.trainingBadge,
                useForTraining ? styles.trainingEnabled : styles.trainingDisabled
              )}
              onClick={onToggleTraining}
            >
              <BrainCircuit20Regular style={{ width: 12, height: 12 }} />
            </span>
          </Tooltip>
        )}
      </span>
    );
  }

  if (identificationStatus === 'suggest') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
        <Tooltip content={`Suggested: ${suggestedName || 'unknown'} (${pct})`} relationship="label">
          <span
            className={mergeClasses(styles.badge, styles.suggest)}
            onClick={() => setShowCandidates(!showCandidates)}
          >
            <QuestionCircle12Regular />
            {suggestedName || '?'}
          </span>
        </Tooltip>
        {onAcceptSuggestion && (
          <span className={styles.actions}>
            <Tooltip content="Accept suggestion" relationship="label">
              <Button
                appearance="subtle"
                size="small"
                className={styles.actionButton}
                icon={<Checkmark12Regular />}
                onClick={onAcceptSuggestion}
              />
            </Tooltip>
            <Tooltip content="Reject suggestion" relationship="label">
              <Button
                appearance="subtle"
                size="small"
                className={styles.actionButton}
                icon={<Dismiss12Regular />}
                onClick={onRejectSuggestion}
              />
            </Tooltip>
          </span>
        )}
        {showCandidates && topCandidates.length > 0 && (
          <div className={styles.candidateChips}>
            {topCandidates.slice(0, 5).map((c) => (
              <span
                key={c.participantId}
                className={styles.candidateChip}
                onClick={() => onSelectCandidate?.(c.participantId)}
              >
                {c.displayName || c.participantId.substring(0, 8)}
                <span className={styles.candidateSim}>{Math.round(c.similarity * 100)}%</span>
              </span>
            ))}
          </div>
        )}
      </span>
    );
  }

  // unknown
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
      <Tooltip content="Unknown speaker" relationship="label">
        <span
          className={mergeClasses(styles.badge, styles.unknown)}
          onClick={() => setShowCandidates(!showCandidates)}
        >
          <QuestionCircle12Regular />
          ?
        </span>
      </Tooltip>
      {showCandidates && topCandidates.length > 0 && (
        <div className={styles.candidateChips}>
          {topCandidates.slice(0, 5).map((c) => (
            <span
              key={c.participantId}
              className={styles.candidateChip}
              onClick={() => onSelectCandidate?.(c.participantId)}
            >
              {c.displayName || c.participantId.substring(0, 8)}
              <span className={styles.candidateSim}>{Math.round(c.similarity * 100)}%</span>
            </span>
          ))}
        </div>
      )}
    </span>
  );
}
