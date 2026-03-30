import { useMemo } from "react";

export interface TranscriptEntryData {
  id: string;
  speakerLabel: string;
  displayName: string;
  text: string;
  startTimeMs?: number;
  endTimeMs?: number;
}

interface TranscriptJsonPhrase {
  speaker?: number | string;
  text: string;
  offsetMs?: number;
  durationMs?: number;
  offset?: string;
  duration?: string;
}

function ticksToMs(ticks: string): number {
  // ISO 8601 duration or raw ticks
  const match = ticks.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?/);
  if (match) {
    const h = parseFloat(match[1] || "0");
    const m = parseFloat(match[2] || "0");
    const s = parseFloat(match[3] || "0");
    return Math.round((h * 3600 + m * 60 + s) * 1000);
  }
  return parseInt(ticks, 10) / 10000; // .NET ticks to ms
}

function parseDiarizedText(text: string): TranscriptEntryData[] {
  const entries: TranscriptEntryData[] = [];
  const lines = text.split("\n").filter((l) => l.trim());
  const speakerRegex = /^(.+?):\s*(.+)$/;

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(speakerRegex);
    if (match) {
      entries.push({
        id: `entry-${i}`,
        speakerLabel: match[1].trim(),
        displayName: match[1].trim(),
        text: match[2].trim(),
      });
    } else if (entries.length > 0) {
      // Continuation of previous entry
      entries[entries.length - 1].text += " " + lines[i].trim();
    }
  }
  return entries;
}

function parseTranscriptJson(
  json: string,
  speakerMapping?: Record<string, { displayName?: string }>
): TranscriptEntryData[] {
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(json);
  } catch {
    return [];
  }

  // Azure Speech Services format: { recognizedPhrases: [...] }
  // Each phrase has: speaker (int), offset, duration, nBest[0].display
  const recognizedPhrases = (parsed as Record<string, unknown>).recognizedPhrases as Array<Record<string, unknown>> | undefined;

  let phrases: TranscriptJsonPhrase[];
  if (recognizedPhrases && Array.isArray(recognizedPhrases)) {
    phrases = recognizedPhrases.map((rp) => {
      const nBest = rp.nBest as Array<Record<string, string>> | undefined;
      const text = nBest?.[0]?.display || nBest?.[0]?.lexical || "";
      return {
        speaker: rp.speaker as number,
        text,
        offset: rp.offset as string | undefined,
        duration: rp.duration as string | undefined,
      };
    });
  } else if (Array.isArray(parsed)) {
    phrases = parsed as TranscriptJsonPhrase[];
  } else {
    // Try common alternative formats
    phrases = ((parsed as Record<string, unknown>).phrases ||
      (parsed as Record<string, unknown>).segments ||
      (parsed as Record<string, unknown>).results ||
      []) as TranscriptJsonPhrase[];
  }

  const entries: TranscriptEntryData[] = [];

  for (const phrase of phrases) {
    if (!phrase.text || !phrase.text.trim()) continue;

    const speakerLabel = phrase.speaker != null ? `Speaker ${phrase.speaker}` : "Unknown";
    const startTimeMs = phrase.offsetMs ?? (phrase.offset ? ticksToMs(phrase.offset) : undefined);
    const durationMs =
      phrase.durationMs ?? (phrase.duration ? ticksToMs(phrase.duration) : undefined);
    const endTimeMs =
      startTimeMs != null && durationMs != null ? startTimeMs + durationMs : undefined;

    // Resolve display name from speaker mapping
    const mappingEntry = speakerMapping?.[speakerLabel];
    const displayName = mappingEntry?.displayName || speakerLabel;

    // Merge consecutive same-speaker phrases
    const last = entries[entries.length - 1];
    if (last && last.speakerLabel === speakerLabel) {
      last.text += " " + phrase.text;
      if (endTimeMs != null) last.endTimeMs = endTimeMs;
    } else {
      entries.push({
        id: `entry-${entries.length}`,
        speakerLabel,
        displayName,
        text: phrase.text,
        startTimeMs,
        endTimeMs,
      });
    }
  }

  return entries;
}

export function useTranscriptParser(
  transcriptJson?: string | null,
  diarizedText?: string | null,
  plainText?: string | null,
  speakerMapping?: Record<string, { displayName?: string }> | null
): TranscriptEntryData[] {
  return useMemo(() => {
    if (transcriptJson) {
      const parsed = parseTranscriptJson(transcriptJson, speakerMapping ?? undefined);
      if (parsed.length > 0) return parsed;
    }
    if (diarizedText) {
      return parseDiarizedText(diarizedText);
    }
    if (plainText) {
      return [
        {
          id: "entry-0",
          speakerLabel: "",
          displayName: "",
          text: plainText,
        },
      ];
    }
    return [];
  }, [transcriptJson, diarizedText, plainText, speakerMapping]);
}
