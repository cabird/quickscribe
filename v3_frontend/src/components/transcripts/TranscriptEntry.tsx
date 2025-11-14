import { makeStyles } from '@fluentui/react-components';
import { APP_COLORS } from '../../config/styles';

const useStyles = makeStyles({
  entry: {
    display: 'flex',
    gap: '16px',
    marginBottom: '16px',
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
    color: APP_COLORS.transcriptSpeaker,
    marginBottom: '4px',
  },
  text: {
    lineHeight: '1.6',
    fontSize: '14px',
  },
});

interface TranscriptEntryProps {
  speaker: string;
  text: string;
  time?: string;
}

export function TranscriptEntry({ speaker, text, time }: TranscriptEntryProps) {
  const styles = useStyles();

  return (
    <div className={styles.entry}>
      {time && <div className={styles.time}>{time}</div>}
      <div className={styles.content}>
        <div className={styles.speaker}>{speaker}</div>
        <div className={styles.text}>{text}</div>
      </div>
    </div>
  );
}
