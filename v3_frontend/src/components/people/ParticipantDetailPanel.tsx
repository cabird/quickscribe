import { useState, useEffect, useCallback } from 'react';
import {
  makeStyles,
  Text,
  tokens,
  Spinner,
  Avatar,
  Badge,
  Card,
  CardHeader,
  Button,
  Input,
  Textarea,
  Switch,
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@fluentui/react-components';
import {
  People24Regular,
  Mail20Regular,
  Briefcase20Regular,
  Building20Regular,
  PersonLink20Regular,
  Calendar20Regular,
  Document20Regular,
  ChevronRight20Regular,
  Edit20Regular,
  Save20Regular,
  Dismiss20Regular,
  Person20Regular,
  Key20Regular,
} from '@fluentui/react-icons';
import type { Participant, Recording, UpdateParticipantRequest } from '../../types';
import { formatDate } from '../../utils/dateUtils';

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

const useStyles = makeStyles({
  container: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    backgroundColor: tokens.colorNeutralBackground1,
  },
  loadingContainer: {
    flex: 1,
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
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
  scrollContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px',
  },
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '16px',
    marginBottom: '24px',
    paddingBottom: '20px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  headerInfo: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    flex: 1,
  },
  nameRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  displayName: {
    fontSize: '22px',
    fontWeight: 600,
    color: '#111827',
  },
  meBadge: {
    backgroundColor: '#10B981',
    color: 'white',
  },
  fullName: {
    fontSize: '14px',
    color: '#6B7280',
  },
  headerActions: {
    display: 'flex',
    gap: '8px',
  },
  section: {
    marginBottom: '24px',
  },
  sectionTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#374151',
    marginBottom: '12px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  infoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '16px',
  },
  infoItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  infoLabel: {
    fontSize: '12px',
    color: '#9CA3AF',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  infoValue: {
    fontSize: '14px',
    color: '#111827',
  },
  infoValueEmpty: {
    fontSize: '14px',
    color: '#9CA3AF',
    fontStyle: 'italic',
  },
  infoValueMono: {
    fontSize: '12px',
    color: '#6B7280',
    fontFamily: 'monospace',
    userSelect: 'all',
  },
  notesBox: {
    backgroundColor: tokens.colorNeutralBackground2,
    padding: '12px',
    borderRadius: '8px',
    fontSize: '14px',
    color: '#4B5563',
    lineHeight: '1.6',
    whiteSpace: 'pre-wrap',
  },
  aliasesList: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
  },
  aliasChip: {
    backgroundColor: tokens.colorNeutralBackground3,
    padding: '4px 10px',
    borderRadius: '12px',
    fontSize: '13px',
    color: '#4B5563',
  },
  statsRow: {
    display: 'flex',
    gap: '24px',
  },
  statItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  statValue: {
    fontSize: '20px',
    fontWeight: 600,
    color: '#111827',
  },
  statLabel: {
    fontSize: '12px',
    color: '#6B7280',
  },
  recordingCard: {
    cursor: 'pointer',
    marginBottom: '8px',
    transition: 'background-color 0.15s',
    ':hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  recordingTitle: {
    fontWeight: 500,
    color: '#111827',
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  recordingMeta: {
    fontSize: '12px',
    color: '#6B7280',
  },
  showAllLink: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    color: tokens.colorBrandForeground1,
    cursor: 'pointer',
    fontSize: '14px',
    marginTop: '8px',
    ':hover': {
      textDecoration: 'underline',
    },
  },
  // Edit mode styles
  editInput: {
    width: '100%',
  },
  editDisplayName: {
    fontSize: '18px',
    fontWeight: 500,
  },
  meToggleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px',
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: '8px',
    marginTop: '16px',
  },
  meToggleLabel: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
  },
  meToggleLabelPrimary: {
    fontSize: '14px',
    fontWeight: 500,
    color: '#111827',
  },
  meToggleLabelSecondary: {
    fontSize: '12px',
    color: '#6B7280',
  },
  aliasInputContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  aliasHint: {
    fontSize: '12px',
    color: '#6B7280',
  },
  savingOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.8)',
    zIndex: 10,
  },
  containerRelative: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    backgroundColor: tokens.colorNeutralBackground1,
    position: 'relative',
  },
});

