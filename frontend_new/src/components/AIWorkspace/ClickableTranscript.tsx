import { Text, Group, ActionIcon, Box, Tooltip } from '@mantine/core';
import { LuVolume2, LuPencil } from 'react-icons/lu';
import { useMemo, useRef, useEffect, useState, useCallback } from 'react';
import { InlineParticipantPicker } from './InlineParticipantPicker';
import { AddParticipantModal } from './AddParticipantModal';
import axios from 'axios';
import { notifications } from '@mantine/notifications';

interface TranscriptPhrase {
  speaker: number;
  text: string;
  offsetMilliseconds: number;
  durationMilliseconds: number;
  confidence: number;
}

interface ClickableTranscriptProps {
  transcription: {
    id: string;
    transcript_json?: string;
    diarized_transcript?: string;
    text?: string;
    speaker_mapping?: {
      [key: string]: {
        name?: string;
        displayName?: string;
        reasoning: string;
        participantId?: string;
        confidence?: number;
        manuallyVerified?: boolean;
      };
    };
  };
  onPhraseClick?: (offsetMs: number) => void;
  currentAudioTime?: number;
  showAudioButton?: boolean;
  onParticipantPickerStateChange?: (isOpen: boolean) => void;
}

export function ClickableTranscript({ 
  transcription, 
  onPhraseClick, 
  currentAudioTime = 0,
  showAudioButton = false,
  onParticipantPickerStateChange 
}: ClickableTranscriptProps) {
  const phraseRefs = useRef<{ [key: string]: HTMLElement | null }>({});
  const lastScrolledPhraseRef = useRef<number>(-1);
  const [hoveredSpeaker, setHoveredSpeaker] = useState<string | null>(null);
  const [editingSpeaker, setEditingSpeaker] = useState<string | null>(null);
  const [addParticipantModalOpen, setAddParticipantModalOpen] = useState(false);
  const [pendingSpeakerForNewParticipant, setPendingSpeakerForNewParticipant] = useState<string | null>(null);
  const speakerRefs = useRef<{ [key: string]: HTMLElement | null }>({});
  // Parse the transcript JSON to get phrases with timestamps
  const phrases = useMemo(() => {
    if (!transcription.transcript_json) {
      return null;
    }
    
    try {
      const data = JSON.parse(transcription.transcript_json);
      
      if (!data.recognizedPhrases) {
        return null;
      }
      
      return data.recognizedPhrases.map((phrase: any) => ({
        speaker: phrase.speaker,
        text: phrase.nBest?.[0]?.display || phrase.nBest?.[0]?.maskedITN || '',
        offsetMilliseconds: phrase.offsetMilliseconds || 0,
        durationMilliseconds: phrase.durationMilliseconds || 0,
        confidence: phrase.nBest?.[0]?.confidence || 0
      })) as TranscriptPhrase[];
    } catch (e) {
      console.error('Failed to parse transcript JSON:', e);
      return null;
    }
  }, [transcription.transcript_json]);

  // Group phrases by speaker for better display
  const groupedPhrases = useMemo(() => {
    if (!phrases) return [];
    
    const groups: Array<{
      speaker: string;
      phrases: TranscriptPhrase[];
      startTime: number;
    }> = [];
    
    let currentGroup: typeof groups[0] | null = null;
    
    phrases.forEach((phrase) => {
      const speakerLabel = `Speaker ${phrase.speaker}`;
      
      if (!currentGroup || currentGroup.speaker !== speakerLabel) {
        currentGroup = {
          speaker: speakerLabel,
          phrases: [phrase],
          startTime: phrase.offsetMilliseconds
        };
        groups.push(currentGroup);
      } else {
        currentGroup.phrases.push(phrase);
      }
    });
    return groups;
  }, [phrases]);

  const handlePhraseClick = (offsetMs: number) => {
    // Call the parent handler
    onPhraseClick?.(offsetMs);
    
    // Also try to use the global audio player if available
    if ((window as any).audioPlayerSeekTo) {
      (window as any).audioPlayerSeekTo(offsetMs);
    }
  };

  const getSpeakerDisplayName = (speakerLabel: string) => {
    const mapping = transcription.speaker_mapping?.[speakerLabel];
    return mapping?.displayName || mapping?.name || speakerLabel;
  };

  const isCurrentlyPlaying = (startMs: number, durationMs: number) => {
    const currentMs = currentAudioTime * 1000;
    return currentMs >= startMs && currentMs <= startMs + durationMs;
  };

  const handleParticipantSelect = useCallback(async (speakerLabel: string, participantId: string) => {
    setEditingSpeaker(null); // Close picker immediately for better UX
    
    if (participantId === 'new') {
      // Open modal to create new participant
      setPendingSpeakerForNewParticipant(speakerLabel);
      setAddParticipantModalOpen(true);
      return;
    }

    try {
      // Update the speaker mapping
      const response = await axios.post(`/api/transcription/${transcription.id}/speaker`, {
        speaker_label: speakerLabel,
        participant_id: participantId,
        manually_verified: true,
      });

      if (response.data.success) {
        notifications.show({
          message: 'Speaker assignment updated',
          color: 'green',
        });
        
        // Trigger a refresh of the transcription data
        // This would ideally be handled by a parent component or global state
        window.dispatchEvent(new CustomEvent('transcriptionUpdated', { 
          detail: { transcriptionId: transcription.id } 
        }));
      }
    } catch (error) {
      console.error('Failed to update speaker assignment:', error);
      notifications.show({
        message: 'Failed to update speaker assignment',
        color: 'red',
      });
    }
  }, [transcription.id]);

  const handleNewParticipantCreated = useCallback(async (participantId: string) => {
    if (pendingSpeakerForNewParticipant) {
      // Assign the new participant to the speaker
      await handleParticipantSelect(pendingSpeakerForNewParticipant, participantId);
      setPendingSpeakerForNewParticipant(null);
    }
  }, [pendingSpeakerForNewParticipant, handleParticipantSelect]);

  // Auto-scroll to the currently playing phrase
  useEffect(() => {
    if (!phrases || currentAudioTime === 0) return;

    const currentMs = currentAudioTime * 1000;
    
    // Find the currently playing phrase
    for (let i = 0; i < phrases.length; i++) {
      const phrase = phrases[i];
      if (currentMs >= phrase.offsetMilliseconds && 
          currentMs <= phrase.offsetMilliseconds + phrase.durationMilliseconds) {
        
        // Only scroll if we haven't already scrolled to this phrase
        if (lastScrolledPhraseRef.current !== i) {
          const key = `phrase-${i}`;
          const element = phraseRefs.current[key];
          
          if (element) {
            // Scroll the element into view with smooth scrolling
            element.scrollIntoView({
              behavior: 'smooth',
              block: 'center',
              inline: 'nearest'
            });
            lastScrolledPhraseRef.current = i;
          }
        }
        break;
      }
    }
  }, [currentAudioTime, phrases]);

  // Fallback to non-clickable display if we can't parse timestamps
  if (!phrases) {
    if (transcription.diarized_transcript) {
      return (
        <div>
          {transcription.diarized_transcript.split('\n').map((line, idx) => {
            const speakerMatch = line.match(/^([^:]+):\s*(.*)$/);
            if (speakerMatch) {
              const speakerLabel = speakerMatch[1];
              const content = speakerMatch[2];
              const displayName = getSpeakerDisplayName(speakerLabel);
              
              return (
                <div key={idx} style={{ marginBottom: '1rem' }}>
                  <Text fw={600} c="blue.6" size="sm">{displayName}:</Text>
                  <Text size="sm">{content}</Text>
                </div>
              );
            }
            return <Text key={idx} size="sm" style={{ marginBottom: '0.5rem' }}>{line}</Text>;
          })}
        </div>
      );
    } else if (transcription.text) {
      return <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{transcription.text}</Text>;
    }
    return <Text size="sm" c="dimmed" ta="center">No transcript available</Text>;
  }

  // Calculate a flat index for each phrase across all groups
  let phraseIndex = 0;

  return (
    <>
      <div>
        {groupedPhrases.map((group, groupIdx) => {
        const displayName = getSpeakerDisplayName(group.speaker);
        const speakerData = transcription.speaker_mapping?.[group.speaker];
        const isVerified = speakerData?.manuallyVerified;
        const hasParticipant = !!speakerData?.participantId;
        
        return (
          <div key={groupIdx} style={{ marginBottom: '1.5rem' }}>
            <Group gap="xs" mb="xs" wrap="nowrap">
              <Box
                ref={(el) => { speakerRefs.current[group.speaker] = el; }}
                onMouseEnter={() => setHoveredSpeaker(group.speaker)}
                onMouseLeave={() => setHoveredSpeaker(null)}
                style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}
              >
                <Text 
                  fw={600} 
                  c={hasParticipant ? 'blue.6' : 'gray.6'}
                  size="sm"
                  style={{ 
                    textDecoration: isVerified ? 'underline' : 'none',
                    fontStyle: hasParticipant ? 'normal' : 'italic'
                  }}
                >
                  {displayName}:
                </Text>
                <ActionIcon
                  size="xs"
                  variant="subtle"
                  onClick={(e) => {
                    e.stopPropagation();
                    // Store the click position for the dropdown
                    const rect = e.currentTarget.getBoundingClientRect();
                    (window as any).lastSpeakerEditClick = {
                      x: e.clientX,
                      y: e.clientY,
                      rect: { 
                        left: rect.left, 
                        top: rect.top, 
                        bottom: rect.bottom,
                        right: rect.right,
                        height: rect.height,
                        width: rect.width
                      }
                    };
                    setEditingSpeaker(group.speaker);
                    onParticipantPickerStateChange?.(true);
                  }}
                  style={{ 
                    marginLeft: 4,
                    opacity: hoveredSpeaker === group.speaker ? 1 : 0,
                    transition: 'opacity 0.15s ease-in-out',
                    cursor: 'pointer',
                    pointerEvents: hoveredSpeaker === group.speaker ? 'auto' : 'none'
                  }}
                  title="Edit speaker assignment"
                >
                  <LuPencil size={12} />
                </ActionIcon>
              </Box>
              {showAudioButton && (
                <Tooltip label="Click to play from this speaker's section">
                  <ActionIcon 
                    size="xs" 
                    variant="subtle"
                    onClick={() => handlePhraseClick(group.startTime)}
                    style={{ cursor: 'pointer' }}
                  >
                    <LuVolume2 size={14} />
                  </ActionIcon>
                </Tooltip>
              )}
            </Group>
            
            <div>
              {group.phrases.map((phrase, phraseIdx) => {
                const isPlaying = isCurrentlyPlaying(
                  phrase.offsetMilliseconds, 
                  phrase.durationMilliseconds
                );
                const currentPhraseIndex = phraseIndex++;
                const phraseKey = `phrase-${currentPhraseIndex}`;
                
                return (
                  <span 
                    key={phraseIdx}
                    ref={(el) => { phraseRefs.current[phraseKey] = el; }}
                    style={{
                      cursor: 'pointer',
                      backgroundColor: isPlaying ? 'var(--mantine-color-yellow-1)' : 'transparent',
                      padding: '2px 4px',
                      borderRadius: '3px',
                      transition: 'all 0.2s',
                      opacity: phrase.confidence < 0.5 ? 0.7 : 1,
                      display: 'inline-block'
                    }}
                    onClick={() => handlePhraseClick(phrase.offsetMilliseconds)}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'var(--mantine-color-blue-1)';
                      e.currentTarget.style.textDecoration = 'underline';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = isPlaying ? 'var(--mantine-color-yellow-1)' : 'transparent';
                      e.currentTarget.style.textDecoration = 'none';
                    }}
                    title={`Click to play (${Math.round(phrase.confidence * 100)}% confidence)`}
                  >
                    {phrase.text}{' '}
                  </span>
                );
              })}
            </div>
          </div>
        );
        })}
      </div>
      
      {/* Inline participant picker - rendered outside main content */}
      {editingSpeaker && (
        <InlineParticipantPicker
          isOpen={!!editingSpeaker}
          onClose={() => {
            setEditingSpeaker(null);
            onParticipantPickerStateChange?.(false);
          }}
          onSelect={(participantId) => {
            handleParticipantSelect(editingSpeaker, participantId);
            onParticipantPickerStateChange?.(false);
          }}
          anchorRef={{ current: speakerRefs.current[editingSpeaker] }}
          currentParticipantId={transcription.speaker_mapping?.[editingSpeaker]?.participantId}
        />
      )}
      
      {/* Add Participant Modal */}
      <AddParticipantModal
        opened={addParticipantModalOpen}
        onClose={() => {
          setAddParticipantModalOpen(false);
          setPendingSpeakerForNewParticipant(null);
        }}
        onParticipantCreated={handleNewParticipantCreated}
        initialName={pendingSpeakerForNewParticipant ? getSpeakerDisplayName(pendingSpeakerForNewParticipant) : ''}
      />
    </>
  );
}