import { Stack, Text, Button, Checkbox, Group } from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import type { FileWithPath } from '@mantine/dropzone';
import { IconUpload, IconX, IconFile } from '@tabler/icons-react';
import { useState } from 'react';
import { uploadFile } from '../../api/recordings';
import { useRecordingStore } from '../../stores/useRecordingStore';
import { useUIStore } from '../../stores/useUIStore';
import { showNotificationFromApiResponse } from '../../utils';
import { fetchRecordings } from '../../api/recordings';

export function UploadTab() {
  const [autoTranscribe, setAutoTranscribe] = useState(true);
  const [speakerID, setSpeakerID] = useState(true);
  const [removeNoise, setRemoveNoise] = useState(false);
  const [detectContent, setDetectContent] = useState(true);
  const [suggestTags, setSuggestTags] = useState(false);

  const { setRecordings } = useRecordingStore();
  const { uploadLoading, setUploadLoading } = useUIStore();

  const handleFileDrop = async (files: FileWithPath[]) => {
    if (files.length === 0) return;

    setUploadLoading(true);
    
    try {
      for (const file of files) {
        const response = await uploadFile(file);
        showNotificationFromApiResponse(response);
      }
      
      // Refresh recordings list after upload
      const updatedRecordings = await fetchRecordings();
      setRecordings(updatedRecordings);
      
    } catch (error) {
      console.error('Upload error:', error);
    } finally {
      setUploadLoading(false);
    }
  };

  const handlePlaudSync = () => {
    // Placeholder for Plaud sync functionality
    console.log('Plaud sync triggered');
  };

  return (
    <Stack gap="md">
      <Text fw={600} size="lg">Upload Audio Files</Text>
      
      <Dropzone
        onDrop={handleFileDrop}
        accept={['audio/*']}
        loading={uploadLoading}
        styles={{
          root: {
            borderStyle: 'dashed',
            borderWidth: 2,
            borderRadius: 12,
            padding: '2rem',
            textAlign: 'center',
            cursor: 'pointer',
            transition: 'all 200ms ease',
            '&:hover': {
              borderColor: 'var(--mantine-color-blue-6)',
              backgroundColor: 'var(--mantine-color-blue-0)',
            },
          },
        }}
      >
        <Group justify="center" gap="sm" style={{ pointerEvents: 'none' }}>
          <Dropzone.Accept>
            <IconUpload size={40} color="var(--mantine-color-blue-6)" />
          </Dropzone.Accept>
          <Dropzone.Reject>
            <IconX size={40} color="var(--mantine-color-red-6)" />
          </Dropzone.Reject>
          <Dropzone.Idle>
            <IconFile size={40} color="var(--mantine-color-gray-6)" />
          </Dropzone.Idle>
        </Group>

        <Text size="lg" fw={500} mt="md">
          Drop files here or click to browse
        </Text>
        <Text size="sm" c="dimmed">
          Supports MP3, WAV, M4A, and other audio formats
        </Text>
      </Dropzone>

      {/* Processing Options */}
      <Stack gap="xs">
        <Text fw={500} size="sm" c="dark">Processing Options</Text>
        <Checkbox
          label="Auto-transcribe"
          checked={autoTranscribe}
          onChange={(e) => setAutoTranscribe(e.currentTarget.checked)}
        />
        <Checkbox
          label="Speaker identification"
          checked={speakerID}
          onChange={(e) => setSpeakerID(e.currentTarget.checked)}
        />
        <Checkbox
          label="Remove background noise"
          checked={removeNoise}
          onChange={(e) => setRemoveNoise(e.currentTarget.checked)}
        />
      </Stack>

      {/* Auto-tagging Options */}
      <Stack gap="xs">
        <Text fw={500} size="sm" c="dark">Auto-tagging</Text>
        <Checkbox
          label="Detect content type"
          checked={detectContent}
          onChange={(e) => setDetectContent(e.currentTarget.checked)}
        />
        <Checkbox
          label="Suggest tags"
          checked={suggestTags}
          onChange={(e) => setSuggestTags(e.currentTarget.checked)}
        />
      </Stack>

      {/* Action Buttons */}
      <Stack gap="xs" mt="md">
        <Button 
          fullWidth 
          variant="filled"
          onClick={() => (document.querySelector('input[type="file"]') as HTMLInputElement)?.click()}
          loading={uploadLoading}
        >
          📂 Select Files
        </Button>
        <Button 
          fullWidth 
          variant="light"
          color="orange"
          onClick={handlePlaudSync}
        >
          🔄 Sync from Plaud
        </Button>
      </Stack>
    </Stack>
  );
}