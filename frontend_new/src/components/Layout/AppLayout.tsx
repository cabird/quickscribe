import { AppShell } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { MainContent } from './MainContent';
import { AIWorkspaceModal } from '../AIWorkspace/AIWorkspaceModal';
import { useUIStore } from '../../stores/useUIStore';
import { useRecordingStore } from '../../stores/useRecordingStore';
import { useTagStore } from '../../stores/useTagStore';
import { fetchRecordings } from '../../api/recordings';
import { fetchTags } from '../../api/tags';
import { notifications } from '@mantine/notifications';

export function AppLayout() {
  const [opened] = useDisclosure();
  
  const { aiWorkspace } = useUIStore();
  const { setRecordings, updateRecording, setLoading, setError } = useRecordingStore();
  const { setTags } = useTagStore();

  // Load initial data
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        // Load recordings and tags in parallel
        const [recordings, tags] = await Promise.all([
          fetchRecordings(),
          fetchTags()
        ]);
        
        setRecordings(recordings);
        setTags(tags);
      } catch (error) {
        console.error('Failed to load initial data:', error);
        setError('Failed to load data');
        notifications.show({
          title: 'Error',
          message: 'Failed to load recordings and tags',
          color: 'red'
        });
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [setRecordings, setTags, setLoading, setError]);

  // Listen for recording update events (preserve existing functionality)
  useEffect(() => {
    const handleRecordingUpdated = (event: CustomEvent) => {
      const { recording } = event.detail;
      updateRecording(recording);
    };
    
    window.addEventListener('recordingUpdated', handleRecordingUpdated as EventListener);
    return () => {
      window.removeEventListener('recordingUpdated', handleRecordingUpdated as EventListener);
    };
  }, [updateRecording]);

  return (
    <>
      <AppShell
        navbar={{
          width: 340,
          breakpoint: 'sm',
          collapsed: { mobile: !opened },
        }}
        padding="md"
        styles={{
          navbar: {
            background: 'var(--mantine-color-white)',
            borderRight: '1px solid var(--mantine-color-gray-3)',
          },
          main: {
            background: 'linear-gradient(135deg, var(--mantine-color-gray-0) 0%, var(--mantine-color-blue-0) 100%)',
            minHeight: '100vh',
          },
        }}
      >
        <AppShell.Navbar>
          <Sidebar />
        </AppShell.Navbar>

        <AppShell.Main>
          <MainContent />
        </AppShell.Main>
      </AppShell>

      {aiWorkspace.isOpen && <AIWorkspaceModal />}
    </>
  );
}