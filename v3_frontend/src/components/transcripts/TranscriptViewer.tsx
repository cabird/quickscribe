import { useState, useEffect, useRef, useCallback } from 'react';
import { makeStyles, mergeClasses, Text, Spinner, tokens, Button, Tooltip, Popover, PopoverTrigger, PopoverSurface } from '@fluentui/react-components';
import { Copy24Regular, Copy16Regular, Chat24Regular, Delete24Regular, Info24Regular, ChevronDown20Regular, ChevronUp20Regular } from '@fluentui/react-icons';
import type { Recording, Transcription, Participant } from '../../types';
import { TranscriptEntry } from './TranscriptEntry';
import { ChatDrawer } from './ChatDrawer';
import { AudioPlayer, AudioPlayerHandle } from './AudioPlayer';
import { useTranscriptParser } from './useTranscriptParser';
import type { ChatMessage } from '../../services/chatService';
import { formatDate, formatTime, formatDuration } from '../../utils/dateUtils';
import { formatSpeakersList, getSpeakerNamesFromMapping } from '../../utils/formatters';
import { showToast } from '../../utils/toast';
import { recordingsService } from '../../services/recordingsService';
import { participantsService } from '../../services/participantsService';
import { transcriptionsService } from '../../services/transcriptionsService';
import { useIsMobile } from '../../hooks/useIsMobile';

const useStyles = makeStyles({
  viewContainer: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
  },
  container: {
    flex: 1,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: 'hidden',
  },
  chatDrawerContainer: {
    flexShrink: 0,
  },
  // Mobile full-screen chat overlay
  mobileChatOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 200,
    backgroundColor: tokens.colorNeutralBackground1,
    display: 'flex',
    flexDirection: 'column',
  },
  headerButtons: {
    display: 'flex',
    gap: '4px',
  },
  headerButton: {
    color: '#9CA3AF',
    transition: 'color 0.15s',
    ':hover': {
      color: '#374151',
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  header: {
    padding: '24px',
    paddingBottom: '16px',
    flexShrink: 0,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  headerMobile: {
    padding: '12px 16px',
    paddingBottom: '8px',
  },
  headerTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '12px',
  },
  headerTopMobile: {
    marginBottom: '0',
  },
  titleContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    flex: 1,
    marginRight: '16px',
  },
  title: {
    fontSize: '22px',
    fontWeight: 600,
    color: '#111827',
    lineHeight: '1.3',
  },
  titleMobile: {
    fontSize: '16px',
    lineHeight: '1.2',
  },
  meta: {
    display: 'flex',
    gap: '8px',
    fontSize: '13px',
    color: '#6B7280',
    marginTop: '8px',
  },
  metaMobile: {
    fontSize: '12px',
    marginTop: '4px',
    flexWrap: 'wrap',
  },
  metaSeparator: {
    color: '#D1D5DB',
  },
  description: {
    fontSize: '14px',
    color: '#4B5563',
    marginTop: '12px',
    lineHeight: '1.6',
  },
  descriptionMobile: {
    fontSize: '13px',
    marginTop: '8px',
    lineHeight: '1.5',
  },
  collapsibleContent: {
    overflow: 'hidden',
    transitionProperty: 'max-height, opacity',
    transitionDuration: '200ms',
    transitionTimingFunction: 'ease-in-out',
  },
  collapsed: {
    maxHeight: '0',
    opacity: 0,
  },
  expanded: {
    maxHeight: '500px',
    opacity: 1,
  },
  collapseToggle: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '2px 0',
    cursor: 'pointer',
    color: tokens.colorNeutralForeground3,
    fontSize: '12px',
    gap: '4px',
    border: 'none',
    backgroundColor: 'transparent',
    width: '100%',
  },
  transcriptArea: {
    flex: 1,
    minHeight: 0,
    overflowY: 'auto',
    padding: '24px',
  },
  transcriptAreaMobile: {
    padding: '12px 16px',
  },
  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    padding: '24px',
    textAlign: 'center',
    gap: '12px',
  },
  infoPopover: {
    padding: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
    minWidth: '320px',
    maxHeight: '400px',
    overflowY: 'auto',
  },
  infoSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  infoSectionTitle: {
    fontSize: '11px',
    fontWeight: 600,
    color: tokens.colorNeutralForeground3,
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
  },
  infoRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  infoLabel: {
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
    fontWeight: 500,
  },
  infoValue: {
    fontSize: '13px',
    fontFamily: 'monospace',
    color: tokens.colorNeutralForeground1,
    userSelect: 'all',
  },
  infoValueRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  copyButton: {
    minWidth: '20px',
    width: '20px',
    height: '20px',
    padding: '2px',
    color: tokens.colorNeutralForeground3,
    cursor: 'pointer',
    borderRadius: '4px',
    flexShrink: 0,
    ':hover': {
      color: tokens.colorNeutralForeground1,
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  speakerTable: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '12px',
  },
  speakerTableHeader: {
    textAlign: 'left',
    padding: '4px 6px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    color: tokens.colorNeutralForeground3,
    fontWeight: 500,
  },
  speakerTableCell: {
    padding: '4px 6px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke3}`,
    fontFamily: 'monospace',
    fontSize: '11px',
    verticalAlign: 'top',
  },
  speakerLabel: {
    fontWeight: 600,
    color: tokens.colorNeutralForeground1,
  },
  noSpeakers: {
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
    fontStyle: 'italic',
  },
});

