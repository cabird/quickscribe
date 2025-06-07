import { AppShell, Group } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { MainContent } from './MainContent';
import { AIWorkspaceModal } from '../AIWorkspace/AIWorkspaceModal';
import { LocalAuthDropdown } from '../LocalAuthDropdown';
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

  // Load initial data
  useEffect(() => {
    loadData();
  }, [setRecordings, setTags, setLoading, setError]);

  // Listen for recording update events (preserve existing functionality)
  useEffect(() => {
    const handleRecordingUpdated = (event: CustomEvent) => {
      const { recording } = event.detail;
      updateRecording(recording);
    };

    const handleUserDataReset = () => {
      // Reload all data when user data is reset
      loadData();
    };
    
    window.addEventListener('recordingUpdated', handleRecordingUpdated as EventListener);
    window.addEventListener('userDataReset', handleUserDataReset as EventListener);
    return () => {
      window.removeEventListener('recordingUpdated', handleRecordingUpdated as EventListener);
      window.removeEventListener('userDataReset', handleUserDataReset as EventListener);
    };
  }, [updateRecording, loadData]);

  return (
    <>
      <AppShell
        header={{ height: 60 }}
        navbar={{
          width: 340,
          breakpoint: 'sm',
          collapsed: { mobile: !opened },
        }}
        padding="md"
        styles={{
          header: {
            background: 'var(--mantine-color-white)',
            borderBottom: '1px solid var(--mantine-color-gray-3)',
          },
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
        <AppShell.Header>
          <Group h="100%" px="md" justify="space-between" align="center">
            <Group>
              {/* Future: App title/logo could go here */}
            </Group>
            <LocalAuthDropdown onUserChange={(user) => {
              if (user) {
                // Reload data when user changes
                loadData();
              }
            }} />
          </Group>
        </AppShell.Header>

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