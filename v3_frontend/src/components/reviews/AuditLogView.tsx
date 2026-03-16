import { useState, useEffect, useCallback, useRef } from 'react';
import {
  makeStyles,
  mergeClasses,
  Text,
  Spinner,
  Button,
  Tooltip,
  tokens,
  Checkbox,
} from '@fluentui/react-components';
import {
  Play16Regular,
  Pause16Regular,
} from '@fluentui/react-icons';
import type { TopCandidate, Transcription } from '../../types';
import { speakerReviewService, type AuditEntry } from '../../services/speakerReviewService';
import { recordingsService } from '../../services/recordingsService';
import { transcriptionsService } from '../../services/transcriptionsService';
import { participantsService } from '../../services/participantsService';
import { showToast } from '../../utils/toast';
import { useIsMobile } from '../../hooks/useIsMobile';

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
  auto_assigned: { label: 'Auto-assigned', color: '#166534' },
  accepted: { label: 'Accepted', color: '#1E40AF' },
  rejected: { label: 'Rejected', color: '#DC2626' },
  dismissed: { label: 'Dismissed', color: '#6B7280' },
  reassigned: { label: 'Reassigned', color: '#7C3AED' },
  training_approved: { label: 'Training approved', color: '#0891B2' },
  training_revoked: { label: 'Training revoked', color: '#9CA3AF' },
  suggest: { label: 'Suggested', color: '#D97706' },
  unknown: { label: 'Unknown', color: '#6B7280' },
};

const useStyles = makeStyles({
  container: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
    minHeight: 0,
  },
  listPanel: {
    width: '420px',
    flexShrink: 0,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    overflowY: 'auto',
  },
  listPanelMobile: {
    width: '100%',
    borderRight: 'none',
  },
  detailPanel: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px',
  },
  auditCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    padding: '12px 16px',
    cursor: 'pointer',
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    ':hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  auditCardSelected: {
    backgroundColor: tokens.colorBrandBackground2,
  },
  auditCardTitle: {
    fontSize: '13px',
    fontWeight: 500,
    color: tokens.colorNeutralForeground1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  auditCardMeta: {
    display: 'flex',
    gap: '6px',
    alignItems: 'center',
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
  },
  actionBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '1px 6px',
    borderRadius: '10px',
    fontSize: '11px',
    fontWeight: 500,
  },
  detailSection: {
    marginBottom: '20px',
  },
  detailSectionTitle: {
    fontSize: '11px',
    fontWeight: 600,
    color: tokens.colorNeutralForeground3,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '8px',
  },
  detailRow: {
    display: 'flex',
    gap: '8px',
    fontSize: '13px',
    marginBottom: '4px',
  },
  detailLabel: {
    color: tokens.colorNeutralForeground3,
    minWidth: '100px',
  },
  detailValue: {
    color: tokens.colorNeutralForeground1,
    fontWeight: 500,
  },
  candidateList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    marginTop: '4px',
  },
  candidateRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '12px',
    padding: '4px 8px',
    borderRadius: '4px',
    backgroundColor: tokens.colorNeutralBackground3,
  },
  candidateName: {
    fontWeight: 500,
  },
  candidateSim: {
    color: tokens.colorNeutralForeground3,
  },
  timelineEntry: {
    display: 'flex',
    gap: '12px',
    padding: '8px 0',
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
  },
  timelineDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    marginTop: '5px',
    flexShrink: 0,
  },
  reassignSection: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    flexWrap: 'wrap',
    marginTop: '12px',
    padding: '12px',
    borderRadius: '8px',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground3,
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    gap: '12px',
    color: tokens.colorNeutralForeground3,
  },
  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
  },
  audioSnippet: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
});

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}

