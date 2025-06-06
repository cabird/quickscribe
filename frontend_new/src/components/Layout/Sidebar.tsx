import { Stack, Group, Text, UnstyledButton, rem } from '@mantine/core';
import { IconUpload, IconSearch, IconSettings } from '@tabler/icons-react';
import { useUIStore } from '../../stores/useUIStore';
import { UploadTab } from './UploadTab';
import { BrowseTab } from './BrowseTab';
import { SettingsTab } from './SettingsTab';

const tabs = [
  { value: 'upload', label: 'Upload', icon: IconUpload },
  { value: 'browse', label: 'Browse', icon: IconSearch },
  { value: 'settings', label: 'Settings', icon: IconSettings },
] as const;

export function Sidebar() {
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
                  borderRadius: rem(6),
                  backgroundColor: isActive ? 'var(--mantine-color-blue-light)' : 'var(--mantine-color-gray-0)',
                  color: isActive ? 'var(--mantine-color-blue-filled)' : 'var(--mantine-color-gray-7)',
                  textAlign: 'center',
                  transition: 'all 200ms ease',
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
        {sidebarTab === 'upload' && <UploadTab />}
        {sidebarTab === 'browse' && <BrowseTab />}
        {sidebarTab === 'settings' && <SettingsTab />}
      </Stack>
    </Stack>
  );
}