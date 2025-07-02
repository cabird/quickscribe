import { Badge, Group } from '@mantine/core';
import { LuCircleHelp } from 'react-icons/lu';
import type { RecordingParticipant } from '../../types';

interface ParticipantBadgeProps {
  participants: string[] | RecordingParticipant[];
  size?: 'xs' | 'sm' | 'md' | 'lg';
}

export function ParticipantBadge({ participants, size = 'xs' }: ParticipantBadgeProps) {
  if (!participants || participants.length === 0) {
    return null;
  }

  // Deduplicate participants by participantId for new format
  const getUniqueParticipants = (participantList: RecordingParticipant[]): RecordingParticipant[] => {
    const seen = new Map<string, RecordingParticipant>();
    
    for (const participant of participantList) {
      const existing = seen.get(participant.participantId);
      if (!existing) {
        // First time seeing this participant
        seen.set(participant.participantId, participant);
      } else {
        // Keep the one with higher confidence, or manually verified, or first speaker label alphabetically
        if (participant.manuallyVerified && !existing.manuallyVerified) {
          seen.set(participant.participantId, participant);
        } else if (participant.manuallyVerified === existing.manuallyVerified && 
                   participant.confidence > existing.confidence) {
          seen.set(participant.participantId, participant);
        } else if (participant.manuallyVerified === existing.manuallyVerified && 
                   participant.confidence === existing.confidence && 
                   participant.speakerLabel < existing.speakerLabel) {
          seen.set(participant.participantId, participant);
        }
      }
    }
    
    return Array.from(seen.values());
  };

  return (
    <Group gap="xs">
      {/* Check if using old string format */}
      {typeof participants[0] === 'string' ? (
        <Badge 
          size={size} 
          variant="filled" 
          color="orange"
          leftSection={<LuCircleHelp size={12} />}
        >
          Participants need migration
        </Badge>
      ) : (
        /* New RecordingParticipant format - deduplicated */
        getUniqueParticipants(participants as RecordingParticipant[]).map((participant) => {
          // Count how many speakers this participant is assigned to
          const speakerCount = (participants as RecordingParticipant[])
            .filter(p => p.participantId === participant.participantId).length;
          
          const speakerLabels = (participants as RecordingParticipant[])
            .filter(p => p.participantId === participant.participantId)
            .map(p => p.speakerLabel)
            .sort();
          
          const tooltip = speakerCount > 1 
            ? `${speakerLabels.join(', ')} • Confidence: ${Math.round(participant.confidence * 100)}%`
            : `${participant.speakerLabel} • Confidence: ${Math.round(participant.confidence * 100)}%`;

          return (
            <Badge 
              key={participant.participantId} 
              size={size} 
              variant={participant.manuallyVerified ? "filled" : "light"}
              color={participant.confidence >= 0.8 ? "blue" : "gray"}
              title={tooltip}
            >
              {participant.displayName}
            </Badge>
          );
        })
      )}
    </Group>
  );
}