import { useState, useEffect, useCallback, useRef } from 'react';
import {
  makeStyles,
  mergeClasses,
  Text,
  Spinner,
  Button,
  Tooltip,
  tokens,
  Badge,
  Checkbox,
} from '@fluentui/react-components';
import {
  ArrowSync24Regular,
  Checkmark16Regular,
  Dismiss16Regular,
  ArrowLeft20Regular,
  Play16Regular,
  Pause16Regular,
} from '@fluentui/react-icons';
import type { Transcription, SpeakerMappingEntry, TopCandidate } from '../../types';
import { speakerReviewService, type ReviewItem } from '../../services/speakerReviewService';
import { transcriptionsService } from '../../services/transcriptionsService';
import { recordingsService } from '../../services/recordingsService';
import { SpeakerConfidenceBadge } from '../transcripts/SpeakerConfidenceBadge';
import { participantsService } from '../../services/participantsService';
import { showToast } from '../../utils/toast';
import { formatDate, formatDuration } from '../../utils/dateUtils';
import { useIsMobile } from '../../hooks/useIsMobile';
import { AuditLogView } from './AuditLogView';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    minHeight: 0,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 24px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    flexShrink: 0,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  headerTitle: {
    fontSize: '20px',
    fontWeight: 600,
    color: tokens.colorNeutralForeground1,
  },
  headerActions: {
    display: 'flex',
    gap: '8px',
  },
  viewContainer: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
    minHeight: 0,
  },
  listPanel: {
    width: '380px',
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
  detailPanelMobile: {
    padding: '16px',
  },
  recordingItem: {
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
  recordingItemSelected: {
    backgroundColor: tokens.colorBrandBackground2,
  },
  recordingTitle: {
    fontSize: '14px',
    fontWeight: 500,
    color: tokens.colorNeutralForeground1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  recordingMeta: {
    display: 'flex',
    gap: '8px',
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
  },
  badges: {
    display: 'flex',
    gap: '6px',
    marginTop: '4px',
  },
  speakerCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    padding: '16px',
    borderRadius: '8px',
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    marginBottom: '12px',
  },
  speakerCardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  speakerLabel: {
    fontSize: '15px',
    fontWeight: 600,
    color: tokens.colorNeutralForeground1,
  },
  candidateChips: {
    display: 'flex',
    gap: '6px',
    flexWrap: 'wrap',
  },
  candidateChip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '4px 12px',
    borderRadius: '16px',
    fontSize: '13px',
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
    fontSize: '11px',
    color: tokens.colorNeutralForeground3,
  },
  speakerActions: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
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
  mobileBackBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    flexShrink: 0,
  },
  audioSnippet: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: '6px',
    fontSize: '12px',
    color: tokens.colorNeutralForeground2,
  },
  audioSnippetText: {
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
  },
});

