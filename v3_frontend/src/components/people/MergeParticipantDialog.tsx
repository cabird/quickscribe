import { useState, useMemo, useCallback } from 'react';
import {
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Text,
  Spinner,
  Input,
  makeStyles,
  tokens,
  Persona,
} from '@fluentui/react-components';
import { Search20Regular, ArrowRight20Regular } from '@fluentui/react-icons';
import type { Participant } from '../../types';

const useStyles = makeStyles({
  searchInput: {
    width: '100%',
    marginBottom: '16px',
  },
  participantList: {
    maxHeight: '300px',
    overflowY: 'auto',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: '4px',
  },
  participantItem: {
    display: 'flex',
    alignItems: 'center',
    padding: '12px',
    cursor: 'pointer',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    ':hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
    ':last-child': {
      borderBottom: 'none',
    },
  },
  participantItemSelected: {
    backgroundColor: '#EBF5FF',
    ':hover': {
      backgroundColor: '#E0F0FF',
    },
  },
  mergePreview: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    padding: '16px',
    marginTop: '16px',
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: '8px',
  },
  mergeArrow: {
    color: tokens.colorBrandForeground1,
    fontSize: '24px',
  },
  emptyState: {
    padding: '24px',
    textAlign: 'center',
    color: tokens.colorNeutralForeground3,
  },
  warningText: {
    marginTop: '12px',
    color: '#6B7280',
    fontSize: '13px',
    display: 'block',
  },
});

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

interface MergeParticipantDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  primaryParticipant: Participant | null;
  participants: Participant[];
  onConfirm: (secondaryId: string) => void;
  saving: boolean;
}

export function MergeParticipantDialog({
  open,
  onOpenChange,
  primaryParticipant,
  participants,
  onConfirm,
  saving,
}: MergeParticipantDialogProps) {
  const styles = useStyles();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSecondaryId, setSelectedSecondaryId] = useState<string | null>(null);

  // Filter out the primary participant and search
  const availableParticipants = useMemo(() => {
    if (!primaryParticipant) return [];

    return participants.filter(p => {
      // Exclude the primary participant
      if (p.id === primaryParticipant.id) return false;

      // Filter by search query
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const matchesName = p.displayName.toLowerCase().includes(query);
        const matchesFirstName = p.firstName?.toLowerCase().includes(query);
        const matchesLastName = p.lastName?.toLowerCase().includes(query);
        const matchesAlias = p.aliases.some(a => a.toLowerCase().includes(query));
        return matchesName || matchesFirstName || matchesLastName || matchesAlias;
      }

      return true;
    });
  }, [participants, primaryParticipant, searchQuery]);

  const selectedSecondary = useMemo(() => {
    if (!selectedSecondaryId) return null;
    return participants.find(p => p.id === selectedSecondaryId) || null;
  }, [participants, selectedSecondaryId]);

  const handleClose = useCallback(() => {
    if (!saving) {
      setSearchQuery('');
      setSelectedSecondaryId(null);
      onOpenChange(false);
    }
  }, [saving, onOpenChange]);

  const handleConfirm = useCallback(() => {
    if (selectedSecondaryId) {
      onConfirm(selectedSecondaryId);
    }
  }, [selectedSecondaryId, onConfirm]);

  // Reset selection when dialog opens/closes
  const handleOpenChange = useCallback((newOpen: boolean) => {
    if (!newOpen) {
      setSearchQuery('');
      setSelectedSecondaryId(null);
    }
    onOpenChange(newOpen);
  }, [onOpenChange]);

  if (!primaryParticipant) return null;

  return (
    <Dialog open={open} onOpenChange={(_, data) => handleOpenChange(data.open)}>
      <DialogSurface style={{ maxWidth: '500px' }}>
        <DialogBody>
          <DialogTitle>Merge Participant</DialogTitle>
          <DialogContent>
            <Text>
              Select a participant to merge into "{primaryParticipant.displayName}".
              The selected participant will be deleted and their data combined.
            </Text>

            <Input
              className={styles.searchInput}
              placeholder="Search participants..."
              contentBefore={<Search20Regular />}
              value={searchQuery}
              onChange={(_, data) => setSearchQuery(data.value)}
              style={{ marginTop: '16px' }}
            />

            <div className={styles.participantList}>
              {availableParticipants.length === 0 ? (
                <div className={styles.emptyState}>
                  {searchQuery ? 'No matching participants found' : 'No other participants available'}
                </div>
              ) : (
                availableParticipants.map(participant => (
                  <div
                    key={participant.id}
                    className={`${styles.participantItem} ${
                      selectedSecondaryId === participant.id ? styles.participantItemSelected : ''
                    }`}
                    onClick={() => setSelectedSecondaryId(participant.id)}
                  >
                    <Persona
                      name={participant.displayName}
                      secondaryText={participant.organization || participant.role}
                      avatar={{ color: 'colorful', initials: getInitials(participant) }}
                      size="medium"
                    />
                  </div>
                ))
              )}
            </div>

            {selectedSecondary && (
              <div className={styles.mergePreview}>
                <Persona
                  name={selectedSecondary.displayName}
                  avatar={{ color: 'colorful', initials: getInitials(selectedSecondary) }}
                  size="small"
                />
                <ArrowRight20Regular className={styles.mergeArrow} />
                <Persona
                  name={primaryParticipant.displayName}
                  avatar={{ color: 'colorful', initials: getInitials(primaryParticipant) }}
                  size="small"
                />
              </div>
            )}

            <Text className={styles.warningText}>
              Merging will combine aliases, notes, and update timestamps. Recording speaker mappings will be updated to point to the primary participant.
            </Text>
          </DialogContent>
          <DialogActions>
            <Button
              appearance="secondary"
              onClick={handleClose}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              appearance="primary"
              onClick={handleConfirm}
              disabled={saving || !selectedSecondaryId}
            >
              {saving ? <Spinner size="tiny" /> : 'Merge'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
