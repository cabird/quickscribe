import { Modal, Stack, Text, TextInput, Button, Group, Loader, Alert } from '@mantine/core';
import { LuUsers } from 'react-icons/lu';
import { useState, useEffect } from 'react';
import { updateSpeakers, getSpeakerSummaries } from '../../api/recordings';
import { showNotificationFromApiResponse } from '../../utils';
import type { Recording, Transcription } from '../../types';

interface EditSpeakersModalProps {
  opened: boolean;
  onClose: () => void;
  recording: Recording;
  transcription: Transcription;
  onSpeakersUpdated?: (recording: Recording, transcription: Transcription) => void;
}

interface SpeakerData {
  label: string;
  currentName: string;
  summary: string;
  newName: string;
}

export function EditSpeakersModal({
  opened,
  onClose,
  recording,
  transcription,
  onSpeakersUpdated
}: EditSpeakersModalProps) {
  const [speakers, setSpeakers] = useState<SpeakerData[]>([]);
  const [summariesLoading, setSummariesLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Initialize speakers from transcription speaker_mapping
  useEffect(() => {
    if (opened && transcription?.speaker_mapping) {
      const speakerData: SpeakerData[] = Object.entries(transcription.speaker_mapping).map(
        ([label, mapping]) => ({
          label,
          currentName: mapping.name,
          summary: '',
          newName: mapping.name // Initialize with current name
        })
      );
      setSpeakers(speakerData);
      
      // Fetch speaker summaries
      fetchSpeakerSummaries();
    }
  }, [opened, transcription]);

  const fetchSpeakerSummaries = async () => {
    if (!transcription?.id) return;
    
    setSummariesLoading(true);
    try {
      const summaries = await getSpeakerSummaries(transcription.id);
      console.log('DEBUG: Received speaker summaries:', summaries);
      console.log('DEBUG: Current speakers state:', speakers);
      
      if (summaries) {
        setSpeakers(prev => prev.map(speaker => {
          const summary = summaries[speaker.label] || 'No summary available';
          console.log(`DEBUG: Mapping ${speaker.label} -> ${summary}`);
          return {
            ...speaker,
            summary
          };
        }));
      }
    } catch (error) {
      console.error('Failed to fetch speaker summaries:', error);
      // Set fallback summaries
      setSpeakers(prev => prev.map(speaker => ({
        ...speaker,
        summary: 'Summary unavailable'
      })));
    } finally {
      setSummariesLoading(false);
    }
  };

  const validateSpeakers = (): string[] => {
    const errors: string[] = [];
    const names = new Set<string>();

    for (const speaker of speakers) {
      const trimmedName = speaker.newName.trim();
      
      if (!trimmedName) {
        errors.push(`${speaker.label}: Name cannot be empty`);
      } else if (trimmedName.length > 50) {
        errors.push(`${speaker.label}: Name too long (max 50 characters)`);
      } else if (names.has(trimmedName.toLowerCase())) {
        errors.push(`Duplicate name: "${trimmedName}"`);
      } else {
        names.add(trimmedName.toLowerCase());
      }
    }

    return errors;
  };

  const handleSpeakerNameChange = (index: number, newName: string) => {
    setSpeakers(prev => prev.map((speaker, i) => 
      i === index ? { ...speaker, newName } : speaker
    ));
    
    // Clear validation errors when user starts typing
    if (validationErrors.length > 0) {
      setValidationErrors([]);
    }
  };

  const handleSave = async () => {
    // Validate
    const errors = validateSpeakers();
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }

    setSaving(true);
    try {
      // Create speaker mapping object
      const speakerMapping: Record<string, string> = {};
      speakers.forEach(speaker => {
        speakerMapping[speaker.label] = speaker.newName.trim();
      });

      const response = await updateSpeakers(recording.id, speakerMapping);
      showNotificationFromApiResponse(response);

      if (response.status === 'success' && response.data) {
        const { updated_recording, updated_transcription } = response.data;
        
        if (updated_recording && updated_transcription && onSpeakersUpdated) {
          onSpeakersUpdated(updated_recording, updated_transcription);
        }
        
        // Also dispatch the recording update event for global state
        if (updated_recording) {
          window.dispatchEvent(new CustomEvent('recordingUpdated', { 
            detail: { recording: updated_recording } 
          }));
        }
        
        onClose();
      }
    } catch (error) {
      console.error('Error updating speakers:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    // Reset to original names
    setSpeakers(prev => prev.map(speaker => ({
      ...speaker,
      newName: speaker.currentName
    })));
    setValidationErrors([]);
    onClose();
  };

  return (
    <Modal
      opened={opened}
      onClose={handleCancel}
      title={
        <Group gap="xs">
          <LuUsers size={20} />
          <Text fw={600}>Edit Speakers</Text>
        </Group>
      }
      size="lg"
      centered
    >
      <Stack gap="lg">
        {validationErrors.length > 0 && (
          <Alert color="red" variant="light">
            <Stack gap="xs">
              {validationErrors.map((error, index) => (
                <Text key={index} size="sm">{error}</Text>
              ))}
            </Stack>
          </Alert>
        )}

        {speakers.map((speaker, index) => (
          <Stack key={speaker.label} gap="xs">
            <Text fw={500} size="sm" c="dimmed">
              {speaker.label}
            </Text>
            
            {summariesLoading ? (
              <Group gap="xs" align="center">
                <Loader size="xs" />
                <Text size="sm" c="dimmed">Loading speaker summary...</Text>
              </Group>
            ) : (
              <Text size="sm" c="dimmed" style={{ 
                fontStyle: 'italic',
                padding: '8px 12px',
                backgroundColor: 'var(--mantine-color-gray-0)',
                borderRadius: '6px',
                border: '1px solid var(--mantine-color-gray-3)'
              }}>
                {speaker.summary}
              </Text>
            )}
            
            <TextInput
              placeholder="Enter speaker name"
              value={speaker.newName}
              onChange={(e) => handleSpeakerNameChange(index, e.target.value)}
              disabled={saving}
              maxLength={50}
            />
          </Stack>
        ))}

        <Group justify="flex-end" mt="md">
          <Button
            variant="subtle"
            onClick={handleCancel}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            loading={saving}
            disabled={summariesLoading}
            color="blue"
          >
            Save Changes
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}