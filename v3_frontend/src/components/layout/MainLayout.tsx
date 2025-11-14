import { useState } from 'react';
import { makeStyles } from '@fluentui/react-components';
import { NavigationRail } from './NavigationRail';
import { TranscriptsView } from '../transcripts/TranscriptsView';
import { LogsPlaceholder } from '../logs/LogsPlaceholder';
import { SearchPlaceholder } from '../search/SearchPlaceholder';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    height: '100%',
    width: '100%',
    overflow: 'hidden',
  },
  mainContent: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
});

export function MainLayout() {
  const styles = useStyles();
  const [activeView, setActiveView] = useState<'transcripts' | 'logs' | 'search'>('transcripts');

  return (
    <div className={styles.container}>
      <NavigationRail activeView={activeView} onViewChange={setActiveView} />
      <div className={styles.mainContent}>
        {activeView === 'transcripts' && <TranscriptsView />}
        {activeView === 'logs' && <LogsPlaceholder />}
        {activeView === 'search' && <SearchPlaceholder />}
      </div>
    </div>
  );
}
