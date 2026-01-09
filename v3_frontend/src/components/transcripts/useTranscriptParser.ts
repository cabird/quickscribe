import { useMemo } from 'react';
import type { Transcription } from '../../types';

// Interface for parsed transcript entries with timestamps
export interface TranscriptEntryData {
  speakerLabel: string;  // Original label (e.g., "Speaker 1")
  displayName: string;   // Display name (mapped or original)
  text: string;
  startTimeMs: number;   // Start time in milliseconds
  endTimeMs: number;     // End time in milliseconds
}

// Interface for transcript_json phrase structure
interface TranscriptPhrase {
  speaker: number;
  offsetMilliseconds?: number;
  durationMilliseconds?: number;
  offsetInTicks?: number;
  durationInTicks?: number;
  nBest?: Array<{ display?: string }>;
}

interface UseTranscriptParserResult {
  entries: TranscriptEntryData[];
  speakerIndexMap: Map<string, number>;
  hasTimestamps: boolean;
}

/**
 * Custom hook to parse transcript data into structured entries.
 * Handles transcript_json (with timestamps), diarized_transcript, and plain text fallbacks.
 */
export function useTranscriptParser(
  transcription: Transcription | null,
  speakerMappings: Record<string, string>
): UseTranscriptParserResult {
  return useMemo(() => {
    const entries: TranscriptEntryData[] = [];

    if (!transcription) {
      return { entries, speakerIndexMap: new Map(), hasTimestamps: false };
    }

    // Helper to resolve speaker display name (checks local rename, server mapping, then default)
    const getDisplayName = (speakerLabel: string): string => {
      let displayName = speakerMappings[speakerLabel];
      if (!displayName && transcription.speaker_mapping?.[speakerLabel]) {
        displayName = transcription.speaker_mapping[speakerLabel].displayName || speakerLabel;
      }
      return displayName || speakerLabel;
    };

    // Try parsing transcript_json first (has timestamps)
    if (transcription.transcript_json) {
      try {
        const jsonData = JSON.parse(transcription.transcript_json);
        const phrases: TranscriptPhrase[] = jsonData.recognizedPhrases || [];

        // Merge consecutive same-speaker phrases
        let currentSpeaker: number | null = null;
        let currentTexts: string[] = [];
        let currentStartMs = 0;
        let currentEndMs = 0;

        const flushEntry = () => {
          if (currentSpeaker !== null && currentTexts.length > 0) {
            const speakerLabel = `Speaker ${currentSpeaker}`;

            entries.push({
              speakerLabel,
              displayName: getDisplayName(speakerLabel),
              text: currentTexts.join(' '),
              startTimeMs: currentStartMs,
              endTimeMs: currentEndMs,
            });
          }
        };

        phrases.forEach((phrase) => {
          const speaker = phrase.speaker;
          const text = phrase.nBest?.[0]?.display || '';

          // Get timing - prefer milliseconds, fall back to ticks
          const offsetMs = phrase.offsetMilliseconds ?? (phrase.offsetInTicks ? phrase.offsetInTicks / 10000 : 0);
          const durationMs = phrase.durationMilliseconds ?? (phrase.durationInTicks ? phrase.durationInTicks / 10000 : 0);

          if (speaker === currentSpeaker) {
            // Same speaker - append text and extend end time
            currentTexts.push(text);
            currentEndMs = offsetMs + durationMs;
          } else {
            // New speaker - flush previous entry and start new one
            flushEntry();
            currentSpeaker = speaker;
            currentTexts = [text];
            currentStartMs = offsetMs;
            currentEndMs = offsetMs + durationMs;
          }
        });

        // Flush last entry
        flushEntry();

      } catch (err) {
        console.error('Failed to parse transcript_json:', err);
      }
    }

    // Fallback to diarized_transcript if no entries from JSON
    if (entries.length === 0 && transcription.diarized_transcript) {
      const paragraphs = transcription.diarized_transcript.split('\n\n').filter(p => p.trim());

      paragraphs.forEach((paragraph) => {
        const match = paragraph.match(/^(.+?):\s*(.+)$/s);
        if (match) {
          const speakerLabel = match[1].trim();

          entries.push({
            speakerLabel,
            displayName: getDisplayName(speakerLabel),
            text: match[2].trim(),
            startTimeMs: 0,
            endTimeMs: 0,
          });
        }
      });
    }

    // Final fallback: plain text
    if (entries.length === 0 && transcription.text) {
      const paragraphs = transcription.text.split('\n\n').filter(p => p.trim());
      paragraphs.forEach((para) => {
        entries.push({
          speakerLabel: 'Speaker',
          displayName: 'Speaker',
          text: para.trim(),
          startTimeMs: 0,
          endTimeMs: 0,
        });
      });
    }

    // Build speaker index map based on order of first appearance
    const speakerIndexMap = new Map<string, number>();
    entries.forEach((entry) => {
      if (!speakerIndexMap.has(entry.speakerLabel)) {
        speakerIndexMap.set(entry.speakerLabel, speakerIndexMap.size);
      }
    });

    // Check if we have timestamps available
    const hasTimestamps = entries.some(e => e.startTimeMs > 0);

    return { entries, speakerIndexMap, hasTimestamps };
  }, [transcription, speakerMappings]);
}
