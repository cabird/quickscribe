import { Stack, Text, Button, Checkbox, Group, Progress, Alert } from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import type { FileWithPath } from '@mantine/dropzone';
import { 
  LuUpload, 
  LuX, 
  LuFile, 
  LuCircleAlert,
  LuFolder,
  LuRefreshCw
} from 'react-icons/lu';
import { useState, useEffect, useRef } from 'react';
import { uploadFile } from '../../api/recordings';
import { useRecordingStore } from '../../stores/useRecordingStore';
import { useUIStore } from '../../stores/useUIStore';
import { showNotificationFromApiResponse } from '../../utils';
import { fetchRecordings } from '../../api/recordings';
import { startPlaudSync, getSyncProgress, checkActiveSync } from '../../api/plaud';
import { notifications } from '@mantine/notifications';
import type { SyncProgress } from '../../types/index';

export function UploadTab() {
  const [autoTranscribe, setAutoTranscribe] = useState(true);
  const [speakerID, setSpeakerID] = useState(true);
  const [removeNoise, setRemoveNoise] = useState(false);
  const [detectContent, setDetectContent] = useState(true);
  const [suggestTags, setSuggestTags] = useState(false);
  
  // Sync progress state
  const [syncProgress, setSyncProgress] = useState<SyncProgress | null>(null);
  const [syncToken, setSyncToken] = useState<string | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const { setRecordings } = useRecordingStore();
  const { uploadLoading, setUploadLoading } = useUIStore();

  // Check for active sync on component mount and cleanup on unmount
  useEffect(() => {
    const checkForActiveSync = async () => {
      try {
        const activeSync = await checkActiveSync();
        if (activeSync.has_active_sync && activeSync.sync_token && activeSync.progress) {
          // Resume monitoring existing sync
          setSyncToken(activeSync.sync_token);
          setSyncProgress(activeSync.progress);
          startPolling(activeSync.sync_token);
          
          console.log('Resumed monitoring active sync:', activeSync.sync_token);
        }
      } catch (error) {
        console.error('Failed to check for active sync:', error);
      }
    };
    
    checkForActiveSync();
    
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Start polling for sync progress
  const startPolling = (token: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const progress = await getSyncProgress(token);
        setSyncProgress(progress);

        // Stop polling if sync is completed or failed
        if (progress.status === 'completed' || progress.status === 'failed') {
          stopPolling();
          
          // Refresh recordings list when completed
          if (progress.status === 'completed') {
            try {
              const updatedRecordings = await fetchRecordings();
              setRecordings(updatedRecordings);
            } catch (error) {
              console.error('Failed to refresh recordings after sync completion:', error);
            }
          }
        }
      } catch (error) {
        console.error('Failed to fetch sync progress:', error);
        // Continue polling unless it's a 404 (progress not found)
        if (error.response?.status === 404) {
          stopPolling();
          setSyncProgress(null);
        }
      }
    }, 10000); // Poll every 10 seconds
  };

  // Stop polling
  const stopPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

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

  const handlePlaudSync = async () => {
    // Don't allow starting sync if one is already in progress
    if (syncProgress && (syncProgress.status === 'queued' || syncProgress.status === 'processing')) {
      notifications.show({
        title: 'Sync Already in Progress',
        message: 'Please wait for the current sync to complete.',
        color: 'orange',
      });
      return;
    }

    setUploadLoading(true);
    
    try {
      const response = await startPlaudSync(false); // dry_run = false for real sync
      
      // Set sync token and start polling
      setSyncToken(response.sync_token);
      startPolling(response.sync_token);
      
      notifications.show({
        title: 'Plaud Sync Started',
        message: response.message || 'Your Plaud recordings are being synced in the background.',
        color: 'green',
      });
      
    } catch (error: any) {
      console.error('Plaud sync error:', error);
      
      // Handle 409 - sync already in progress
      if (error.response?.status === 409) {
        const activeToken = error.response?.data?.active_sync_token;
        if (activeToken) {
          // Resume monitoring existing sync instead of failing
          setSyncToken(activeToken);
          startPolling(activeToken);
          
          notifications.show({
            title: 'Sync Already Running',
            message: 'Resuming monitoring of your active sync...',
            color: 'blue',
          });
          return;
        }
      }
      
      const errorMessage = error.response?.data?.error || error.message || 'Failed to start Plaud sync';
      
      notifications.show({
        title: 'Plaud Sync Failed',
        message: errorMessage,
        color: 'red',
      });
    } finally {
      setUploadLoading(false);
    }
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
            backgroundColor: 'rgba(255, 255, 255, 0.8)',
            backdropFilter: 'blur(8px)',
            border: '2px dashed rgba(74, 144, 226, 0.4)',
            '&:hover': {
              borderColor: 'var(--mantine-color-blue-6)',
              backgroundColor: 'rgba(74, 144, 226, 0.1)',
              borderStyle: 'dashed',
            },
          },
        }}
      >
        <Group justify="center" gap="sm" style={{ pointerEvents: 'none' }}>
          <Dropzone.Accept>
            <LuUpload size={40} color="var(--mantine-color-blue-6)" />
          </Dropzone.Accept>
          <Dropzone.Reject>
            <LuX size={40} color="var(--mantine-color-red-6)" />
          </Dropzone.Reject>
          <Dropzone.Idle>
            <LuFile size={40} color="var(--mantine-color-gray-6)" />
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
          color="blue"
          onClick={() => (document.querySelector('input[type="file"]') as HTMLInputElement)?.click()}
          loading={uploadLoading}
        >
          <Group gap="xs">
            <LuFolder size={16} />
            <span>Select Files</span>
          </Group>
        </Button>
        <Button 
          fullWidth 
          variant="light"
          color="orange"
          onClick={handlePlaudSync}
          loading={uploadLoading}
          disabled={syncProgress && (syncProgress.status === 'queued' || syncProgress.status === 'processing')}
        >
          <Group gap="xs">
            <LuRefreshCw size={16} />
            <span>Sync from Plaud</span>
          </Group>
        </Button>
      </Stack>

      {/* Sync Progress Display */}
      {syncProgress && (
        <Stack gap="xs" mt="md">
          <Text fw={500} size="sm" c="dark">Plaud Sync Progress</Text>
          
          {/* Status message */}
          <Text size="sm" c="dimmed">
            {syncProgress.currentStep}
          </Text>
          
          {/* Progress bar (only show if we have total recordings) */}
          {syncProgress.totalRecordings && syncProgress.totalRecordings > 0 && (
            <Stack gap="xs">
              <Progress 
                value={Math.min(100, ((syncProgress.processedRecordings + syncProgress.failedRecordings) / syncProgress.totalRecordings) * 100)}
                color={syncProgress.status === 'failed' ? 'red' : syncProgress.status === 'completed' ? 'green' : 'blue'}
                size="md"
                radius="md"
              />
              <Text size="xs" c="dimmed" ta="center">
                {syncProgress.processedRecordings + syncProgress.failedRecordings} / {syncProgress.totalRecordings} recordings processed
                {syncProgress.failedRecordings > 0 && (
                  <span style={{ color: 'var(--mantine-color-red-6)' }}>
                    {' '}({syncProgress.failedRecordings} failed)
                  </span>
                )}
              </Text>
            </Stack>
          )}
          
          {/* Status indicator */}
          <Text size="xs" fw={500} 
                c={syncProgress.status === 'completed' ? 'green' : 
                  syncProgress.status === 'failed' ? 'red' : 
                  syncProgress.status === 'processing' ? 'blue' : 'orange'}>
            Status: {syncProgress.status.charAt(0).toUpperCase() + syncProgress.status.slice(1)}
          </Text>
          
          {/* Error messages */}
          {syncProgress.errors && syncProgress.errors.length > 0 && (
            <Alert 
              icon={<LuCircleAlert size={16} />} 
              title="Some recordings failed" 
              color="orange"
              variant="light"
            >
              <Stack gap="xs">
                {syncProgress.errors.slice(0, 3).map((error, index) => (
                  <Text key={index} size="xs">{error}</Text>
                ))}
                {syncProgress.errors.length > 3 && (
                  <Text size="xs" c="dimmed">
                    ... and {syncProgress.errors.length - 3} more errors
                  </Text>
                )}
              </Stack>
            </Alert>
          )}
        </Stack>
      )}
    </Stack>
  );
}