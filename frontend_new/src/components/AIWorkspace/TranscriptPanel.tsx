import { Card, Stack, Group, Text, Button, Center, Loader, Badge } from '@mantine/core';
import { LuFileText, LuCopy, LuEye, LuBot, LuUsers } from 'react-icons/lu';
import { notifications } from '@mantine/notifications';
import { formatDuration, getStatusText, showNotificationFromApiResponse } from '../../utils';
import { TagBadge } from '../Tags/TagBadge';
import { ParticipantBadge } from '../ParticipantBadge';
import { triggerPostProcessing, fetchRecording } from '../../api/recordings';
import { useState } from 'react';
import type { Recording, Transcription, Tag } from '../../types';

interface TranscriptPanelProps {
  recording: Recording;
  recordingTags: Tag[];
  transcription: Transcription | null;
  transcriptionLoading: boolean;
  onViewFullTranscript?: () => void;
  onRecordingUpdate?: (recording: Recording) => void;
  onTranscriptReload?: () => void;
  onPostProcessingUpdate?: (recording: Recording, transcription: Transcription) => void;
  onEditSpeakers?: () => void;
}

export function TranscriptPanel({ 
  recording, 
  recordingTags, 
  transcription, 
  transcriptionLoading,
  onViewFullTranscript,
  onRecordingUpdate,
  onTranscriptReload,
  onPostProcessingUpdate,
  onEditSpeakers
}: TranscriptPanelProps) {
  const [postProcessingLoading, setPostProcessingLoading] = useState(false);
  
  const handleCopyTranscript = async () => {
    if (!transcription) return;
    
    try {
      let textToCopy = '';
      
      if (transcription.diarized_transcript) {
        textToCopy = transcription.diarized_transcript
          .split('\n')
          .map(line => {
            const speakerMatch = line.match(/^([^:]+):\s*(.*)$/);
            if (speakerMatch) {
              const speakerLabel = speakerMatch[1];
              const content = speakerMatch[2];
              // Use speaker mapping with new participant format
              const speakerData = transcription.speaker_mapping?.[speakerLabel];
              const displayName = speakerData?.displayName || speakerData?.name || speakerLabel;
              return `${displayName}: ${content}`;
            }
            return line;
          })
          .filter(line => line.trim())
          .join('\n');
      } else if (transcription.text) {
        textToCopy = transcription.text;
      }
      
      await navigator.clipboard.writeText(textToCopy);
      notifications.show({
        title: 'Copied!',
        message: 'Transcript copied to clipboard',
        color: 'green',
        autoClose: 3000,
      });
    } catch (error) {
      console.error('Failed to copy transcript:', error);
      notifications.show({
        title: 'Copy failed',
        message: 'Unable to copy transcript to clipboard',
        color: 'red',
        autoClose: 3000,
      });
    }
  };

  const handlePostProcessing = async () => {
    setPostProcessingLoading(true);
    
    try {
      const response = await triggerPostProcessing(recording.id);
      showNotificationFromApiResponse(response);
      
      if (response.status === 'success' && response.data) {
        // Check if speaker inference was skipped due to manual verification
        if (response.data.speaker_update?.skipped === 'manually_verified') {
          notifications.show({
            title: 'AI Enhancement Completed',
            message: 'Title and description updated. Speaker assignments preserved (manually verified).',
            color: 'blue',
            autoClose: 5000,
          });
        }
        
        // Use the updated data directly from the response instead of making additional API calls
        const { updated_recording, updated_transcription } = response.data;
        
        if (updated_recording) {
          // Update the recording data
          if (onRecordingUpdate) {
            onRecordingUpdate(updated_recording);
          }
          
          // Also dispatch a custom event to update the recording in the store
          window.dispatchEvent(new CustomEvent('recordingUpdated', { 
            detail: { recording: updated_recording } 
          }));
        }
        
        // If both recording and transcription were updated, use the combined callback
        if (updated_recording && updated_transcription && onPostProcessingUpdate) {
          console.log('Post-processing completed, updating recording and transcription...');
          onPostProcessingUpdate(updated_recording, updated_transcription);
        } else if (response.data?.results?.speakers_updated && onTranscriptReload) {
          // Fallback to the old method if needed
          console.log('Speaker names were updated, reloading transcript...');
          onTranscriptReload();
        }
      }
    } catch (error) {
      console.error('Error during post-processing:', error);
      notifications.show({
        title: 'Error',
        message: 'Failed to trigger AI post-processing',
        color: 'red'
      });
    } finally {
      setPostProcessingLoading(false);
    }
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Stack gap="xs" style={{ padding: '1rem', paddingBottom: '0.5rem', flexShrink: 0 }}>
        <Group justify="space-between" align="center">
          <Text fw={600} size="lg">Recording Workspace</Text>
          <Badge color="green" variant="light" size="sm">
            {getStatusText(recording.transcription_status)}
          </Badge>
        </Group>
        <div>
          <Group justify="space-between" align="flex-start">
            <div style={{ flex: 1 }}>
              <Text fw={500} size="md">
                {recording.title || recording.original_filename}
              </Text>
              {recording.description && (
                <Text size="sm" c="dimmed" mt={2}>
                  {recording.description}
                </Text>
              )}
            </div>
            <Text size="sm" c="dimmed">
              {formatDuration(recording.duration || 0)} • {recording.recorded_timestamp ? new Date(recording.recorded_timestamp).toLocaleDateString() : 'Unknown'}
            </Text>
          </Group>
        </div>
        {recordingTags.length > 0 && (
          <Group gap="xs">
            {recordingTags.map(tag => (
              <TagBadge key={tag.id} tag={tag} size="xs" />
            ))}
          </Group>
        )}
        
        {/* Participants */}
        <ParticipantBadge participants={recording.participants || []} size="xs" />
      </Stack>

      {/* Transcript Card */}
      <div style={{ flex: 1, padding: '0 1rem 1rem 1rem', minHeight: 0 }}>
        <Card withBorder radius="md" h="100%">
          <Stack gap="sm" h="100%">
            <Group justify="space-between" style={{ flexShrink: 0 }}>
              <Group gap="xs">
                <LuFileText size={20} />
                <Text fw={600} size="md">Transcript Preview</Text>
              </Group>
              <Group gap="xs">
                <Button 
                  size="xs" 
                  variant="light" 
                  leftSection={<LuCopy size={14} />}
                  onClick={handleCopyTranscript}
                  disabled={!transcription || transcriptionLoading}
                >
                  Copy
                </Button>
                <Button 
                  size="xs" 
                  variant="light" 
                  leftSection={<LuEye size={14} />}
                  onClick={onViewFullTranscript}
                  disabled={!transcription || transcriptionLoading}
                >
                  View Full
                </Button>
                <Button 
                  size="xs" 
                  variant="filled" 
                  color="blue"
                  leftSection={<LuBot size={14} />}
                  onClick={handlePostProcessing}
                  loading={postProcessingLoading}
                  disabled={!transcription || transcriptionLoading || recording.transcription_status !== 'completed'}
                >
                  AI Enhance
                </Button>
                <Button 
                  size="xs" 
                  variant="outline" 
                  color="blue"
                  leftSection={<LuUsers size={14} />}
                  onClick={onEditSpeakers}
                  disabled={!transcription || transcriptionLoading || recording.transcription_status !== 'completed' || !transcription?.diarized_transcript}
                >
                  Edit Speakers
                </Button>
              </Group>
            </Group>
            
            {/* Scrollable Transcript Content */}
            <div style={{ 
              flex: 1,
              overflow: 'auto',
              padding: '0.75rem',
              backgroundColor: 'var(--mantine-color-gray-0)',
              borderRadius: '6px',
              fontSize: '0.875rem',
              lineHeight: 1.6,
              border: '1px solid var(--mantine-color-gray-3)',
              minHeight: 0,
            }}>
              {transcriptionLoading ? (
                <Center p="md">
                  <Loader size="sm" />
                </Center>
              ) : transcription?.diarized_transcript ? (
                <div
                  dangerouslySetInnerHTML={{
                    __html: transcription.diarized_transcript
                      .split('\n')
                      .map(line => {
                        const speakerMatch = line.match(/^([^:]+):\s*(.*)$/);
                        if (speakerMatch) {
                          const speakerLabel = speakerMatch[1];
                          const content = speakerMatch[2];
                          // Use speaker mapping with new participant format
                          const speakerData = transcription.speaker_mapping?.[speakerLabel];
                          const displayName = speakerData?.displayName || speakerData?.name || speakerLabel;
                          const isVerified = speakerData?.manuallyVerified;
                          const participantId = speakerData?.participantId;
                          
                          // Add visual indicators for participant status
                          const nameStyle = participantId 
                            ? `color: var(--mantine-color-blue-6); ${isVerified ? 'font-weight: 600;' : ''}`
                            : 'color: var(--mantine-color-gray-6);';
                          
                          return `<div style="margin-bottom: 1rem;"><strong style="${nameStyle}">${displayName}:</strong><br/>${content}</div>`;
                        }
                        return `<div style="margin-bottom: 0.5rem;">${line}</div>`;
                      })
                      .join('')
                  }}
                />
              ) : transcription?.text ? (
                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                  {transcription.text}
                </Text>
              ) : (
                <Text size="sm" c="dimmed" ta="center">
                  No transcript available for this recording
                </Text>
              )}
            </div>
          </Stack>
        </Card>
      </div>
    </div>
  );
}