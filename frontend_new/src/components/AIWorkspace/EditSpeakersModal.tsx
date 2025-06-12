import { Modal, Stack, Text, TextInput, Button, Group, Loader, Alert, Select, Paper, Divider } from '@mantine/core';
import { LuUsers, LuUser } from 'react-icons/lu';
import { useState, useEffect, useCallback } from 'react';
import { updateSpeakers, getSpeakerSummaries } from '../../api/recordings';
import { getParticipants, createParticipant } from '../../api/participants';
import { showNotificationFromApiResponse } from '../../utils';
import type { Recording, Transcription, Participant, CreateParticipantRequest } from '../../types';

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
  selectedParticipantId: string | null;
  showCreateForm: boolean;
  newParticipantData: CreateParticipantRequest;
}

export function EditSpeakersModal({
  opened,
  onClose,
  recording,
  transcription,
  onSpeakersUpdated
}: EditSpeakersModalProps) {
  const [speakers, setSpeakers] = useState<SpeakerData[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [summariesLoading, setSummariesLoading] = useState(false);
  const [participantsLoading, setParticipantsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const loadParticipants = async () => {
    setParticipantsLoading(true);
    try {
      const allParticipants = await getParticipants();
      setParticipants(allParticipants);
    } catch (error) {
      console.error('Failed to load participants:', error);
      setParticipants([]);
    } finally {
      setParticipantsLoading(false);
    }
  };

  const fetchSpeakerSummaries = useCallback(async () => {
    if (!transcription?.id) return;
    
    setSummariesLoading(true);
    try {
      const summaries = await getSpeakerSummaries(transcription.id);
      console.log('DEBUG: Received speaker summaries:', summaries);
      
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
  }, [transcription?.id]);

  const extractSpeakersFromDiarizedTranscript = useCallback((diarizedTranscript: string): string[] => {
    const speakerLabels = new Set<string>();
    const lines = diarizedTranscript.split('\n');
    
    for (const line of lines) {
      const speakerMatch = line.match(/^([^:]+):\s*(.*)$/);
      if (speakerMatch) {
        const speakerLabel = speakerMatch[1].trim();
        if (speakerLabel) {
          speakerLabels.add(speakerLabel);
        }
      }
    }
    
    return Array.from(speakerLabels).sort();
  }, []);

  const initializeSpeakers = useCallback(() => {
    let speakerData: SpeakerData[] = [];
    
    if (transcription?.speaker_mapping) {
      // Use existing speaker mapping if available (AI enhanced)
      speakerData = Object.entries(transcription.speaker_mapping).map(
        ([label, mapping]) => ({
          label,
          currentName: mapping.displayName || mapping.name,
          summary: '',
          selectedParticipantId: mapping.participantId || null,
          showCreateForm: false,
          newParticipantData: {
            displayName: mapping.displayName || mapping.name
          }
        })
      );
    } else if (transcription?.diarized_transcript) {
      // Extract speakers from raw diarized transcript
      const speakerLabels = extractSpeakersFromDiarizedTranscript(transcription.diarized_transcript);
      speakerData = speakerLabels.map(label => ({
        label,
        currentName: label, // Use the raw speaker label as default name
        summary: '',
        selectedParticipantId: null,
        showCreateForm: false,
        newParticipantData: {
          displayName: label
        }
      }));
    }
    
    setSpeakers(speakerData);
    
    // Fetch speaker summaries if we have speakers
    if (speakerData.length > 0) {
      fetchSpeakerSummaries();
    }
  }, [transcription?.speaker_mapping, transcription?.diarized_transcript, extractSpeakersFromDiarizedTranscript, fetchSpeakerSummaries]);

  // Load participants and initialize speakers
  useEffect(() => {
    if (opened) {
      loadParticipants();
      initializeSpeakers();
    }
  }, [opened, transcription, initializeSpeakers]);

  const validateSpeakers = (): string[] => {
    const errors: string[] = [];

    for (const speaker of speakers) {
      if (!speaker.selectedParticipantId && !speaker.showCreateForm) {
        errors.push(`${speaker.label}: Please select a participant or create a new one`);
      } else if (speaker.showCreateForm && !speaker.newParticipantData.displayName.trim()) {
        errors.push(`${speaker.label}: Participant name cannot be empty`);
      }
    }

    return errors;
  };

  const handleParticipantSelect = (index: number, participantId: string | null) => {
    setSpeakers(prev => prev.map((speaker, i) => 
      i === index ? { 
        ...speaker, 
        selectedParticipantId: participantId,
        showCreateForm: participantId === 'create-new'
      } : speaker
    ));
    
    if (validationErrors.length > 0) {
      setValidationErrors([]);
    }
  };

  const handleNewParticipantDataChange = (index: number, field: keyof CreateParticipantRequest, value: string) => {
    setSpeakers(prev => prev.map((speaker, i) => 
      i === index ? {
        ...speaker,
        newParticipantData: {
          ...speaker.newParticipantData,
          [field]: value
        }
      } : speaker
    ));
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
      // Process speakers: create new participants if needed, then build mapping
      const speakerMapping: Record<string, { participantId: string; displayName: string }> = {};

      for (const speaker of speakers) {
        if (speaker.showCreateForm) {
          // Create new participant
          try {
            const newParticipant = await createParticipant(speaker.newParticipantData);
            speakerMapping[speaker.label] = {
              participantId: newParticipant.id,
              displayName: newParticipant.displayName
            };
          } catch (error) {
            throw new Error(`Failed to create participant for ${speaker.label}: ${error}`);
          }
        } else if (speaker.selectedParticipantId) {
          // Use existing participant
          const participant = participants.find(p => p.id === speaker.selectedParticipantId);
          speakerMapping[speaker.label] = {
            participantId: speaker.selectedParticipantId,
            displayName: participant?.displayName || speaker.currentName
          };
        }
      }

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
      setValidationErrors([error instanceof Error ? error.message : 'Failed to update speakers']);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    // Reset to original state
    initializeSpeakers();
    setValidationErrors([]);
    onClose();
  };

  // Helper function to find smart participant suggestions
  const findSuggestedParticipant = (speakerName: string): Participant | null => {
    if (!participants.length) return null;
    
    // Exact match first
    let match = participants.find(p => 
      p.displayName.toLowerCase() === speakerName.toLowerCase()
    );
    if (match) return match;
    
    // Alias match
    match = participants.find(p => 
      p.aliases.some(alias => alias.toLowerCase() === speakerName.toLowerCase())
    );
    if (match) return match;
    
    // Fuzzy match (starts with)
    match = participants.find(p => 
      p.displayName.toLowerCase().startsWith(speakerName.toLowerCase()) ||
      p.firstName?.toLowerCase().startsWith(speakerName.toLowerCase()) ||
      p.lastName?.toLowerCase().startsWith(speakerName.toLowerCase())
    );
    
    return match;
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

        {!transcription?.speaker_mapping && transcription?.diarized_transcript && (
          <Alert color="blue" variant="light">
            <Text size="sm">
              <strong>Speaker labels detected from transcript</strong><br />
              These are the raw speaker labels from the transcription service. For better speaker identification and names, consider running "AI Enhance" first.
            </Text>
          </Alert>
        )}

        {speakers.length === 0 ? (
          <Alert color="yellow" variant="light">
            <Text size="sm">
              <strong>No speakers detected</strong><br />
              This recording doesn't appear to have speaker separation (diarization). This usually means it's either a single speaker recording or the transcription service didn't detect multiple speakers.
            </Text>
          </Alert>
        ) : (
          speakers.map((speaker, index) => {
          const suggestedParticipant = findSuggestedParticipant(speaker.currentName);
          const selectData = [
            ...participants.map(p => ({
              value: p.id,
              label: `${p.displayName}${p.email ? ` (${p.email})` : ''}${p.isUser ? ' [You]' : ''}`
            })),
            { value: 'create-new', label: '+ Create New Participant' }
          ];

          return (
            <Stack key={speaker.label} gap="md">
              <Paper p="md" withBorder>
                <Stack gap="sm">
                  <Group justify="space-between">
                    <Text fw={500} size="sm" c="dimmed">
                      {speaker.label}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Currently: {speaker.currentName}
                    </Text>
                  </Group>
                  
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

                  <Select
                    label="Assign to Participant"
                    placeholder={participantsLoading ? "Loading participants..." : "Select a participant"}
                    data={selectData}
                    value={speaker.selectedParticipantId}
                    onChange={(value) => handleParticipantSelect(index, value)}
                    disabled={saving || participantsLoading}
                    searchable
                    leftSection={<LuUser size={16} />}
                    comboboxProps={{ withinPortal: true }}
                  />

                  {suggestedParticipant && !speaker.selectedParticipantId && (
                    <Alert color="blue" variant="light" p="xs">
                      <Text size="sm">
                        💡 Suggestion: <strong>{suggestedParticipant.displayName}</strong>
                        {suggestedParticipant.email && ` (${suggestedParticipant.email})`}
                      </Text>
                    </Alert>
                  )}

                  {speaker.showCreateForm && (
                    <Stack gap="xs" mt="sm">
                      <Divider label="Create New Participant" />
                      <TextInput
                        label="Display Name"
                        placeholder="Enter participant name"
                        value={speaker.newParticipantData.displayName}
                        onChange={(e) => handleNewParticipantDataChange(index, 'displayName', e.target.value)}
                        disabled={saving}
                        required
                      />
                      <Group grow>
                        <TextInput
                          label="First Name"
                          placeholder="First name (optional)"
                          value={speaker.newParticipantData.firstName || ''}
                          onChange={(e) => handleNewParticipantDataChange(index, 'firstName', e.target.value)}
                          disabled={saving}
                        />
                        <TextInput
                          label="Last Name"
                          placeholder="Last name (optional)"
                          value={speaker.newParticipantData.lastName || ''}
                          onChange={(e) => handleNewParticipantDataChange(index, 'lastName', e.target.value)}
                          disabled={saving}
                        />
                      </Group>
                    </Stack>
                  )}
                </Stack>
              </Paper>
            </Stack>
          );
        })
        )}

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