interface TranscriptViewerProps {
  transcription: Transcription | null;
  recording: Recording | null;
  loading: boolean;
}

export function TranscriptViewer({ transcription, recording, loading }: TranscriptViewerProps) {
  const styles = useStyles();
  const isMobile = useIsMobile();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatDrawerWidth] = useState(40);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [speakerMappings, setSpeakerMappings] = useState<Record<string, string>>({});
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [isAudioPlaying, setIsAudioPlaying] = useState(false);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [isHeaderCollapsed, setIsHeaderCollapsed] = useState(false);

  const audioPlayerRef = useRef<AudioPlayerHandle>(null);
  const entryRefs = useRef<(HTMLDivElement | null)[]>([]);

  // Use the transcript parser hook
  const { entries: transcriptEntries, speakerIndexMap, hasTimestamps } = useTranscriptParser(
    transcription,
    speakerMappings
  );

  // Reset state when transcription changes
  useEffect(() => {
    setChatMessages([]);
    setIsHeaderCollapsed(false);
    // Reset speaker mappings - initialize from transcription's speaker_mapping if available
    if (transcription?.speaker_mapping) {
      const initialMappings: Record<string, string> = {};
      for (const [label, mapping] of Object.entries(transcription.speaker_mapping)) {
        // Use enriched displayName from API (name is deprecated legacy field)
        if (mapping.displayName) {
          initialMappings[label] = mapping.displayName;
        }
      }
      setSpeakerMappings(initialMappings);
    } else {
      setSpeakerMappings({});
    }
  }, [transcription?.id]);

  // Fetch participants on mount
  useEffect(() => {
    const fetchParticipants = async () => {
      try {
        const data = await participantsService.getParticipants();
        setParticipants(data);
      } catch (err) {
        console.error('[Participants] Failed to fetch participants:', err);
      }
    };
    fetchParticipants();
  }, []);

  // Load audio URL when recording changes
  useEffect(() => {
    if (recording?.id) {
      recordingsService.getRecordingAudioUrl(recording.id)
        .then(({ audio_url }) => {
          setAudioUrl(audio_url);
        })
        .catch(err => {
          console.error('[Audio] Failed to get audio URL:', err);
        });
    }
  }, [recording?.id]);

  // Handle scrolling to and highlighting transcript entries
  useEffect(() => {
    if (highlightedIndex === null) return;

    const targetEntry = entryRefs.current[highlightedIndex];
    if (targetEntry) {
      targetEntry.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Clear the highlight after a delay
    const timer = setTimeout(() => {
      setHighlightedIndex(null);
    }, 2000);

    return () => clearTimeout(timer);
  }, [highlightedIndex]);

  const handleCopyTranscript = async () => {
    if (!transcription?.diarized_transcript && !transcription?.text) {
      showToast.warning('No transcript text to copy');
      return;
    }

    try {
      const textToCopy = transcription.diarized_transcript || transcription.text || '';
      await navigator.clipboard.writeText(textToCopy);
      showToast.success('Transcript copied to clipboard');
    } catch (error) {
      showToast.error('Failed to copy transcript');
    }
  };

  const handleCopyId = async (id: string, label: string) => {
    try {
      await navigator.clipboard.writeText(id);
      showToast.success(`${label} copied`);
    } catch (error) {
      showToast.error('Failed to copy');
    }
  };

  const handleDeleteRecording = async () => {
    if (!recording) return;

    if (!confirm(`Are you sure you want to delete "${recording.title || recording.original_filename}"? This cannot be undone.`)) {
      return;
    }

    try {
      await recordingsService.deleteRecording(recording.id);
      showToast.success('Recording deleted successfully');
      window.dispatchEvent(new CustomEvent('recordingDeleted', {
        detail: { recordingId: recording.id }
      }));
    } catch (error) {
      console.error('Failed to delete recording:', error);
      showToast.error('Failed to delete recording');
    }
  };

  const handlePlayFromTime = (timeMs: number) => {
    audioPlayerRef.current?.seekTo(timeMs);
  };

  const handleAudioPause = useCallback(() => {
    audioPlayerRef.current?.pause();
  }, []);

  const handlePlayStateChange = useCallback((playing: boolean, timeMs: number) => {
    setIsAudioPlaying(playing);
    setCurrentTimeMs(timeMs);
  }, []);

  const handleSpeakerRename = useCallback(async (speakerLabel: string, newName: string) => {
    if (!transcription) {
      showToast.error('No transcription available');
      return;
    }

    console.log(`[Speaker] Renaming "${speakerLabel}" to "${newName}"`);

    // Optimistically update local state
    setSpeakerMappings(prev => ({
      ...prev,
      [speakerLabel]: newName,
    }));

    try {
      // Find or create participant with this name
      const participant = await participantsService.findOrCreateParticipant(newName);
      console.log(`[Speaker] Using participant ${participant.id} (${participant.displayName})`);

      // Sync local state with the actual displayName from the service
      setSpeakerMappings(prev => ({
        ...prev,
        [speakerLabel]: participant.displayName,
      }));

      // Update participant list if this is a new participant
      setParticipants(prev => {
        const exists = prev.some(p => p.id === participant.id);
        if (!exists) {
          return [...prev, participant];
        }
        return prev;
      });

      // Call backend to persist the speaker mapping
      await transcriptionsService.updateSpeaker(
        transcription.id,
        speakerLabel,
        participant.id,
        true // manuallyVerified
      );

      showToast.success(`Speaker renamed to ${participant.displayName}`);
    } catch (err) {
      console.error('[Speaker] Failed to save speaker mapping:', err);
      showToast.error('Failed to save speaker assignment');

      // Revert optimistic update on error
      setSpeakerMappings(prev => {
        const updated = { ...prev };
        delete updated[speakerLabel];
        return updated;
      });
    }
  }, [transcription]);

  const handleRefClick = (transcriptIndex: number) => {
    setHighlightedIndex(transcriptIndex);
  };

  // Get full name for a speaker label by looking up participant
  const getFullName = useCallback((speakerLabel: string): string | undefined => {
    const mapping = transcription?.speaker_mapping?.[speakerLabel];
    if (!mapping?.participantId) return undefined;

    const participant = participants.find(p => p.id === mapping.participantId);
    if (!participant) return undefined;

    // Combine first and last name, falling back gracefully
    const nameParts = [participant.firstName, participant.lastName].filter(Boolean);
    if (nameParts.length > 0) {
      return nameParts.join(' ');
    }
    // Fallback to displayName if no first/last name
    return participant.displayName;
  }, [transcription?.speaker_mapping, participants]);

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingContainer}>
          <Spinner label="Loading transcript..." />
        </div>
      </div>
    );
  }

  if (!recording || !transcription) {
    return (
      <div className={styles.container}>
        <div className={styles.emptyState}>
          <Text size={400}>Select a recording to view transcript</Text>
        </div>
      </div>
    );
  }

  const headerContent = (
    <>
      <div className={mergeClasses(styles.headerTop, isMobile && styles.headerTopMobile)}>
        <div className={styles.titleContainer}>
          <Text className={mergeClasses(styles.title, isMobile && styles.titleMobile)}>
            {recording.title || recording.original_filename}
          </Text>
          {/* On mobile when collapsed, show minimal meta inline */}
          {(!isMobile || !isHeaderCollapsed) && (
            <div className={mergeClasses(styles.meta, isMobile && styles.metaMobile)}>
              {recording.recorded_timestamp && (
                <>
                  <Text>{formatDate(recording.recorded_timestamp)}</Text>
                  <Text className={styles.metaSeparator}>·</Text>
                  <Text>{formatTime(recording.recorded_timestamp)}</Text>
                </>
              )}
              {recording.duration && (
                <>
                  <Text className={styles.metaSeparator}>·</Text>
                  <Text>{formatDuration(recording.duration)}</Text>
                </>
              )}
              {!isMobile && transcription?.speaker_mapping && Object.keys(transcription.speaker_mapping).length > 0 && (
                <>
                  <Text className={styles.metaSeparator}>·</Text>
                  <Text>{formatSpeakersList(getSpeakerNamesFromMapping(transcription.speaker_mapping))}</Text>
                </>
              )}
            </div>
          )}
        </div>
        <div className={styles.headerButtons}>
          <Tooltip content="Chat with transcript" relationship="label">
            <Button
              appearance="subtle"
              className={styles.headerButton}
              icon={<Chat24Regular />}
              onClick={() => setIsChatOpen(!isChatOpen)}
            />
          </Tooltip>
          <Tooltip content="Copy transcript to clipboard" relationship="label">
            <Button
              appearance="subtle"
              className={styles.headerButton}
              icon={<Copy24Regular />}
              onClick={handleCopyTranscript}
            />
          </Tooltip>
          <Popover withArrow>
            <PopoverTrigger disableButtonEnhancement>
              <Tooltip content="View details" relationship="label">
                <Button
                  appearance="subtle"
                  className={styles.headerButton}
                  icon={<Info24Regular />}
                />
              </Tooltip>
            </PopoverTrigger>
            <PopoverSurface>
              <div className={styles.infoPopover}>
                {/* IDs Section */}
                <div className={styles.infoSection}>
                  <Text className={styles.infoSectionTitle}>Identifiers</Text>
                  <div className={styles.infoRow}>
                    <Text className={styles.infoLabel}>Recording ID</Text>
                    <div className={styles.infoValueRow}>
                      <Text className={styles.infoValue}>{recording.id}</Text>
                      <Button
                        appearance="subtle"
                        size="small"
                        className={styles.copyButton}
                        icon={<Copy16Regular />}
                        onClick={() => handleCopyId(recording.id, 'Recording ID')}
                      />
                    </div>
                  </div>
                  <div className={styles.infoRow}>
                    <Text className={styles.infoLabel}>Transcription ID</Text>
                    <div className={styles.infoValueRow}>
                      <Text className={styles.infoValue}>{transcription.id}</Text>
                      <Button
                        appearance="subtle"
                        size="small"
                        className={styles.copyButton}
                        icon={<Copy16Regular />}
                        onClick={() => handleCopyId(transcription.id, 'Transcription ID')}
                      />
                    </div>
                  </div>
                </div>

                {/* Speaker Mapping Section */}
                <div className={styles.infoSection}>
                  <Text className={styles.infoSectionTitle}>Speaker Mapping</Text>
                  {transcription.speaker_mapping && Object.keys(transcription.speaker_mapping).length > 0 ? (
                    <table className={styles.speakerTable}>
                      <thead>
                        <tr>
                          <th className={styles.speakerTableHeader}>#</th>
                          <th className={styles.speakerTableHeader}>Name</th>
                          <th className={styles.speakerTableHeader}>Verified</th>
                          <th className={styles.speakerTableHeader}>Participant</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(transcription.speaker_mapping).map(([label, mapping]) => {
                          const speakerNum = label.replace(/\D/g, '') || label;
                          return (
                            <tr key={label}>
                              <td className={styles.speakerTableCell}>
                                <span className={styles.speakerLabel}>{speakerNum}</span>
                              </td>
                              <td className={styles.speakerTableCell}>
                                {mapping.displayName || label}
                              </td>
                              <td className={styles.speakerTableCell}>
                                {mapping.manuallyVerified ? '✓' : '-'}
                              </td>
                              <td className={styles.speakerTableCell}>
                                {mapping.participantId ? (
                                  <div className={styles.infoValueRow}>
                                    <span>{mapping.participantId.substring(0, 8)}...</span>
                                    <Button
                                      appearance="subtle"
                                      size="small"
                                      className={styles.copyButton}
                                      icon={<Copy16Regular />}
                                      onClick={() => handleCopyId(mapping.participantId!, 'Participant ID')}
                                    />
                                  </div>
                                ) : '-'}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  ) : (
                    <Text className={styles.noSpeakers}>No speaker mapping available</Text>
                  )}
                </div>
              </div>
            </PopoverSurface>
          </Popover>
          <Tooltip content="Delete recording" relationship="label">
            <Button
              appearance="subtle"
              className={styles.headerButton}
              icon={<Delete24Regular />}
              onClick={handleDeleteRecording}
            />
          </Tooltip>
        </div>
      </div>

      {/* Collapsible description section on mobile */}
      {recording.description && (
        isMobile ? (
          <div
            className={mergeClasses(
              styles.collapsibleContent,
              isHeaderCollapsed ? styles.collapsed : styles.expanded
            )}
          >
            <div className={mergeClasses(styles.description, styles.descriptionMobile)}>
              <Text>{recording.description}</Text>
            </div>
          </div>
        ) : (
          <div className={styles.description}>
            <Text>{recording.description}</Text>
          </div>
        )
      )}

      {/* Collapse/expand toggle for mobile */}
      {isMobile && recording.description && (
        <button
          className={styles.collapseToggle}
          onClick={() => setIsHeaderCollapsed(!isHeaderCollapsed)}
        >
          {isHeaderCollapsed ? (
            <>Show details <ChevronDown20Regular /></>
          ) : (
            <>Hide details <ChevronUp20Regular /></>
          )}
        </button>
      )}
    </>
  );

  const transcriptContent = (
    <>
      <div className={mergeClasses(styles.header, isMobile && styles.headerMobile)}>
        {headerContent}
      </div>

      {/* Audio player - only show if we have audio and timestamps */}
      {audioUrl && hasTimestamps && (
        <AudioPlayer
          ref={audioPlayerRef}
          audioUrl={audioUrl}
          onPlayStateChange={handlePlayStateChange}
        />
      )}

      <div className={mergeClasses(styles.transcriptArea, isMobile && styles.transcriptAreaMobile)}>
        {transcriptEntries.length > 0 ? (
          transcriptEntries.map((entry, index) => (
            <div
              key={index}
              ref={el => { entryRefs.current[index] = el; }}
              style={{
                backgroundColor: highlightedIndex === index ? '#fff3cd' : 'transparent',
                transition: 'background-color 0.3s',
              }}
            >
              <TranscriptEntry
                speaker={entry.displayName}
                speakerLabel={entry.speakerLabel}
                fullName={getFullName(entry.speakerLabel)}
                text={entry.text}
                speakerIndex={speakerIndexMap.get(entry.speakerLabel) ?? 0}
                startTimeMs={entry.startTimeMs}
                endTimeMs={entry.endTimeMs}
                hasTimestamp={entry.startTimeMs > 0}
                isAudioPlaying={isAudioPlaying}
                currentTimeMs={currentTimeMs}
                onPlayFromTime={handlePlayFromTime}
                onPause={handleAudioPause}
                onSpeakerRename={handleSpeakerRename}
                knownSpeakers={participants.map(p =>
                  p.firstName && p.lastName
                    ? `${p.firstName} ${p.lastName}`
                    : p.displayName
                )}
              />
            </div>
          ))
        ) : (
          <div className={styles.emptyState}>
            <Text>No transcript available</Text>
          </div>
        )}
      </div>
    </>
  );

  // Mobile: full-screen chat overlay
  if (isMobile && isChatOpen && transcription) {
    return (
      <div className={styles.viewContainer} style={{ position: 'relative' }}>
        <div className={styles.container}>
          {transcriptContent}
        </div>
        <div className={styles.mobileChatOverlay}>
          <ChatDrawer
            transcriptionIds={[transcription.id]}
            transcriptEntries={transcriptEntries.map(e => ({ speaker: e.displayName, text: e.text }))}
            messages={chatMessages}
            onMessagesChange={setChatMessages}
            onClose={() => setIsChatOpen(false)}
            onMinimize={() => setIsChatOpen(false)}
            onRefClick={handleRefClick}
          />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.viewContainer}>
      <div className={styles.container}>
        {transcriptContent}
      </div>

      {isChatOpen && transcription && (
        <div className={styles.chatDrawerContainer} style={{ width: `${chatDrawerWidth}%` }}>
          <ChatDrawer
            transcriptionIds={[transcription.id]}
            transcriptEntries={transcriptEntries.map(e => ({ speaker: e.displayName, text: e.text }))}
            messages={chatMessages}
            onMessagesChange={setChatMessages}
            onClose={() => setIsChatOpen(false)}
            onMinimize={() => setIsChatOpen(false)}
            onRefClick={handleRefClick}
          />
        </div>
      )}
    </div>
  );
}
