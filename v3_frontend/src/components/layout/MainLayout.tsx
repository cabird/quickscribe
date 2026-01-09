import { useState } from 'react';
import { makeStyles } from '@fluentui/react-components';
import { NavigationRail } from './NavigationRail';
import { TranscriptsView } from '../transcripts/TranscriptsView';
import { PeopleView } from '../people/PeopleView';
import { JobsView } from '../jobs/JobsView';
import { SearchPlaceholder } from '../search/SearchPlaceholder';
import { SettingsView } from '../settings/SettingsView';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    flex: 1,
    width: '100%',
    overflow: 'hidden',
  },
  mainContent: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    minHeight: 0,
  },
});

export function MainLayout() {
  const styles = useStyles();
  const [activeView, setActiveView] = useState<'transcripts' | 'people' | 'logs' | 'search' | 'settings'>('transcripts');

  return (
    <div className={styles.container}>
      <NavigationRail activeView={activeView} onViewChange={setActiveView} />
      <div className={styles.mainContent}>
        {activeView === 'transcripts' && <TranscriptsView />}
        {activeView === 'people' && <PeopleView />}
        {activeView === 'logs' && <JobsView />}
        {activeView === 'search' && <SearchPlaceholder />}
        {activeView === 'settings' && <SettingsView />}
      </div>
    </div>
  );
}
