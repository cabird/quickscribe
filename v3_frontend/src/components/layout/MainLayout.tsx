import { useState, useEffect, useCallback } from 'react';
import { makeStyles } from '@fluentui/react-components';
import { NavigationRail } from './NavigationRail';
import { TranscriptsView } from '../transcripts/TranscriptsView';
import { PeopleView } from '../people/PeopleView';
import { SpeakerReviewView } from '../reviews/SpeakerReviewView';
import { JobsView } from '../jobs/JobsView';
import { SearchPlaceholder } from '../search/SearchPlaceholder';
import { SettingsView } from '../settings/SettingsView';
import { useIsMobile } from '../../hooks/useIsMobile';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    flex: 1,
    width: '100%',
    overflow: 'hidden',
  },
  containerMobile: {
    flexDirection: 'column',
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
  const isMobile = useIsMobile();
  const [activeView, setActiveView] = useState<'transcripts' | 'people' | 'reviews' | 'logs' | 'search' | 'settings'>('transcripts');
  const [pendingRecordingId, setPendingRecordingId] = useState<string | null>(null);

  // Handle navigation to a specific recording from other views (e.g., People view)
  const handleNavigateToRecording = useCallback((event: Event) => {
    const customEvent = event as CustomEvent<{ recordingId: string }>;
    const { recordingId } = customEvent.detail;
    setPendingRecordingId(recordingId);
    setActiveView('transcripts');
  }, []);

  useEffect(() => {
    window.addEventListener('navigateToRecording', handleNavigateToRecording);
    return () => {
      window.removeEventListener('navigateToRecording', handleNavigateToRecording);
    };
  }, [handleNavigateToRecording]);

  // Clear pending recording ID after TranscriptsView has had a chance to use it
  const handleRecordingNavigated = useCallback(() => {
    setPendingRecordingId(null);
  }, []);

  return (
    <div className={`${styles.container} ${isMobile ? styles.containerMobile : ''}`}>
      {/* On desktop, sidebar is first (left). On mobile, content is first (top). */}
      {!isMobile && <NavigationRail activeView={activeView} onViewChange={setActiveView} />}
      <div className={styles.mainContent}>
        {activeView === 'transcripts' && (
          <TranscriptsView
            navigateToRecordingId={pendingRecordingId}
            onNavigationComplete={handleRecordingNavigated}
          />
        )}
        {activeView === 'people' && <PeopleView />}
        {activeView === 'reviews' && <SpeakerReviewView />}
        {activeView === 'logs' && <JobsView />}
        {activeView === 'search' && <SearchPlaceholder />}
        {activeView === 'settings' && <SettingsView />}
      </div>
      {isMobile && <NavigationRail activeView={activeView} onViewChange={setActiveView} />}
    </div>
  );
}