/** Inline dropdown for assigning a speaker — supports search, existing participants, and "Add new" */
function SpeakerAssignDropdown({ participants, onAssign, onAddNew }: {
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
      <Button
        appearance="outline"
        size="small"
        onClick={() => setIsOpen(!isOpen)}
      >
        Assign speaker...
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

export function SpeakerReviewView() {
  const styles = useStyles();
  const isMobile = useIsMobile();

  const [viewMode, setViewMode] = useState<'reviews' | 'audit'>('reviews');
  const [auditRefreshKey, setAuditRefreshKey] = useState(0);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [participants, setParticipants] = useState<{ id: string; displayName: string }[]>([]);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [playingSpeaker, setPlayingSpeaker] = useState<string | null>(null);
  const [trainingFlags, setTrainingFlags] = useState<Record<string, boolean>>({});
  // Per-speaker status: 'pending' while API call is in flight, 'confirmed' when done
  const [speakerActionStatus, setSpeakerActionStatus] = useState<Record<string, 'pending' | 'confirmed'>>({});
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const selectedReview = selectedIndex !== null ? reviews[selectedIndex] : null;

  useEffect(() => {
    loadReviews();
    loadParticipants();
  }, []);

  // Load audio URL when a recording is selected
  useEffect(() => {
    setAudioUrl(null);
    setPlayingSpeaker(null);
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (selectedReview?.recording.id) {
      recordingsService.getRecordingAudioUrl(selectedReview.recording.id)
        .then(({ audio_url }) => setAudioUrl(audio_url))
        .catch(err => console.error('[Reviews] Failed to get audio URL:', err));
    }
  }, [selectedReview?.recording.id]);

  const loadReviews = async () => {
    setLoading(true);
    try {
      const response = await speakerReviewService.getReviews('all', 100, 0);
      setReviews(response.data);
    } catch (err) {
      console.error('[Reviews] Failed to load:', err);
      showToast.error('Failed to load speaker reviews');
    } finally {
      setLoading(false);
    }
  };

  const loadParticipants = async () => {
    try {
      const data = await participantsService.getParticipants();
      setParticipants(data.map(p => ({ id: p.id, displayName: p.displayName })));
    } catch (err) {
      console.error('[Reviews] Failed to load participants:', err);
    }
  };

  // Find the longest segment for a speaker from transcript_json
  const findSpeakerSegment = useCallback((transcription: Transcription, speakerLabel: string): { startS: number; endS: number } | null => {
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
      // Pick the longest segment
      segments.sort((a, b) => (b.end - b.start) - (a.end - a.start));
      return { startS: segments[0].start, endS: segments[0].end };
    } catch {
      return null;
    }
  }, []);

  const handlePlaySpeaker = useCallback((speakerLabel: string) => {
    if (!audioUrl || !selectedReview) return;

    // If already playing this speaker, stop
    if (playingSpeaker === speakerLabel && audioRef.current) {
      audioRef.current.pause();
      setPlayingSpeaker(null);
      return;
    }

    const seg = findSpeakerSegment(selectedReview.transcription as Transcription, speakerLabel);
    if (!seg) {
      showToast.warning('No audio segment found for this speaker');
      return;
    }

    // Create or reuse audio element
    if (!audioRef.current) {
      audioRef.current = new Audio(audioUrl);
    } else if (audioRef.current.src !== audioUrl) {
      audioRef.current.src = audioUrl;
    }

    const audio = audioRef.current;
    audio.currentTime = seg.startS;
    setPlayingSpeaker(speakerLabel);

    // Stop at end of segment
    const handleTimeUpdate = () => {
      if (audio.currentTime >= seg.endS) {
        audio.pause();
        setPlayingSpeaker(null);
        audio.removeEventListener('timeupdate', handleTimeUpdate);
      }
    };
    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('pause', () => setPlayingSpeaker(null), { once: true });
    audio.play().catch(() => setPlayingSpeaker(null));
  }, [audioUrl, selectedReview, playingSpeaker, findSpeakerSegment]);

  // Optimistically update a speaker mapping entry in local state
  const updateSpeakerLocally = useCallback((
    transcriptionId: string,
    speakerLabel: string,
    updates: Partial<SpeakerMappingEntry>
  ) => {
    setReviews(prev => prev.map(review => {
      if (review.transcription.id !== transcriptionId) return review;
      const mapping = { ...review.transcription.speaker_mapping };
      if (mapping[speakerLabel]) {
        mapping[speakerLabel] = { ...mapping[speakerLabel], ...updates };
      }
      return {
        ...review,
        transcription: { ...review.transcription, speaker_mapping: mapping },
      };
    }));
  }, []);

  const handleAccept = useCallback(async (transcriptionId: string, speakerLabel: string, participantId?: string, explicitDisplayName?: string) => {
    // Optimistic: show pending immediately
    const review = reviews.find(r => r.transcription.id === transcriptionId);
    const mapping = review?.transcription.speaker_mapping?.[speakerLabel];
    const pid = participantId || mapping?.suggestedParticipantId || mapping?.participantId;
    const displayName = explicitDisplayName
      || participants.find(p => p.id === pid)?.displayName
      || mapping?.topCandidates?.find(c => c.participantId === pid)?.displayName
      || mapping?.suggestedDisplayName;
    const useForTraining = trainingFlags[speakerLabel] ?? false;

    updateSpeakerLocally(transcriptionId, speakerLabel, {
      identificationStatus: 'auto',
      participantId: pid,
      displayName,
      manuallyVerified: true,
      useForTraining,
      suggestedParticipantId: undefined,
      suggestedDisplayName: undefined,
    });
    setSpeakerActionStatus(prev => ({ ...prev, [speakerLabel]: 'pending' }));

    try {
      await transcriptionsService.acceptSuggestion(transcriptionId, speakerLabel, participantId, useForTraining);
      setSpeakerActionStatus(prev => ({ ...prev, [speakerLabel]: 'confirmed' }));
    } catch (err) {
      console.error('[Reviews] Accept failed:', err);
      setSpeakerActionStatus(prev => { const next = { ...prev }; delete next[speakerLabel]; return next; });
      showToast.error('Failed to accept speaker');
    }
  }, [trainingFlags, reviews, participants, updateSpeakerLocally]);

  const handleReject = useCallback(async (transcriptionId: string, speakerLabel: string) => {
    updateSpeakerLocally(transcriptionId, speakerLabel, {
      identificationStatus: 'unknown',
      suggestedParticipantId: undefined,
      suggestedDisplayName: undefined,
    });
    setSpeakerActionStatus(prev => ({ ...prev, [speakerLabel]: 'pending' }));

    try {
      await transcriptionsService.rejectSuggestion(transcriptionId, speakerLabel);
      setSpeakerActionStatus(prev => ({ ...prev, [speakerLabel]: 'confirmed' }));
    } catch (err) {
      console.error('[Reviews] Reject failed:', err);
      setSpeakerActionStatus(prev => { const next = { ...prev }; delete next[speakerLabel]; return next; });
      showToast.error('Failed to reject suggestion');
    }
  }, [updateSpeakerLocally]);

  const handleDismiss = useCallback(async (transcriptionId: string, speakerLabel: string) => {
    updateSpeakerLocally(transcriptionId, speakerLabel, {
      identificationStatus: 'dismissed',
      suggestedParticipantId: undefined,
      suggestedDisplayName: undefined,
    });
    setSpeakerActionStatus(prev => ({ ...prev, [speakerLabel]: 'pending' }));

    try {
      await transcriptionsService.dismissSpeaker(transcriptionId, speakerLabel);
      setSpeakerActionStatus(prev => ({ ...prev, [speakerLabel]: 'confirmed' }));
    } catch (err) {
      console.error('[Reviews] Dismiss failed:', err);
      setSpeakerActionStatus(prev => { const next = { ...prev }; delete next[speakerLabel]; return next; });
      showToast.error('Failed to dismiss speaker');
    }
  }, [updateSpeakerLocally]);

  const handleRebuildProfiles = useCallback(async () => {
    try {
      const result = await speakerReviewService.rebuildProfiles();
      showToast.success(result.message);
    } catch (err) {
      console.error('[Reviews] Rebuild failed:', err);
      showToast.error('Failed to rebuild profiles');
    }
  }, []);

  // Get speakers needing review from a transcription
  const getSpeakersNeedingReview = (transcription: Transcription): [string, SpeakerMappingEntry][] => {
    if (!transcription.speaker_mapping) return [];
    return Object.entries(transcription.speaker_mapping).filter(([_, m]) => {
      const status = m.identificationStatus;
      return status === 'suggest' || status === 'unknown';
    });
  };

  // All speakers with identification data (for the detail panel)
  const getAllIdentifiedSpeakers = (transcription: Transcription): [string, SpeakerMappingEntry][] => {
    if (!transcription.speaker_mapping) return [];
    return Object.entries(transcription.speaker_mapping).filter(([_, m]) => {
      return m.identificationStatus != null;  // Has been through identification
    });
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingContainer}>
          <Spinner label="Loading reviews..." />
        </div>
      </div>
    );
  }

  // Mobile: show detail when selected, list otherwise
  if (isMobile && selectedReview) {
    const speakersToReview = getSpeakersNeedingReview(selectedReview.transcription as Transcription);

    return (
      <div className={styles.container}>
        <div className={styles.mobileBackBar}>
          <Button
            appearance="subtle"
            icon={<ArrowLeft20Regular />}
            onClick={() => setSelectedIndex(null)}
          />
          <Text style={{ fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {selectedReview.recording.title || selectedReview.recording.original_filename}
          </Text>
        </div>
        <div className={mergeClasses(styles.detailPanel, styles.detailPanelMobile)}>
          {renderDetailContent(speakersToReview, selectedReview)}
        </div>
      </div>
    );
  }

  function renderDetailContent(
    _speakersToReview: [string, SpeakerMappingEntry][],
    review: ReviewItem
  ) {
    const allSpeakers = getAllIdentifiedSpeakers(review.transcription as Transcription);

    if (allSpeakers.length === 0) {
      return (
        <div className={styles.emptyState}>
          <Text>No speaker identification data</Text>
        </div>
      );
    }

    return allSpeakers.map(([label, mapping]) => {
      const isResolved = mapping.identificationStatus === 'auto' && mapping.manuallyVerified;
      const isDismissed = mapping.identificationStatus === 'dismissed';
      const isPending = mapping.identificationStatus === 'suggest' || mapping.identificationStatus === 'unknown';

      return (
      <div key={label} className={styles.speakerCard} style={{
        opacity: isDismissed ? 0.5 : 1,
        borderColor: isResolved ? '#86EFAC' : undefined,
      }}>
        <div className={styles.speakerCardHeader}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Tooltip content={playingSpeaker === label ? 'Stop' : 'Listen to this speaker'} relationship="label">
              <Button
                appearance="subtle"
                size="small"
                icon={playingSpeaker === label ? <Pause16Regular /> : <Play16Regular />}
                onClick={() => handlePlaySpeaker(label)}
                disabled={!audioUrl}
              />
            </Tooltip>
            <Text className={styles.speakerLabel}>
              {label}{mapping.displayName ? ` → ${mapping.displayName}` : ''}
            </Text>
            <SpeakerConfidenceBadge
              identificationStatus={mapping.identificationStatus}
              similarity={mapping.similarity}
              suggestedName={mapping.suggestedDisplayName}
            />
          </div>
          <div className={styles.speakerActions}>
            {isPending && mapping.identificationStatus === 'suggest' && mapping.suggestedParticipantId && (
              <>
                <Tooltip content={`Accept: ${mapping.suggestedDisplayName || 'suggested'}`} relationship="label">
                  <Button
                    appearance="primary"
                    size="small"
                    icon={<Checkmark16Regular />}
                    onClick={() => handleAccept(review.transcription.id, label, undefined, mapping.suggestedDisplayName)}
                  >
                    Accept
                  </Button>
                </Tooltip>
                <Tooltip content="Reject suggestion" relationship="label">
                  <Button
                    appearance="subtle"
                    size="small"
                    icon={<Dismiss16Regular />}
                    onClick={() => handleReject(review.transcription.id, label)}
                  >
                    Reject
                  </Button>
                </Tooltip>
              </>
            )}
            {!isDismissed && !isResolved && (
              <Tooltip content="Don't care — skip this speaker permanently" relationship="label">
                <Button
                  appearance="subtle"
                  size="small"
                  onClick={() => handleDismiss(review.transcription.id, label)}
                >
                  Skip
                </Button>
              </Tooltip>
            )}
          </div>
        </div>

        {/* Status indicator */}
        {(() => {
          const actionStatus = speakerActionStatus[label];
          if (actionStatus === 'pending') {
            return <Text style={{ fontSize: '12px', color: '#D97706' }}>Saving...</Text>;
          }
          if (actionStatus === 'confirmed') {
            if (isResolved) return (
              <Text style={{ fontSize: '12px', color: '#166534' }}>
                Confirmed{mapping.useForTraining ? ' · Training approved' : ''}
              </Text>
            );
            if (isDismissed) return <Text style={{ fontSize: '12px', color: '#6B7280' }}>Dismissed · Confirmed</Text>;
            return <Text style={{ fontSize: '12px', color: '#166534' }}>Confirmed</Text>;
          }
          if (isResolved) return (
            <Text style={{ fontSize: '12px', color: '#166534' }}>
              Assigned{mapping.useForTraining ? ' · Training approved' : ''}
            </Text>
          );
          if (isDismissed) return <Text style={{ fontSize: '12px', color: '#6B7280' }}>Dismissed</Text>;
          return null;
        })()}

        {/* Top candidate chips — only for pending speakers */}
        {isPending && mapping.topCandidates && mapping.topCandidates.length > 0 && (
          <>
            <Text style={{ fontSize: '12px', color: tokens.colorNeutralForeground3 }}>
              Top matches:
            </Text>
            <div className={styles.candidateChips}>
              {mapping.topCandidates.map((c: TopCandidate) => (
                <span
                  key={c.participantId}
                  className={styles.candidateChip}
                  onClick={() => handleAccept(review.transcription.id, label, c.participantId, c.displayName)}
                >
                  {c.displayName || c.participantId.substring(0, 8)}
                  <span className={styles.candidateSim}>{Math.round(c.similarity * 100)}%</span>
                </span>
              ))}
            </div>
          </>
        )}

        {/* Assign/reassign dropdown + training checkbox — for pending and resolved */}
        {!isDismissed && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <SpeakerAssignDropdown
            participants={participants}
            onAssign={(participantId) => {
              const name = participants.find(p => p.id === participantId)?.displayName;
              handleAccept(review.transcription.id, label, participantId, name);
            }}
            onAddNew={async (name) => {
              try {
                const participant = await participantsService.findOrCreateParticipant(name);
                setParticipants(prev => {
                  if (prev.some(p => p.id === participant.id)) return prev;
                  return [...prev, { id: participant.id, displayName: participant.displayName }];
                });
                handleAccept(review.transcription.id, label, participant.id, participant.displayName);
              } catch (err) {
                console.error('[Reviews] Failed to create participant:', err);
                showToast.error('Failed to create participant');
              }
            }}
          />
          <Tooltip content="If checked, this speaker's audio will be used to improve their voice profile for future identification" relationship="label">
            <Checkbox
              label="Use for training"
              size="medium"
              checked={trainingFlags[label] ?? mapping.useForTraining ?? false}
              onChange={async (_, data) => {
                const newVal = !!data.checked;
                setTrainingFlags(prev => ({ ...prev, [label]: newVal }));
                // If speaker is already assigned, toggle training via API immediately
                if (isResolved && mapping.participantId) {
                  setSpeakerActionStatus(prev => ({ ...prev, [label]: 'pending' }));
                  updateSpeakerLocally(review.transcription.id, label, { useForTraining: newVal });
                  try {
                    await transcriptionsService.toggleTraining(review.transcription.id, label, newVal);
                    setSpeakerActionStatus(prev => ({ ...prev, [label]: 'confirmed' }));
                  } catch {
                    setSpeakerActionStatus(prev => { const next = { ...prev }; delete next[label]; return next; });
                    showToast.error('Failed to update training setting');
                  }
                }
              }}
            />
          </Tooltip>
        </div>
        )}
      </div>
      );
    });
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Button
            appearance={viewMode === 'reviews' ? 'primary' : 'subtle'}
            size="small"
            onClick={() => setViewMode('reviews')}
          >
            Pending Reviews
            {viewMode === 'reviews' && reviews.length > 0 && (
              <Badge appearance="filled" color="important" size="small" style={{ marginLeft: '6px' }}>{reviews.length}</Badge>
            )}
          </Button>
          <Button
            appearance={viewMode === 'audit' ? 'primary' : 'subtle'}
            size="small"
            onClick={() => setViewMode('audit')}
          >
            Audit Log
          </Button>
        </div>
        <div className={styles.headerActions}>
          {viewMode === 'reviews' && (
            <Tooltip content="Rebuild speaker profiles" relationship="label">
              <Button
                appearance="subtle"
                icon={<ArrowSync24Regular />}
                onClick={handleRebuildProfiles}
              >
                Rebuild Profiles
              </Button>
            </Tooltip>
          )}
          <Tooltip content="Refresh" relationship="label">
            <Button
              appearance="subtle"
              icon={<ArrowSync24Regular />}
              onClick={viewMode === 'reviews' ? loadReviews : () => setAuditRefreshKey(k => k + 1)}
            />
          </Tooltip>
        </div>
      </div>

      {viewMode === 'audit' ? (
        <AuditLogView onRefresh={loadReviews} refreshKey={auditRefreshKey} />
      ) : (
      <div className={styles.viewContainer}>
        {/* List panel */}
        <div className={mergeClasses(styles.listPanel, isMobile && styles.listPanelMobile)}>
          {reviews.length === 0 ? (
            <div className={styles.emptyState} style={{ padding: '40px 20px' }}>
              <Text size={400}>No recordings need review</Text>
              <Text size={200}>Speaker identifications will appear here when ready</Text>
            </div>
          ) : (
            reviews.map((review, index) => (
              <div
                key={review.recording.id}
                className={mergeClasses(
                  styles.recordingItem,
                  selectedIndex === index && styles.recordingItemSelected
                )}
                onClick={() => setSelectedIndex(index)}
              >
                <Text className={styles.recordingTitle}>
                  {review.recording.title || review.recording.original_filename}
                </Text>
                <div className={styles.recordingMeta}>
                  {review.recording.recorded_timestamp && (
                    <Text>{formatDate(review.recording.recorded_timestamp)}</Text>
                  )}
                  {review.recording.duration && (
                    <Text>{formatDuration(review.recording.duration)}</Text>
                  )}
                </div>
                <div className={styles.badges}>
                  {review.suggestCount > 0 && (
                    <Badge appearance="tint" color="warning" size="small">
                      {review.suggestCount} suggested
                    </Badge>
                  )}
                  {review.unknownCount > 0 && (
                    <Badge appearance="tint" color="informative" size="small">
                      {review.unknownCount} unknown
                    </Badge>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Detail panel (desktop only) */}
        {!isMobile && (
          <div className={styles.detailPanel}>
            {selectedReview ? (
              <>
                <Text style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px', display: 'block' }}>
                  {selectedReview.recording.title || selectedReview.recording.original_filename}
                </Text>
                {renderDetailContent(
                  getSpeakersNeedingReview(selectedReview.transcription as Transcription),
                  selectedReview
                )}
              </>
            ) : (
              <div className={styles.emptyState}>
                <Text size={400}>Select a recording to review speakers</Text>
              </div>
            )}
          </div>
        )}
      </div>
      )}
    </div>
  );
}
