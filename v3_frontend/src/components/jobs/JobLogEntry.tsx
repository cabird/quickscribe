import { makeStyles, Text, tokens } from '@fluentui/react-components';
import type { JobLogEntry as JobLogEntryType } from '../../types';
import { formatTime } from '../../utils/dateUtils';

const useStyles = makeStyles({
  entry: {
    display: 'flex',
    gap: '12px',
    padding: '6px 0',
    fontFamily: 'monospace',
    fontSize: tokens.fontSizeBase200,
    lineHeight: '1.5',
  },
  timestamp: {
    color: tokens.colorNeutralForeground3,
    flexShrink: 0,
    width: '80px',
  },
  level: {
    flexShrink: 0,
    width: '60px',
    fontWeight: tokens.fontWeightSemibold,
  },
  levelDebug: {
    color: tokens.colorPaletteBlueForeground1,
  },
  levelInfo: {
    color: tokens.colorNeutralForeground2,
  },
  levelWarning: {
    color: tokens.colorPaletteOrangeForeground1,
  },
  levelError: {
    color: tokens.colorPaletteRedForeground1,
  },
  message: {
    flex: 1,
    wordBreak: 'break-word',
  },
});

interface JobLogEntryProps {
  log: JobLogEntryType;
}

export function JobLogEntry({ log }: JobLogEntryProps) {
  const styles = useStyles();

  const getLevelColor = () => {
    switch (log.level) {
      case 'debug':
        return '#0078D4'; // Blue
      case 'info':
        return '#616161'; // Gray
      case 'warning':
        return '#F59E0B'; // Orange
      case 'error':
        return '#D13438'; // Red
      default:
        return '#616161';
    }
  };

  const formatTimeWithSeconds = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  return (
    <div className={styles.entry}>
      <Text className={styles.timestamp}>{formatTimeWithSeconds(log.timestamp)}</Text>
      <Text className={styles.level} style={{ color: getLevelColor() }}>
        {log.level.toUpperCase()}
      </Text>
      <Text className={styles.message}>{log.message}</Text>
    </div>
  );
}