function findSpeakerSegment(transcription: Transcription, speakerLabel: string): { startS: number; endS: number } | null {
  if (!transcription.transcript_json) return null;
  try {
    const data = JSON.parse(transcription.transcript_json);
    const segments: { start: number; end: number }[] = [];

    if (Array.isArray(data)) {
      for (const seg of data) {
        const spk = typeof seg.speaker === 'number' ? `Speaker ${seg.speaker}` : (seg.speaker || seg.speakerLabel);
        if (spk === speakerLabel) {
          const start = seg.start ?? seg.offset ?? 0;
          const end = seg.end ?? (start + (seg.duration ?? 0));
          segments.push({ start: Number(start), end: Number(end) });
        }
      }
    } else if (data?.recognizedPhrases) {
      for (const phrase of data.recognizedPhrases) {
        const spk = `Speaker ${phrase.speaker ?? 0}`;
        if (spk === speakerLabel) {
          const start = (phrase.offsetInTicks ?? 0) / 10_000_000;
          const dur = (phrase.durationInTicks ?? 0) / 10_000_000;
          segments.push({ start, end: start + dur });
        }
      }
    }

    if (segments.length === 0) return null;
    segments.sort((a, b) => (b.end - b.start) - (a.end - a.start));
    return { startS: segments[0].start, endS: segments[0].end };
  } catch {
    return null;
  }
}

interface AuditLogViewProps {
  onRefresh?: () => void;
  refreshKey?: number;  // Increment to trigger a reload
}

