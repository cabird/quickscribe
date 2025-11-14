import { makeStyles, mergeClasses, Button, Tooltip, tokens } from '@fluentui/react-components';
import { DocumentText24Regular, ChartMultiple24Regular, Search24Regular } from '@fluentui/react-icons';
import { APP_COLORS } from '../../config/styles';

const useStyles = makeStyles({
  navRail: {
    width: '68px',
    flexShrink: 0,
    backgroundColor: APP_COLORS.navRailBg,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    paddingTop: '12px',
    gap: '8px',
    boxShadow: tokens.shadow16,
    height: '100%',
  },
  navButton: {
    width: '48px',
    height: '48px',
    minWidth: '48px',
    color: 'white',
    ':hover': {
      backgroundColor: 'rgba(255,255,255,0.1)',
    },
  },
  navButtonActive: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    ':hover': {
      backgroundColor: 'rgba(255,255,255,0.25)',
    },
  },
});

interface NavigationRailProps {
  activeView: 'transcripts' | 'logs' | 'search';
  onViewChange: (view: 'transcripts' | 'logs' | 'search') => void;
}

export function NavigationRail({ activeView, onViewChange }: NavigationRailProps) {
  const styles = useStyles();

  return (
    <div className={styles.navRail}>
      <Tooltip content="Transcripts" relationship="label">
        <Button
          appearance="transparent"
          icon={<DocumentText24Regular />}
          className={mergeClasses(styles.navButton, activeView === 'transcripts' && styles.navButtonActive)}
          onClick={() => onViewChange('transcripts')}
        />
      </Tooltip>

      <Tooltip content="Logs" relationship="label">
        <Button
          appearance="transparent"
          icon={<ChartMultiple24Regular />}
          className={mergeClasses(styles.navButton, activeView === 'logs' && styles.navButtonActive)}
          onClick={() => onViewChange('logs')}
        />
      </Tooltip>

      <Tooltip content="Search" relationship="label">
        <Button
          appearance="transparent"
          icon={<Search24Regular />}
          className={mergeClasses(styles.navButton, activeView === 'search' && styles.navButtonActive)}
          onClick={() => onViewChange('search')}
        />
      </Tooltip>
    </div>
  );
}
