import { makeStyles } from '@fluentui/react-components';

// 6 distinct speaker colors - border and name colors
const SPEAKER_COLORS = [
  { border: '#3B82F6', name: '#2563EB' },  // Blue
  { border: '#8B5CF6', name: '#7C3AED' },  // Purple
  { border: '#10B981', name: '#059669' },  // Green
  { border: '#F59E0B', name: '#D97706' },  // Amber
  { border: '#EF4444', name: '#DC2626' },  // Red
  { border: '#6366F1', name: '#4F46E5' },  // Indigo
];

const useStyles = makeStyles({
  entry: {
    display: 'flex',
    gap: '16px',
    marginBottom: '20px',
    paddingLeft: '12px',
    borderLeft: '2px solid #D1D5DB',
  },
  time: {
    width: '50px',
    flexShrink: 0,
    color: '#6B7280',
    fontSize: '13px',
  },
  content: {
    flex: 1,
  },
  speaker: {
    fontWeight: 600,
    fontSize: '13px',
    marginBottom: '4px',
  },
  text: {
    lineHeight: '1.7',
    fontSize: '15px',
    color: '#1f1f1f',
  },
});

interface TranscriptEntryProps {
  speaker: string;
  text: string;
  time?: string;
  speakerIndex: number;  // 0-based index based on order of appearance
}

export function TranscriptEntry({ speaker, text, time, speakerIndex }: TranscriptEntryProps) {
  const styles = useStyles();
  const colors = SPEAKER_COLORS[speakerIndex % 6];  // Wrap at 6 colors

  return (
    <div
      className={styles.entry}
      style={{ borderLeftColor: colors.border }}
    >
      {time && <div className={styles.time}>{time}</div>}
      <div className={styles.content}>
        <div
          className={styles.speaker}
          style={{ color: colors.name }}
        >
          {speaker}
        </div>
        <div className={styles.text}>{text}</div>
      </div>
    </div>
  );
}
