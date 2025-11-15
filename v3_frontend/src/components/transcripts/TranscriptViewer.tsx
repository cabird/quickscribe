import { useState } from 'react';
import { makeStyles, Text, Spinner, Divider, tokens, Button, Tooltip } from '@fluentui/react-components';
import { Copy24Regular, Chat24Regular } from '@fluentui/react-icons';
import type { Recording, Transcription } from '../../types';
import { TranscriptEntry } from './TranscriptEntry';
import { ChatDrawer } from './ChatDrawer';
import type { ChatMessage } from '../../services/chatService';
import { formatDate, formatTime, formatDuration } from '../../utils/dateUtils';
import { formatSpeakersList } from '../../utils/formatters';
import { showToast } from '../../utils/toast';

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
    gap: '8px',
  },
  header: {
    padding: '24px',
    flexShrink: 0,
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
  },
  title: {
    fontSize: tokens.fontSizeBase500,
    fontWeight: tokens.fontWeightSemibold,
  },
  guid: {
    fontSize: tokens.fontSizeBase100,
    color: tokens.colorNeutralForeground3,
    fontFamily: 'monospace',
  },
  meta: {
    display: 'flex',
    gap: '16px',
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
    marginBottom: '8px',
  },
  description: {
    fontSize: tokens.fontSizeBase300,
    color: tokens.colorNeutralForeground2,
    marginTop: '8px',
  },
  divider: {
    flexShrink: 0,
    flexGrow: 0,
    flexBasis: 'auto',
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
  const [chatDrawerWidth, setChatDrawerWidth] = useState(40); // percentage
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]); // Persist chat messages across re-renders

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

  // Parse the diarized transcript into entries
  const transcriptEntries: Array<{ speaker: string; text: string }> = [];

  if (transcription.diarized_transcript) {
    // Split by double newlines to get paragraphs
    const paragraphs = transcription.diarized_transcript.split('\n\n').filter(p => p.trim());

    paragraphs.forEach((paragraph) => {
      // Each paragraph should be "Speaker X: text"
      const match = paragraph.match(/^(.+?):\s*(.+)$/s); // 's' flag allows . to match newlines
      if (match) {
        const speakerLabel = match[1].trim();

        // Map speaker label to actual name if speaker_mapping exists
        let displayName = speakerLabel;
        if (transcription.speaker_mapping && transcription.speaker_mapping[speakerLabel]) {
          displayName = transcription.speaker_mapping[speakerLabel].displayName || speakerLabel;
        }

        transcriptEntries.push({
          speaker: displayName,
          text: match[2].trim(),
        });
      }
    });
  }

  // Fallback: if no diarized transcript, try plain text
  if (transcriptEntries.length === 0 && transcription.text) {
    // Split into paragraphs and show as plain text
    const paragraphs = transcription.text.split('\n\n').filter(p => p.trim());
    paragraphs.forEach((para) => {
      transcriptEntries.push({
        speaker: 'Speaker',
        text: para.trim(),
      });
    });
  }

  const handleRefClick = (transcriptIndex: number) => {
    // Scroll to the transcript entry - use data attribute instead of CSS class
    const transcriptArea = document.querySelector('[data-transcript-area]');
    if (transcriptArea) {
      const entries = transcriptArea.querySelectorAll('[data-transcript-entry]');
      const targetEntry = entries[transcriptIndex] as HTMLElement;
      if (targetEntry) {
        targetEntry.scrollIntoView({ behavior: 'smooth', block: 'center' });
        // Highlight temporarily
        targetEntry.style.backgroundColor = '#fff3cd';
        setTimeout(() => {
          targetEntry.style.backgroundColor = '';
        }, 2000);
      }
    }
  };

  return (
    <div className={styles.viewContainer}>
      <div className={styles.container}>
        <div className={styles.header}>
          <div className={styles.headerTop}>
            <div className={styles.titleContainer}>
              <Text className={styles.title}>{recording.title || recording.original_filename}</Text>
              {transcription && (
                <Text className={styles.guid}>{transcription.id}</Text>
              )}
            </div>
            <div className={styles.headerButtons}>
              <Tooltip content="Chat with transcript" relationship="label">
                <Button
                  appearance="subtle"
                  icon={<Chat24Regular />}
                  onClick={() => setIsChatOpen(!isChatOpen)}
                />
              </Tooltip>
              <Tooltip content="Copy transcript to clipboard" relationship="label">
                <Button
                  appearance="subtle"
                  icon={<Copy24Regular />}
                  onClick={handleCopyTranscript}
                />
              </Tooltip>
            </div>
          </div>
          <div className={styles.meta}>
            {recording.recorded_timestamp && (
              <Text>
                {formatDate(recording.recorded_timestamp)} • {formatTime(recording.recorded_timestamp)}
              </Text>
            )}
            {recording.duration && <Text>• {formatDuration(recording.duration)}</Text>}
            {recording.participants && recording.participants.length > 0 && (
              <Text>• {formatSpeakersList(recording.participants)}</Text>
            )}
          </div>
          {recording.description && (
            <div className={styles.description}>
              <Text>{recording.description}</Text>
            </div>
          )}
        </div>

        <Divider className={styles.divider} />

        <div className={styles.transcriptArea} data-transcript-area>
          {transcriptEntries.length > 0 ? (
            transcriptEntries.map((entry, index) => (
              <div key={index} data-transcript-entry>
                <TranscriptEntry speaker={entry.speaker} text={entry.text} />
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
            transcriptionId={transcription.id}
            transcriptEntries={transcriptEntries}
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
