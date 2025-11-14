import { makeStyles, Text, Spinner, Divider, tokens } from '@fluentui/react-components';
import type { Recording, Transcription } from '../../types';
import { TranscriptEntry } from './TranscriptEntry';
import { formatDate, formatTime, formatDuration } from '../../utils/dateUtils';
import { formatSpeakersList } from '../../utils/formatters';

const useStyles = makeStyles({
  container: {
    flex: 1,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: 'hidden',
  },
  header: {
    padding: '24px',
    flexShrink: 0,
  },
  title: {
    fontSize: tokens.fontSizeBase500,
    fontWeight: tokens.fontWeightSemibold,
    marginBottom: '12px',
  },
  meta: {
    display: 'flex',
    gap: '16px',
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
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
        transcriptEntries.push({
          speaker: match[1].trim(),
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

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Text className={styles.title}>{recording.title || recording.original_filename}</Text>
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
      </div>

      <Divider className={styles.divider} />

      <div className={styles.transcriptArea}>
        {transcriptEntries.length > 0 ? (
          transcriptEntries.map((entry, index) => (
            <TranscriptEntry key={index} speaker={entry.speaker} text={entry.text} />
          ))
        ) : (
          <div className={styles.emptyState}>
            <Text>No transcript available</Text>
          </div>
        )}
      </div>
    </div>
  );
}
