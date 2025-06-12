import { Card, Group, Text, Badge, Button, Stack, ActionIcon, Menu } from '@mantine/core';
import { 
  LuEllipsis, 
  LuEye, 
  LuDownload, 
  LuTag, 
  LuTrash2, 
  LuPlay, 
  LuCheck, 
  LuRefreshCw,
  LuList
} from 'react-icons/lu';
import { useState, useEffect } from 'react';
import type { Recording, Tag } from '../../types';
import { useUIStore } from '../../stores/useUIStore';
import { useRecordingStore } from '../../stores/useRecordingStore';
import { formatDuration, getStatusColor, getStatusText, dispatchRecordingUpdate, showNotificationFromApiResponse } from '../../utils';
import { startTranscription, deleteRecording, deleteTranscription, checkTranscriptionStatus, fetchRecording } from '../../api/recordings';
import { addTagToRecording, removeTagFromRecording } from '../../api/tags';
import { notifications } from '@mantine/notifications';
import { TagBadge } from '../Tags/TagBadge';
import { ParticipantBadge } from '../ParticipantBadge';

interface RecordingCardProps {
  recording: Recording;
  userTags: Tag[];
}

export function RecordingCard({ recording: initialRecording, userTags }: RecordingCardProps) {
  const [recording, setRecording] = useState(initialRecording);
  const [transcriptionStatus, setTranscriptionStatus] = useState<'not_started' | 'in_progress' | 'completed' | 'failed'>((recording.transcription_status as 'not_started' | 'in_progress' | 'completed' | 'failed') || 'not_started');
  
  const { openAIWorkspace } = useUIStore();
  const { removeRecording } = useRecordingStore();

  // Get tags for current recording
  const getRecordingTags = (): Tag[] => {
    if (!recording.tagIds || !userTags.length) return [];
    return userTags.filter(tag => recording.tagIds?.includes(tag.id));
  };

  const handleDelete = async () => {
    try {
      let response;
      if (recording.transcription_id) {
        response = await deleteTranscription(recording.transcription_id);
      } else {
        response = await deleteRecording(recording.id);
      }
      
      showNotificationFromApiResponse(response);
      
      if (response.status === 'success') {
        removeRecording(recording.id);
      }
    } catch (error) {
      console.error('Error deleting recording:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to delete recording',
        color: 'red'
      });
    }
  };

  const handleStartTranscription = async () => {
    try {
      const response = await startTranscription(recording.id);
      showNotificationFromApiResponse(response);
      
      if (response.status === 'success') {
        // Fetch updated recording data
        const updatedRecording = await fetchRecording(recording.id);
        setRecording(updatedRecording);
        setTranscriptionStatus((updatedRecording.transcription_status as 'not_started' | 'in_progress' | 'completed' | 'failed') || 'not_started');
        
        // Update parent component
        dispatchRecordingUpdate(updatedRecording);
      }
    } catch (error) {
      console.error('Error starting transcription:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to start transcription',
        color: 'red'
      });
    }
  };

  const handleOpenAIWorkspace = () => {
    openAIWorkspace(recording.id);
  };

  const handleTagToggle = async (tagId: string) => {
    const currentTagIds = recording.tagIds || [];
    const isTagSelected = currentTagIds.includes(tagId);
    
    // Optimistic update
    let newTagIds: string[];
    if (isTagSelected) {
      newTagIds = currentTagIds.filter(id => id !== tagId);
    } else {
      newTagIds = [...currentTagIds, tagId];
    }
    
    const updatedRecording = { ...recording, tagIds: newTagIds };
    setRecording(updatedRecording);
    dispatchRecordingUpdate(updatedRecording);
    
    try {
      const response = isTagSelected 
        ? await removeTagFromRecording(recording.id, tagId)
        : await addTagToRecording(recording.id, tagId);
      
      if (response.status === 'error') {
        // Revert optimistic update on error
        setRecording(recording);
        dispatchRecordingUpdate(recording);
        showNotificationFromApiResponse(response);
      }
    } catch (error) {
      // Revert optimistic update on error
      setRecording(recording);
      dispatchRecordingUpdate(recording);
      console.error('Error toggling tag:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to update tag',
        color: 'red'
      });
    }
  };

  const isTagSelected = (tagId: string) => {
    return recording.tagIds?.includes(tagId) || false;
  };

  // Update local state when props change
  useEffect(() => {
    setRecording(initialRecording);
    setTranscriptionStatus((initialRecording.transcription_status as 'not_started' | 'in_progress' | 'completed' | 'failed') || 'not_started');
  }, [initialRecording]);


  // Periodic check for transcription status if in progress
  useEffect(() => {
    let intervalId: number;
    if (transcriptionStatus === 'in_progress') {
      intervalId = window.setInterval(() => {
        checkTranscriptionStatus(recording.id).then((response) => {
          if (response.status !== 'in_progress') {
            clearInterval(intervalId);
            setTranscriptionStatus(response.status as 'not_started' | 'in_progress' | 'completed' | 'failed');
            
            // If transcription is complete, fetch the updated recording
            if (response.status === 'completed') {
              fetchRecording(recording.id)
                .then(updatedRecording => {
                  setRecording(updatedRecording);
                  dispatchRecordingUpdate(updatedRecording);
                  
                  notifications.show({
                    title: 'Transcription Complete',
                    message: 'Your recording has been successfully transcribed',
                    color: 'green'
                  });
                })
                .catch(error => {
                  console.error('Failed to fetch updated recording:', error);
                });
            }
          }
        });
      }, 15000); // Check every 15 seconds
    }
    return () => clearInterval(intervalId);
  }, [recording.id, transcriptionStatus]);

  const statusColor = getStatusColor(transcriptionStatus);
  const statusText = getStatusText(transcriptionStatus);

  return (
    <Card
      shadow="sm"
      padding="lg"
      radius="md"
      withBorder
      className="glass-card"
      style={{
        cursor: 'pointer',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <Stack gap="md">
        {/* Header */}
        <Group justify="space-between" align="flex-start">
          <Stack gap={4} style={{ flex: 1 }}>
            <Text fw={600} size="md" lineClamp={2}>
              {recording.title || recording.original_filename}
            </Text>
            {recording.description && (
              <Text size="sm" c="dimmed" lineClamp={2}>
                {recording.description}
              </Text>
            )}
            <Text size="sm" c="dimmed">
              Duration: {formatDuration(recording.duration || 0)}
            </Text>
            {recording.recorded_timestamp && (
              <Text size="xs" c="dimmed">
                Recorded: {new Date(recording.recorded_timestamp).toLocaleDateString()}
              </Text>
            )}
          </Stack>
          
          <Menu shadow="md" width={180}>
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray">
                <LuEllipsis size={16} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<LuEye size={14} />}
                disabled={transcriptionStatus !== 'completed'}
              >
                View Transcription
              </Menu.Item>
              <Menu.Item leftSection={<LuDownload size={14} />}>
                Download
              </Menu.Item>
              
              <Menu.Item
                leftSection={<LuTag size={14} />}
                rightSection="►"
              >
                <Menu trigger="hover" position="right-start" offset={2}>
                  <Menu.Target>
                    <Text>Manage Tags</Text>
                  </Menu.Target>
                  <Menu.Dropdown>
                    {userTags.length === 0 ? (
                      <Menu.Item disabled>
                        <Text size="sm" c="dimmed">No tags available</Text>
                      </Menu.Item>
                    ) : (
                      userTags.map(tag => (
                        <Menu.Item
                          key={tag.id}
                          leftSection={
                            isTagSelected(tag.id) ? (
                              <LuCheck size={14} style={{ color: tag.color }} />
                            ) : (
                              <div style={{ width: 14, height: 14 }} />
                            )
                          }
                          onClick={() => handleTagToggle(tag.id)}
                        >
                          <Group gap="xs">
                            <div
                              style={{
                                width: 12,
                                height: 12,
                                borderRadius: '50%',
                                backgroundColor: tag.color,
                              }}
                            />
                            <Text size="sm">{tag.name}</Text>
                          </Group>
                        </Menu.Item>
                      ))
                    )}
                  </Menu.Dropdown>
                </Menu>
              </Menu.Item>
              
              <Menu.Divider />
              <Menu.Item 
                leftSection={<LuTrash2 size={14} />}
                color="red"
                onClick={handleDelete}
              >
                Delete
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>

        {/* Status Badge */}
        <Badge
          color={statusColor}
          variant="light"
          size="sm"
          radius="sm"
        >
          {statusText}
        </Badge>

        {/* Tags */}
        {getRecordingTags().length > 0 && (
          <Group gap="xs">
            {getRecordingTags().map(tag => (
              <TagBadge 
                key={tag.id} 
                tag={tag} 
                size="xs"
              />
            ))}
          </Group>
        )}

        {/* Participants */}
        <ParticipantBadge participants={recording.participants || []} size="xs" />

        {/* Action Buttons */}
        <Group gap="xs" mt="auto">
          {transcriptionStatus !== 'completed' && (
            <Button
              size="sm"
              variant="light"
              leftSection={transcriptionStatus === 'in_progress' ? <LuRefreshCw size={16} /> : <LuPlay size={16} />}
              onClick={handleStartTranscription}
              disabled={transcriptionStatus === 'in_progress'}
              fullWidth
            >
              {transcriptionStatus === 'in_progress' ? 'Transcribing...' : 'Start Transcription'}
            </Button>
          )}
          
          {transcriptionStatus === 'completed' && (
            <Button
              size="sm"
              variant="filled"
              color="violet"
              onClick={handleOpenAIWorkspace}
              fullWidth
            >
              <Group gap="xs">
                <LuList size={16} />
                <span>Open Recording Workspace</span>
              </Group>
            </Button>
          )}
        </Group>
      </Stack>
    </Card>
  );
}