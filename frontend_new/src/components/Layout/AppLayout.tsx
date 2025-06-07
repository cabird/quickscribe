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
      {/* Fixed Background Layer */}
      <div
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100vw',
          height: '100vh',
          background: `linear-gradient(45deg, 
            rgba(74, 144, 226, 0.15) 0%,
            rgba(138, 43, 226, 0.15) 100%
          )`,
          zIndex: -1,
          pointerEvents: 'none',
        }}
      />
      
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
            background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0.08))',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            borderBottom: '1px solid rgba(255, 255, 255, 0.15)',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.1)',
          },
          navbar: {
            background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.06))',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRight: '1px solid rgba(255, 255, 255, 0.1)',
            boxShadow: '4px 0 16px rgba(0, 0, 0, 0.08)',
          },
          main: {
            background: 'transparent',
            minHeight: '100vh',
            position: 'relative',
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