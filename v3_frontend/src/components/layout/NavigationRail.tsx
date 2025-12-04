import { useState, useEffect } from 'react';
import { makeStyles, mergeClasses, Button, Tooltip, Text, tokens } from '@fluentui/react-components';
import { DocumentText24Regular, TaskListLtr24Regular, Search24Regular, Settings24Regular } from '@fluentui/react-icons';
import { APP_COLORS } from '../../config/styles';
import { versionService } from '../../services/versionService';

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
  spacer: {
    flexGrow: 1,
  },
  version: {
    fontSize: tokens.fontSizeBase200,
    color: 'rgba(255,255,255,0.6)',
    paddingBottom: '16px',
    textAlign: 'center',
    userSelect: 'text',
  },
});

interface NavigationRailProps {
  activeView: 'transcripts' | 'logs' | 'search' | 'settings';
  onViewChange: (view: 'transcripts' | 'logs' | 'search' | 'settings') => void;
}

export function NavigationRail({ activeView, onViewChange }: NavigationRailProps) {
  const styles = useStyles();
  const [version, setVersion] = useState<string>('...');

  useEffect(() => {
    versionService.getVersion().then(setVersion);
  }, []);

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

      <Tooltip content="Job Logs" relationship="label">
        <Button
          appearance="transparent"
          icon={<TaskListLtr24Regular />}
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

      <div className={styles.spacer} />

      <Tooltip content="Settings" relationship="label">
        <Button
          appearance="transparent"
          icon={<Settings24Regular />}
          className={mergeClasses(styles.navButton, activeView === 'settings' && styles.navButtonActive)}
          onClick={() => onViewChange('settings')}
        />
      </Tooltip>

      <Tooltip content={`API Version: ${version}`} relationship="label">
        <Text className={styles.version}>v{version}</Text>
      </Tooltip>
    </div>
  );
}
