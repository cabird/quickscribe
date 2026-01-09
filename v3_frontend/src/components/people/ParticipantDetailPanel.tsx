import { makeStyles, Text, tokens, Spinner, Persona, Badge, Card, CardHeader } from '@fluentui/react-components';
import { People24Regular, Mail20Regular, Briefcase20Regular, Building20Regular, PersonLink20Regular, Calendar20Regular, Document20Regular, ChevronRight20Regular } from '@fluentui/react-icons';
import type { Participant, Recording } from '../../types';
import { formatDate } from '../../utils/dateUtils';

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
});

interface ParticipantDetailPanelProps {
  participant: Participant | null;
  recordings: Recording[];
  totalRecordings: number;
  loading: boolean;
  onRecordingClick?: (recordingId: string) => void;
}

export function ParticipantDetailPanel({
  participant,
  recordings,
  totalRecordings,
  loading,
  onRecordingClick,
}: ParticipantDetailPanelProps) {
  const styles = useStyles();

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

  const handleRecordingClick = (recordingId: string) => {
    if (onRecordingClick) {
      onRecordingClick(recordingId);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.scrollContainer}>
        {/* Header with Persona */}
        <div className={styles.header}>
          <Persona
            size="huge"
            name={participant.displayName}
            avatar={{ color: 'colorful' }}
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
