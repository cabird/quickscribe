import { Card, Stack, Group, Text, Button, Center, Loader, Badge } from '@mantine/core';
import { LuFileText, LuCopy, LuEye } from 'react-icons/lu';
import { notifications } from '@mantine/notifications';
import { formatDuration, getStatusText } from '../../utils';
import { TagBadge } from '../Tags/TagBadge';
import type { Recording, Transcription, Tag } from '../../types';

interface TranscriptPanelProps {
  recording: Recording;
  recordingTags: Tag[];
  transcription: Transcription | null;
  transcriptionLoading: boolean;
  onViewFullTranscript?: () => void;
}

export function TranscriptPanel({ 
  recording, 
  recordingTags, 
  transcription, 
  transcriptionLoading,
  onViewFullTranscript 
}: TranscriptPanelProps) {
  
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
              return `${speakerMatch[1]}: ${speakerMatch[2]}`;
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
        <Group justify="space-between" align="center">
          <Text fw={500} size="md" style={{ flex: 1 }}>
            {recording.title || recording.original_filename}
          </Text>
          <Text size="sm" c="dimmed">
            {formatDuration(recording.duration || 0)} • {recording.recorded_timestamp ? new Date(recording.recorded_timestamp).toLocaleDateString() : 'Unknown'}
          </Text>
        </Group>
        {recordingTags.length > 0 && (
          <Group gap="xs">
            {recordingTags.map(tag => (
              <TagBadge key={tag.id} tag={tag} size="xs" />
            ))}
          </Group>
        )}
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
                          return `<div style="margin-bottom: 1rem;"><strong style="color: var(--mantine-color-blue-6);">${speakerMatch[1]}:</strong><br/>${speakerMatch[2]}</div>`;
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