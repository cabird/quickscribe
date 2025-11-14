import type { Recording, Transcription } from '../types';

export function exportTranscriptToFile(
  recording: Recording,
  transcription: Transcription
): void {
  if (!transcription.diarized_transcript) {
    throw new Error('No transcript available to export');
  }

  // Build formatted transcript with metadata header
  let content = '';

  // Add header
  content += `${recording.title || 'Untitled Recording'}\n`;
  content += '='.repeat(60) + '\n\n';

  // Add metadata
  if (recording.recorded_timestamp) {
    const date = new Date(recording.recorded_timestamp);
    content += `Date: ${date.toLocaleDateString()} ${date.toLocaleTimeString()}\n`;
  }
  if (recording.duration) {
    const hours = Math.floor(recording.duration / 3600);
    const minutes = Math.floor((recording.duration % 3600) / 60);
    content += `Duration: ${hours > 0 ? `${hours}h ` : ''}${minutes}m\n`;
  }
  if (recording.participants && recording.participants.length > 0) {
    const speakerNames = recording.participants.map((p: any) =>
      typeof p === 'string' ? p : p.displayName || p.name
    );
    content += `Participants: ${speakerNames.join(', ')}\n`;
  }
  if (recording.description) {
    content += `\nDescription: ${recording.description}\n`;
  }

  content += '\n' + '='.repeat(60) + '\n\n';

  // Add transcript with speaker names
  content += 'TRANSCRIPT\n\n';
  content += transcription.diarized_transcript;

  // Create blob and download
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;

  // Create filename from title and date
  const filename = `${recording.title || 'transcript'}_${new Date().toISOString().split('T')[0]}.txt`;
  link.download = filename;

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