export function AuditLogView({ onRefresh, refreshKey }: AuditLogViewProps) {
  const styles = useStyles();
  const isMobile = useIsMobile();

  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [participants, setParticipants] = useState<{ id: string; displayName: string }[]>([]);
  const [useForTraining, setUseForTraining] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const selectedEntry = selectedIndex !== null ? entries[selectedIndex] : null;

  useEffect(() => {
    loadAudit();
    loadParticipants();
  }, [refreshKey]);

  // Reset state when selection changes, load audio
  useEffect(() => {
    setUseForTraining(false);
    setAudioUrl(null);
    setIsPlaying(false);
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    if (selectedEntry?.recordingId) {
      recordingsService.getRecordingAudioUrl(selectedEntry.recordingId)
        .then(({ audio_url }) => setAudioUrl(audio_url))
        .catch(() => {});
    }
  }, [selectedIndex]);

  const loadAudit = async () => {
    setLoading(true);
    try {
      const response = await speakerReviewService.getAuditLog(200, 0);
      setEntries(response.data);
    } catch (err) {
      console.error('[Audit] Failed to load:', err);
      showToast.error('Failed to load audit log');
    } finally {
      setLoading(false);
    }
  };

  const loadParticipants = async () => {
    try {
      const data = await participantsService.getParticipants();
      setParticipants(data.map(p => ({ id: p.id, displayName: p.displayName })));
    } catch {}
  };

  const handlePlaySpeaker = useCallback(async () => {
    if (!audioUrl || !selectedEntry) return;

    // If already playing, stop
    if (isPlaying && audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
      return;
    }

    // Fetch transcription to find speaker segments
    try {
      const transcription = await transcriptionsService.getTranscriptionById(selectedEntry.transcriptionId);
      const seg = findSpeakerSegment(transcription, selectedEntry.speakerLabel);
      if (!seg) {
        showToast.warning('No audio segment found for this speaker');
        return;
      }

      if (!audioRef.current) {
        audioRef.current = new Audio(audioUrl);
      } else if (audioRef.current.src !== audioUrl) {
        audioRef.current.src = audioUrl;
      }

      const audio = audioRef.current;
      audio.currentTime = seg.startS;
      setIsPlaying(true);

      const handleTimeUpdate = () => {
        if (audio.currentTime >= seg.endS) {
          audio.pause();
          setIsPlaying(false);
          audio.removeEventListener('timeupdate', handleTimeUpdate);
        }
      };
      audio.addEventListener('timeupdate', handleTimeUpdate);
      audio.addEventListener('pause', () => setIsPlaying(false), { once: true });
      audio.play().catch(() => setIsPlaying(false));
    } catch {
      showToast.error('Failed to load audio');
    }
  }, [audioUrl, selectedEntry, isPlaying]);

  const handleReassign = useCallback(async (participantId: string) => {
    if (!selectedEntry) return;
    try {
      await speakerReviewService.reassignSpeaker(
        selectedEntry.transcriptionId,
        selectedEntry.speakerLabel,
        participantId,
        useForTraining
      );
      showToast.success('Speaker reassigned');
    } catch (err) {
      console.error('[Audit] Reassign failed:', err);
      showToast.error('Failed to reassign speaker');
    }
  }, [selectedEntry, useForTraining, onRefresh]);

  const handleAddNewAndReassign = useCallback(async (name: string) => {
    try {
      const participant = await participantsService.findOrCreateParticipant(name);
      setParticipants(prev => {
        if (prev.some(p => p.id === participant.id)) return prev;
        return [...prev, { id: participant.id, displayName: participant.displayName }];
      });
      handleReassign(participant.id);
    } catch (err) {
      showToast.error('Failed to create participant');
    }
  }, [handleReassign]);

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <Spinner label="Loading audit log..." />
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className={styles.emptyState} style={{ padding: '40px' }}>
        <Text size={400}>No identification history yet</Text>
        <Text size={200}>Run the speaker identification worker to start building history</Text>
      </div>
    );
  }

  const renderDetail = () => {
    if (!selectedEntry) {
      return (
        <div className={styles.emptyState}>
          <Text size={400}>Select an entry to view details</Text>
        </div>
      );
    }

    const actionInfo = ACTION_LABELS[selectedEntry.action] || { label: selectedEntry.action, color: '#6B7280' };

    return (
      <>
        {/* Header */}
        <Text style={{ fontSize: '18px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>
          {selectedEntry.recordingTitle}
        </Text>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
          <Text style={{ fontSize: '14px', color: tokens.colorNeutralForeground3 }}>
            {selectedEntry.speakerLabel}
          </Text>
          <Tooltip content={isPlaying ? 'Stop' : 'Listen to this speaker'} relationship="label">
            <Button
              appearance="subtle"
              size="small"
              icon={isPlaying ? <Pause16Regular /> : <Play16Regular />}
              onClick={handlePlaySpeaker}
              disabled={!audioUrl}
            >
              {isPlaying ? 'Stop' : 'Listen'}
            </Button>
          </Tooltip>
        </div>

        {/* Event details */}
        <div className={styles.detailSection}>
          <Text className={styles.detailSectionTitle}>Event Details</Text>
          <div className={styles.detailRow}>
            <Text className={styles.detailLabel}>Action</Text>
            <span className={styles.actionBadge} style={{ backgroundColor: actionInfo.color + '20', color: actionInfo.color }}>
              {actionInfo.label}
            </span>
          </div>
          <div className={styles.detailRow}>
            <Text className={styles.detailLabel}>When</Text>
            <Text className={styles.detailValue}>{formatTimestamp(selectedEntry.timestamp)}</Text>
          </div>
          <div className={styles.detailRow}>
            <Text className={styles.detailLabel}>Source</Text>
            <Text className={styles.detailValue}>{selectedEntry.source || 'unknown'}</Text>
          </div>
          {selectedEntry.displayName && (
            <div className={styles.detailRow}>
              <Text className={styles.detailLabel}>Assigned to</Text>
              <Text className={styles.detailValue}>{selectedEntry.displayName}</Text>
            </div>
          )}
          {selectedEntry.similarity != null && (
            <div className={styles.detailRow}>
              <Text className={styles.detailLabel}>Similarity</Text>
              <Text className={styles.detailValue}>{Math.round(selectedEntry.similarity * 100)}%</Text>
            </div>
          )}
        </div>

        {/* Current state */}
        <div className={styles.detailSection}>
          <Text className={styles.detailSectionTitle}>Current Assignment</Text>
          <div className={styles.detailRow}>
            <Text className={styles.detailLabel}>Speaker</Text>
            <Text className={styles.detailValue}>{selectedEntry.currentDisplayName || 'Unassigned'}</Text>
          </div>
          <div className={styles.detailRow}>
            <Text className={styles.detailLabel}>Status</Text>
            <Text className={styles.detailValue}>{selectedEntry.currentStatus || 'none'}</Text>
          </div>
        </div>

        {/* Candidates presented */}
        {selectedEntry.candidatesPresented && selectedEntry.candidatesPresented.length > 0 && (
          <div className={styles.detailSection}>
            <Text className={styles.detailSectionTitle}>Candidates Presented</Text>
            <div className={styles.candidateList}>
              {selectedEntry.candidatesPresented.map((c: TopCandidate, i: number) => (
                <div key={i} className={styles.candidateRow}>
                  <Text className={styles.candidateName}>{c.displayName || c.participantId?.substring(0, 8)}</Text>
                  <Text className={styles.candidateSim}>{Math.round(c.similarity * 100)}%</Text>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reassign section */}
        <div className={styles.detailSection}>
          <Text className={styles.detailSectionTitle}>Reassign Speaker</Text>
          <div className={styles.reassignSection}>
            <ReassignDropdown
              participants={participants}
              onAssign={handleReassign}
              onAddNew={handleAddNewAndReassign}
            />
            <Tooltip content="If checked, this speaker's audio will be used to improve their voice profile" relationship="label">
              <Checkbox
                label="Use for training"
                size="medium"
                checked={useForTraining}
                onChange={(_, data) => setUseForTraining(!!data.checked)}
              />
            </Tooltip>
          </div>
        </div>
      </>
    );
  };

  return (
    <div className={styles.container}>
      <div className={mergeClasses(styles.listPanel, isMobile && styles.listPanelMobile)}>
        {entries.map((entry, index) => {
          const actionInfo = ACTION_LABELS[entry.action] || { label: entry.action, color: '#6B7280' };
          return (
            <div
              key={`${entry.transcriptionId}-${entry.speakerLabel}-${entry.timestamp}-${index}`}
              className={mergeClasses(
                styles.auditCard,
                selectedIndex === index && styles.auditCardSelected
              )}
              onClick={() => setSelectedIndex(index)}
            >
              <Text className={styles.auditCardTitle}>
                {entry.recordingTitle}
              </Text>
              <div className={styles.auditCardMeta}>
                <span className={styles.actionBadge} style={{ backgroundColor: actionInfo.color + '20', color: actionInfo.color }}>
                  {actionInfo.label}
                </span>
                <Text>
                  {entry.speakerLabel}{entry.currentDisplayName ? ` → ${entry.currentDisplayName}` : ''}
                </Text>
                {entry.similarity != null && <Text>{Math.round(entry.similarity * 100)}%</Text>}
              </div>
              <Text style={{ fontSize: '11px', color: tokens.colorNeutralForeground3 }}>
                {formatTimestamp(entry.timestamp)}
              </Text>
            </div>
          );
        })}
      </div>

      {!isMobile && (
        <div className={styles.detailPanel}>
          {renderDetail()}
        </div>
      )}
    </div>
  );
}

/** Simple dropdown for reassignment */
function ReassignDropdown({ participants, onAssign, onAddNew }: {
  participants: { id: string; displayName: string }[];
  onAssign: (participantId: string) => void;
  onAddNew: (name: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [isOpen]);

  const filtered = participants.filter(p =>
    p.displayName.toLowerCase().includes(search.toLowerCase())
  );
  const showAddNew = search.trim() && !filtered.some(p => p.displayName.toLowerCase() === search.toLowerCase());

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      <Button appearance="primary" size="small" onClick={() => setIsOpen(!isOpen)}>
        Reassign to...
      </Button>
      {isOpen && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, zIndex: 100,
          backgroundColor: 'white', border: '1px solid #d1d5db', borderRadius: '6px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)', minWidth: '240px', maxHeight: '300px',
          overflowY: 'auto', marginTop: '4px',
        }}>
          <div style={{ padding: '8px', borderBottom: '1px solid #e5e7eb' }}>
            <input
              autoFocus
              placeholder="Search or add new..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Escape') { setIsOpen(false); setSearch(''); }
                if (e.key === 'Enter' && showAddNew) { onAddNew(search.trim()); setIsOpen(false); setSearch(''); }
                if (e.key === 'Enter' && filtered.length === 1) { onAssign(filtered[0].id); setIsOpen(false); setSearch(''); }
              }}
              style={{ width: '100%', padding: '6px 8px', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '13px', outline: 'none' }}
            />
          </div>
          {filtered.map(p => (
            <div
              key={p.id}
              onClick={() => { onAssign(p.id); setIsOpen(false); setSearch(''); }}
              style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '13px' }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f3f4f6')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              {p.displayName}
            </div>
          ))}
          {showAddNew && (
            <div
              onClick={() => { onAddNew(search.trim()); setIsOpen(false); setSearch(''); }}
              style={{ padding: '8px 12px', cursor: 'pointer', fontSize: '13px', color: '#2563eb', fontWeight: 500 }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#eff6ff')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              + Add "{search.trim()}"
            </div>
          )}
          {filtered.length === 0 && !showAddNew && (
            <div style={{ padding: '8px 12px', fontSize: '13px', color: '#9ca3af' }}>
              Type to search or add...
            </div>
          )}
        </div>
      )}
    </div>
  );
}