interface ParticipantDetailPanelProps {
  participant: Participant | null;
  recordings: Recording[];
  totalRecordings: number;
  loading: boolean;
  onRecordingClick?: (recordingId: string) => void;
  onSave?: (participantId: string, updates: UpdateParticipantRequest) => Promise<void>;
  existingMeParticipant?: Participant | null;
  saving?: boolean;
}

export function ParticipantDetailPanel({
  participant,
  recordings,
  totalRecordings,
  loading,
  onRecordingClick,
  onSave,
  existingMeParticipant,
  saving = false,
}: ParticipantDetailPanelProps) {
  const styles = useStyles();
  const [isEditing, setIsEditing] = useState(false);
  const [showMeConfirmDialog, setShowMeConfirmDialog] = useState(false);

  // Edit form state
  const [editForm, setEditForm] = useState<UpdateParticipantRequest>({});

  // Initialize edit form when participant changes or entering edit mode
  useEffect(() => {
    if (participant && isEditing) {
      setEditForm({
        displayName: participant.displayName,
        firstName: participant.firstName || '',
        lastName: participant.lastName || '',
        email: participant.email || '',
        role: participant.role || '',
        organization: participant.organization || '',
        relationshipToUser: participant.relationshipToUser || '',
        notes: participant.notes || '',
        aliases: participant.aliases || [],
        isUser: participant.isUser || false,
      });
    }
  }, [participant, isEditing]);

  // Reset edit mode when participant changes
  useEffect(() => {
    setIsEditing(false);
  }, [participant?.id]);

  const handleEditClick = useCallback(() => {
    if (participant) {
      setEditForm({
        displayName: participant.displayName,
        firstName: participant.firstName || '',
        lastName: participant.lastName || '',
        email: participant.email || '',
        role: participant.role || '',
        organization: participant.organization || '',
        relationshipToUser: participant.relationshipToUser || '',
        notes: participant.notes || '',
        aliases: participant.aliases || [],
        isUser: participant.isUser || false,
      });
      setIsEditing(true);
    }
  }, [participant]);

  const handleCancelEdit = useCallback(() => {
    setIsEditing(false);
    setEditForm({});
  }, []);

  const handleSave = useCallback(async () => {
    if (!participant || !onSave) return;

    // Validate displayName
    if (!editForm.displayName?.trim()) {
      return; // Don't save if displayName is empty
    }

    // Build updates object with only changed fields
    const updates: UpdateParticipantRequest = {};

    if (editForm.displayName !== participant.displayName) {
      updates.displayName = editForm.displayName?.trim();
    }
    if (editForm.firstName !== (participant.firstName || '')) {
      updates.firstName = editForm.firstName?.trim() || undefined;
    }
    if (editForm.lastName !== (participant.lastName || '')) {
      updates.lastName = editForm.lastName?.trim() || undefined;
    }
    if (editForm.email !== (participant.email || '')) {
      updates.email = editForm.email?.trim() || undefined;
    }
    if (editForm.role !== (participant.role || '')) {
      updates.role = editForm.role?.trim() || undefined;
    }
    if (editForm.organization !== (participant.organization || '')) {
      updates.organization = editForm.organization?.trim() || undefined;
    }
    if (editForm.relationshipToUser !== (participant.relationshipToUser || '')) {
      updates.relationshipToUser = editForm.relationshipToUser?.trim() || undefined;
    }
    if (editForm.notes !== (participant.notes || '')) {
      updates.notes = editForm.notes?.trim() || undefined;
    }
    if (JSON.stringify(editForm.aliases) !== JSON.stringify(participant.aliases || [])) {
      updates.aliases = editForm.aliases;
    }
    if (editForm.isUser !== (participant.isUser || false)) {
      updates.isUser = editForm.isUser;
    }

    // Only save if there are changes
    if (Object.keys(updates).length === 0) {
      setIsEditing(false);
      return;
    }

    try {
      await onSave(participant.id, updates);
      setIsEditing(false);
    } catch {
      // Error is already handled by the parent (toast shown)
      // Keep edit mode open so user can retry
    }
  }, [participant, editForm, onSave]);

  const handleMeToggle = useCallback((checked: boolean) => {
    if (checked && existingMeParticipant && existingMeParticipant.id !== participant?.id) {
      // Show confirmation dialog
      setShowMeConfirmDialog(true);
    } else {
      setEditForm(prev => ({ ...prev, isUser: checked }));
    }
  }, [existingMeParticipant, participant?.id]);

  const handleConfirmMeToggle = useCallback(() => {
    setEditForm(prev => ({ ...prev, isUser: true }));
    setShowMeConfirmDialog(false);
  }, []);

  const handleAliasesChange = useCallback((value: string) => {
    // Split by commas and trim each alias
    const aliases = value
      .split(',')
      .map(a => a.trim())
      .filter(a => a.length > 0);
    setEditForm(prev => ({ ...prev, aliases }));
  }, []);

  const handleRecordingClick = (recordingId: string) => {
    if (onRecordingClick) {
      onRecordingClick(recordingId);
    }
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingContainer}>
          <Spinner size="medium" label="Loading details..." />
        </div>
      </div>
    );
  }

  if (!participant) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <People24Regular className={styles.emptyIcon} />
          <Text size={400}>Select a person to view details</Text>
        </div>
      </div>
    );
  }

  const fullName = participant.firstName && participant.lastName
    ? `${participant.firstName} ${participant.lastName}`
    : participant.firstName || participant.lastName || null;

  // Edit mode rendering
  if (isEditing) {
    return (
      <div className={styles.containerRelative}>
        {saving && (
          <div className={styles.savingOverlay}>
            <Spinner size="medium" label="Saving..." />
          </div>
        )}
        <div className={styles.scrollContainer}>
          {/* Header with Edit Actions */}
          <div className={styles.header}>
            <Avatar
              size={72}
              name={participant.displayName}
              initials={getInitials(participant)}
              color="colorful"
            />
            <div className={styles.headerInfo}>
              <Input
                className={styles.editDisplayName}
                value={editForm.displayName || ''}
                onChange={(_, data) => setEditForm(prev => ({ ...prev, displayName: data.value }))}
                placeholder="Display Name (required)"
                required
              />
              {editForm.isUser && (
                <Badge className={styles.meBadge} size="small">Me</Badge>
              )}
            </div>
            <div className={styles.headerActions}>
              <Button
                appearance="primary"
                icon={<Save20Regular />}
                onClick={handleSave}
                disabled={!editForm.displayName?.trim() || saving}
              >
                Save
              </Button>
              <Button
                appearance="subtle"
                icon={<Dismiss20Regular />}
                onClick={handleCancelEdit}
                disabled={saving}
              >
                Cancel
              </Button>
            </div>
          </div>

          {/* Editable Info Section */}
          <div className={styles.section}>
            <Text className={styles.sectionTitle}>Information</Text>
            <div className={styles.infoGrid}>
              <div className={styles.infoItem}>
                <Text className={styles.infoLabel}>
                  <Person20Regular />
                  First Name
                </Text>
                <Input
                  className={styles.editInput}
                  value={editForm.firstName || ''}
                  onChange={(_, data) => setEditForm(prev => ({ ...prev, firstName: data.value }))}
                  placeholder="First name"
                />
              </div>
              <div className={styles.infoItem}>
                <Text className={styles.infoLabel}>
                  <Person20Regular />
                  Last Name
                </Text>
                <Input
                  className={styles.editInput}
                  value={editForm.lastName || ''}
                  onChange={(_, data) => setEditForm(prev => ({ ...prev, lastName: data.value }))}
                  placeholder="Last name"
                />
              </div>
              <div className={styles.infoItem}>
                <Text className={styles.infoLabel}>
                  <Mail20Regular />
                  Email
                </Text>
                <Input
                  className={styles.editInput}
                  value={editForm.email || ''}
                  onChange={(_, data) => setEditForm(prev => ({ ...prev, email: data.value }))}
                  placeholder="email@example.com"
                  type="email"
                />
              </div>
              <div className={styles.infoItem}>
                <Text className={styles.infoLabel}>
                  <Briefcase20Regular />
                  Role
                </Text>
                <Input
                  className={styles.editInput}
                  value={editForm.role || ''}
                  onChange={(_, data) => setEditForm(prev => ({ ...prev, role: data.value }))}
                  placeholder="e.g., Project Manager"
                />
              </div>
              <div className={styles.infoItem}>
                <Text className={styles.infoLabel}>
                  <Building20Regular />
                  Group
                </Text>
                <Input
                  className={styles.editInput}
                  value={editForm.organization || ''}
                  onChange={(_, data) => setEditForm(prev => ({ ...prev, organization: data.value }))}
                  placeholder="e.g., Acme Corp"
                />
              </div>
              <div className={styles.infoItem}>
                <Text className={styles.infoLabel}>
                  <PersonLink20Regular />
                  Relationship
                </Text>
                <Input
                  className={styles.editInput}
                  value={editForm.relationshipToUser || ''}
                  onChange={(_, data) => setEditForm(prev => ({ ...prev, relationshipToUser: data.value }))}
                  placeholder="e.g., Colleague, Client"
                />
              </div>
            </div>
          </div>

          {/* Aliases Section - Editable */}
          <div className={styles.section}>
            <Text className={styles.sectionTitle}>Aliases</Text>
            <div className={styles.aliasInputContainer}>
              <Input
                className={styles.editInput}
                value={(editForm.aliases || []).join(', ')}
                onChange={(_, data) => handleAliasesChange(data.value)}
                placeholder="Add aliases separated by commas"
              />
              <Text className={styles.aliasHint}>
                Separate multiple aliases with commas (e.g., "Johnny, J. Smith, JS")
              </Text>
            </div>
          </div>

          {/* Notes Section - Editable */}
          <div className={styles.section}>
            <Text className={styles.sectionTitle}>Notes</Text>
            <Textarea
              value={editForm.notes || ''}
              onChange={(_, data) => setEditForm(prev => ({ ...prev, notes: data.value }))}
              placeholder="Add notes about this person..."
              resize="vertical"
              style={{ width: '100%', minHeight: '100px' }}
            />
          </div>

          {/* "This is me" Toggle */}
          <div className={styles.section}>
            <div className={styles.meToggleRow}>
              <div className={styles.meToggleLabel}>
                <Text className={styles.meToggleLabelPrimary}>This is me</Text>
                <Text className={styles.meToggleLabelSecondary}>
                  Mark this participant as yourself
                </Text>
              </div>
              <Switch
                checked={editForm.isUser || false}
                onChange={(_, data) => handleMeToggle(data.checked)}
              />
            </div>
          </div>
        </div>

        {/* Confirmation Dialog for "Me" Toggle */}
        <Dialog open={showMeConfirmDialog} onOpenChange={(_, data) => setShowMeConfirmDialog(data.open)}>
          <DialogSurface>
            <DialogBody>
              <DialogTitle>Change "Me" Participant?</DialogTitle>
              <DialogContent>
                <Text>
                  This will remove "Me" status from "{existingMeParticipant?.displayName}".
                  Only one participant can be marked as "Me" at a time.
                </Text>
              </DialogContent>
              <DialogActions>
                <Button appearance="secondary" onClick={() => setShowMeConfirmDialog(false)}>
                  Cancel
                </Button>
                <Button appearance="primary" onClick={handleConfirmMeToggle}>
                  Confirm
                </Button>
              </DialogActions>
            </DialogBody>
          </DialogSurface>
        </Dialog>
      </div>
    );
  }

  // Read-only mode rendering (existing code)
  return (
    <div className={styles.container}>
      <div className={styles.scrollContainer}>
        {/* Header with Avatar */}
        <div className={styles.header}>
          <Avatar
            size={72}
            name={participant.displayName}
            initials={getInitials(participant)}
            color="colorful"
          />
          <div className={styles.headerInfo}>
            <div className={styles.nameRow}>
              <Text className={styles.displayName}>{participant.displayName}</Text>
              {participant.isUser && (
                <Badge className={styles.meBadge} size="small">Me</Badge>
              )}
            </div>
            {fullName && fullName !== participant.displayName && (
              <Text className={styles.fullName}>{fullName}</Text>
            )}
          </div>
          {onSave && (
            <div className={styles.headerActions}>
              <Button
                appearance="subtle"
                icon={<Edit20Regular />}
                onClick={handleEditClick}
              >
                Edit
              </Button>
            </div>
          )}
        </div>

        {/* Info Section */}
        <div className={styles.section}>
          <Text className={styles.sectionTitle}>Information</Text>
          <div className={styles.infoGrid}>
            <div className={styles.infoItem}>
              <Text className={styles.infoLabel}>
                <Mail20Regular />
                Email
              </Text>
              <Text className={participant.email ? styles.infoValue : styles.infoValueEmpty}>
                {participant.email || 'Not set'}
              </Text>
            </div>
            <div className={styles.infoItem}>
              <Text className={styles.infoLabel}>
                <Briefcase20Regular />
                Role
              </Text>
              <Text className={participant.role ? styles.infoValue : styles.infoValueEmpty}>
                {participant.role || 'Not set'}
              </Text>
            </div>
            <div className={styles.infoItem}>
              <Text className={styles.infoLabel}>
                <Building20Regular />
                Group
              </Text>
              <Text className={participant.organization ? styles.infoValue : styles.infoValueEmpty}>
                {participant.organization || 'Not set'}
              </Text>
            </div>
            <div className={styles.infoItem}>
              <Text className={styles.infoLabel}>
                <PersonLink20Regular />
                Relationship
              </Text>
              <Text className={participant.relationshipToUser ? styles.infoValue : styles.infoValueEmpty}>
                {participant.relationshipToUser || 'Not set'}
              </Text>
            </div>
            <div className={styles.infoItem}>
              <Text className={styles.infoLabel}>
                <Calendar20Regular />
                First Seen
              </Text>
              <Text className={styles.infoValue}>
                {formatDate(participant.firstSeen)}
              </Text>
            </div>
            <div className={styles.infoItem}>
              <Text className={styles.infoLabel}>
                <Calendar20Regular />
                Last Seen
              </Text>
              <Text className={styles.infoValue}>
                {formatDate(participant.lastSeen)}
              </Text>
            </div>
            <div className={styles.infoItem}>
              <Text className={styles.infoLabel}>
                <Key20Regular />
                ID
              </Text>
              <Text className={styles.infoValueMono}>
                {participant.id}
              </Text>
            </div>
          </div>
        </div>

        {/* Aliases Section */}
        {participant.aliases && participant.aliases.length > 0 && (
          <div className={styles.section}>
            <Text className={styles.sectionTitle}>Aliases</Text>
            <div className={styles.aliasesList}>
              {participant.aliases.map((alias, index) => (
                <span key={index} className={styles.aliasChip}>{alias}</span>
              ))}
            </div>
          </div>
        )}

        {/* Notes Section */}
        {participant.notes && (
          <div className={styles.section}>
            <Text className={styles.sectionTitle}>Notes</Text>
            <div className={styles.notesBox}>
              {participant.notes}
            </div>
          </div>
        )}

        {/* Stats Section */}
        <div className={styles.section}>
          <Text className={styles.sectionTitle}>Statistics</Text>
          <div className={styles.statsRow}>
            <div className={styles.statItem}>
              <Text className={styles.statValue}>{totalRecordings}</Text>
              <Text className={styles.statLabel}>Total Recordings</Text>
            </div>
          </div>
        </div>

        {/* Recent Recordings Section */}
        <div className={styles.section}>
          <Text className={styles.sectionTitle}>
            <Document20Regular />
            Recent Recordings
          </Text>
          {recordings.length === 0 ? (
            <Text className={styles.infoValueEmpty}>No recordings found</Text>
          ) : (
            <>
              {recordings.map((recording) => (
                <Card
                  key={recording.id}
                  className={styles.recordingCard}
                  onClick={() => handleRecordingClick(recording.id)}
                >
                  <CardHeader
                    header={
                      <Text className={styles.recordingTitle}>
                        {recording.title || recording.original_filename}
                        <ChevronRight20Regular />
                      </Text>
                    }
                    description={
                      <Text className={styles.recordingMeta}>
                        {formatDate(recording.recorded_timestamp || recording.upload_timestamp || '')}
                      </Text>
                    }
                  />
                </Card>
              ))}
              {totalRecordings > recordings.length && (
                <div
                  className={styles.showAllLink}
                  onClick={() => {
                    // TODO: Navigate to filtered recordings view
                  }}
                >
                  <Text>Show all ({totalRecordings})</Text>
                  <ChevronRight20Regular />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
