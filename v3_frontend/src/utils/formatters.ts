import type { RecordingParticipant } from '../types';

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

export function formatSpeakersList(speakers?: string[] | RecordingParticipant[]): string {
  if (!speakers || speakers.length === 0) return 'No speakers';

  // Handle both string[] and RecordingParticipant[] formats
  const speakerNames = speakers.map(s =>
    typeof s === 'string' ? s : s.displayName || 'Unknown'
  );

  if (speakerNames.length <= 3) {
    return speakerNames.join(', ');
  }

  return `${speakerNames.slice(0, 2).join(', ')}, +${speakerNames.length - 2} more`;
}
