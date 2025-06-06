import { Stack, Text, Switch, Group, Divider } from '@mantine/core';
import { useState } from 'react';

export function SettingsTab() {
  const [autoTranscribe, setAutoTranscribe] = useState(true);
  const [speakerID, setSpeakerID] = useState(true);
  const [removeNoise, setRemoveNoise] = useState(false);
  const [autoSuggestTags, setAutoSuggestTags] = useState(true);
  const [requireTags, setRequireTags] = useState(false);
  const [emailNotifications, setEmailNotifications] = useState(false);
  const [pushNotifications, setPushNotifications] = useState(true);
  const [darkMode, setDarkMode] = useState(false);

  return (
    <Stack gap="md">
      <Text fw={600} size="lg">Settings & Preferences</Text>
      
      {/* Transcription Settings */}
      <Stack gap="xs">
        <Text fw={500} size="sm" c="dark">Transcription</Text>
        
        <Group justify="space-between">
          <div>
            <Text size="sm">Auto-transcribe uploads</Text>
            <Text size="xs" c="dimmed">Automatically start transcription when files are uploaded</Text>
          </div>
          <Switch
            checked={autoTranscribe}
            onChange={(e) => setAutoTranscribe(e.currentTarget.checked)}
          />
        </Group>

        <Group justify="space-between">
          <div>
            <Text size="sm">Speaker identification</Text>
            <Text size="xs" c="dimmed">Automatically identify different speakers</Text>
          </div>
          <Switch
            checked={speakerID}
            onChange={(e) => setSpeakerID(e.currentTarget.checked)}
          />
        </Group>

        <Group justify="space-between">
          <div>
            <Text size="sm">Background noise removal</Text>
            <Text size="xs" c="dimmed">Clean up audio before transcription</Text>
          </div>
          <Switch
            checked={removeNoise}
            onChange={(e) => setRemoveNoise(e.currentTarget.checked)}
          />
        </Group>
      </Stack>

      <Divider />

      {/* Tagging Settings */}
      <Stack gap="xs">
        <Text fw={500} size="sm" c="dark">Tagging</Text>
        
        <Group justify="space-between">
          <div>
            <Text size="sm">Auto-suggest tags</Text>
            <Text size="xs" c="dimmed">Automatically suggest tags based on content</Text>
          </div>
          <Switch
            checked={autoSuggestTags}
            onChange={(e) => setAutoSuggestTags(e.currentTarget.checked)}
          />
        </Group>

        <Group justify="space-between">
          <div>
            <Text size="sm">Require tags for uploads</Text>
            <Text size="xs" c="dimmed">Force users to tag recordings before saving</Text>
          </div>
          <Switch
            checked={requireTags}
            onChange={(e) => setRequireTags(e.currentTarget.checked)}
          />
        </Group>
      </Stack>

      <Divider />

      {/* Notification Settings */}
      <Stack gap="xs">
        <Text fw={500} size="sm" c="dark">Notifications</Text>
        
        <Group justify="space-between">
          <div>
            <Text size="sm">Email notifications</Text>
            <Text size="xs" c="dimmed">Get notified when transcriptions complete</Text>
          </div>
          <Switch
            checked={emailNotifications}
            onChange={(e) => setEmailNotifications(e.currentTarget.checked)}
          />
        </Group>

        <Group justify="space-between">
          <div>
            <Text size="sm">Push notifications</Text>
            <Text size="xs" c="dimmed">Browser notifications for updates</Text>
          </div>
          <Switch
            checked={pushNotifications}
            onChange={(e) => setPushNotifications(e.currentTarget.checked)}
          />
        </Group>
      </Stack>

      <Divider />

      {/* Appearance Settings */}
      <Stack gap="xs">
        <Text fw={500} size="sm" c="dark">Appearance</Text>
        
        <Group justify="space-between">
          <div>
            <Text size="sm">Dark mode</Text>
            <Text size="xs" c="dimmed">Use dark theme interface</Text>
          </div>
          <Switch
            checked={darkMode}
            onChange={(e) => setDarkMode(e.currentTarget.checked)}
          />
        </Group>
      </Stack>
    </Stack>
  );
}