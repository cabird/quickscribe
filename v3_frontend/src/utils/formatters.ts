import type { RecordingParticipant } from '../types';

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

/**
 * Format a token count as an abbreviated string (e.g., 2100 → "2.1k", 1500000 → "1.5M")
 */
export function formatTokenCount(count: number | undefined): string {
  if (count === undefined || count === null) return '';
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`;
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}k`;
  }
  return count.toString();
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
