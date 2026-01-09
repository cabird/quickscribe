import { useState, useEffect, useRef, useCallback } from 'react';
import { makeStyles, Text, Spinner, tokens, Button, Tooltip } from '@fluentui/react-components';
import { Copy24Regular, Chat24Regular, Delete24Regular } from '@fluentui/react-icons';
import type { Recording, Transcription, Participant } from '../../types';
import { TranscriptEntry } from './TranscriptEntry';
import { ChatDrawer } from './ChatDrawer';
import { AudioPlayer, AudioPlayerHandle } from './AudioPlayer';
import { useTranscriptParser } from './useTranscriptParser';
import type { ChatMessage } from '../../services/chatService';
import { formatDate, formatTime, formatDuration } from '../../utils/dateUtils';
import { formatSpeakersList } from '../../utils/formatters';
import { showToast } from '../../utils/toast';
import { recordingsService } from '../../services/recordingsService';
import { participantsService } from '../../services/participantsService';
import { transcriptionsService } from '../../services/transcriptionsService';

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
  headerTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '12px',
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
  meta: {
    display: 'flex',
    gap: '8px',
    fontSize: '13px',
    color: '#6B7280',
    marginTop: '8px',
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
  transcriptArea: {
    flex: 1,
    minHeight: 0,
    overflowY: 'auto',
    padding: '24px',
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
});

interface TranscriptViewerProps {
  transcription: Transcription | null;
  recording: Recording | null;
  loading: boolean;
}

export function TranscriptViewer({ transcription, recording, loading }: TranscriptViewerProps) {
  const styles = useStyles();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatDrawerWidth] = useState(40);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [speakerMappings, setSpeakerMappings] = useState<Record<string, string>>({});
  const [highlightedIndex, setHighlightedIndex] = useState<number | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);

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
    // Reset speaker mappings - initialize from transcription's speaker_mapping if available
    if (transcription?.speaker_mapping) {
      const initialMappings: Record<string, string> = {};
      for (const [label, mapping] of Object.entries(transcription.speaker_mapping)) {
        if (mapping.displayName || mapping.name) {
          initialMappings[label] = mapping.displayName || mapping.name;
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

  return (
    <div className={styles.viewContainer}>
      <div className={styles.container}>
        <div className={styles.header}>
          <div className={styles.headerTop}>
            <div className={styles.titleContainer}>
              <Text className={styles.title}>{recording.title || recording.original_filename}</Text>
              <div className={styles.meta}>
                {recording.recorded_timestamp && (
                  <>
                    <Text>{formatDate(recording.recorded_timestamp)}</Text>
                    <Text className={styles.metaSeparator}>•</Text>
                    <Text>{formatTime(recording.recorded_timestamp)}</Text>
                  </>
                )}
                {recording.duration && (
                  <>
                    <Text className={styles.metaSeparator}>•</Text>
                    <Text>{formatDuration(recording.duration)}</Text>
                  </>
                )}
                {recording.participants && recording.participants.length > 0 && (
                  <>
                    <Text className={styles.metaSeparator}>•</Text>
                    <Text>{formatSpeakersList(recording.participants)}</Text>
                  </>
                )}
              </div>
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
          {recording.description && (
            <div className={styles.description}>
              <Text>{recording.description}</Text>
            </div>
          )}
        </div>

        {/* Audio player - only show if we have audio and timestamps */}
        {audioUrl && hasTimestamps && (
          <AudioPlayer ref={audioPlayerRef} audioUrl={audioUrl} />
        )}

        <div className={styles.transcriptArea}>
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
                  hasTimestamp={entry.startTimeMs > 0}
                  onPlayFromTime={handlePlayFromTime}
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
