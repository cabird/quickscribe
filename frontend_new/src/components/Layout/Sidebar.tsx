import { Stack, Group, Text, UnstyledButton, rem } from '@mantine/core';
import { LuUpload, LuSearch, LuSettings } from 'react-icons/lu';
import { useUIStore } from '../../stores/useUIStore';
import { lazy, Suspense, memo } from 'react';

// Lazy load tab components to reduce initial bundle and improve tab switching
const UploadTab = lazy(() => import('./UploadTab').then(module => ({ default: module.UploadTab })));
const BrowseTab = lazy(() => import('./BrowseTab').then(module => ({ default: module.BrowseTab })));
const SettingsTab = lazy(() => import('./SettingsTab').then(module => ({ default: module.SettingsTab })));

const tabs = [
  { value: 'upload', label: 'Upload', icon: LuUpload },
  { value: 'browse', label: 'Browse', icon: LuSearch },
  { value: 'settings', label: 'Settings', icon: LuSettings },
] as const;

export const Sidebar = memo(function Sidebar() {
  const { sidebarTab, setSidebarTab } = useUIStore();

  return (
    <Stack h="100%" gap={0}>
      {/* Header */}
      <Stack p="lg" gap="md">
        <Group justify="center">
          <Text size="xl" fw={700} c="dark">
            Quick<Text span c="orange" inherit>Scribe</Text>
          </Text>
        </Group>

        {/* Tab Navigation */}
        <Group grow>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = sidebarTab === tab.value;
            
            return (
              <UnstyledButton
                key={tab.value}
                onClick={() => setSidebarTab(tab.value)}
                style={{
                  padding: rem(8),
                  borderRadius: rem(12),
                  background: isActive 
                    ? 'linear-gradient(135deg, rgba(74, 144, 226, 0.25), rgba(74, 144, 226, 0.15))'
                    : 'linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05))',
                  backdropFilter: 'blur(8px)',
                  border: `1px solid ${isActive ? 'rgba(74, 144, 226, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
                  color: isActive ? 'var(--mantine-color-blue-filled)' : 'var(--mantine-color-gray-7)',
                  textAlign: 'center',
                  transition: 'all 300ms ease',
                  boxShadow: isActive ? '0 4px 16px rgba(74, 144, 226, 0.2)' : '0 2px 8px rgba(0, 0, 0, 0.1)',
                }}
              >
                <Stack align="center" gap={4}>
                  <Icon size={18} />
                  <Text size="xs" fw={500}>
                    {tab.label}
                  </Text>
                </Stack>
              </UnstyledButton>
            );
          })}
        </Group>
      </Stack>

      {/* Tab Content */}
      <Stack flex={1} p="lg" pt={0}>
        <Suspense fallback={<div>Loading...</div>}>
          {sidebarTab === 'upload' && <UploadTab />}
          {sidebarTab === 'browse' && <BrowseTab />}
          {sidebarTab === 'settings' && <SettingsTab />}
        </Suspense>
      </Stack>
    </Stack>
  );
});