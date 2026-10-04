import type { Recording, SpeakerMappingEntry } from "@/types/models";

export interface TranscriptEntryData {
  id: string;
  speakerLabel: string;
  displayName: string;
  text: string;
  startTimeMs?: number;
  endTimeMs?: number;
}

export interface ResolvedTranscript {
  entries: TranscriptEntryData[];
  text: string;
  speakerNames: string[];
  speakerMapping: Record<string, SpeakerMappingEntry> | null;
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
  const match = ticks.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?/);
  if (match) {
    const h = parseFloat(match[1] || "0");
    const m = parseFloat(match[2] || "0");
    const s = parseFloat(match[3] || "0");
    return Math.round((h * 3600 + m * 60 + s) * 1000);
  }
  return parseInt(ticks, 10) / 10000;
}

function parseSpeakerMapping(
  raw: Recording["speaker_mapping"]
): Record<string, SpeakerMappingEntry> | null {
  if (!raw) return null;
  try {
    return typeof raw === "string"
      ? (JSON.parse(raw) as Record<string, SpeakerMappingEntry>)
      : raw;
  } catch {
    return null;
  }
}

function resolveDisplayName(
  speakerLabel: string,
  mapping: Record<string, SpeakerMappingEntry> | null
): string {
  return mapping?.[speakerLabel]?.displayName || speakerLabel;
}

function parseTranscriptJson(
  raw: Recording["transcript_json"],
  mapping: Record<string, SpeakerMappingEntry> | null
): TranscriptEntryData[] {
  if (raw == null) return [];
  let parsed: unknown;
  if (typeof raw === "string") {
    try {
      parsed = JSON.parse(raw);
    } catch {
      return [];
    }
  } else {
    parsed = raw;
  }

  const recognizedPhrases = (parsed as Record<string, unknown>).recognizedPhrases as
    | Array<Record<string, unknown>>
    | undefined;

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

    const displayName = resolveDisplayName(speakerLabel, mapping);

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

function parseDiarizedText(
  text: string,
  mapping: Record<string, SpeakerMappingEntry> | null
): TranscriptEntryData[] {
  const entries: TranscriptEntryData[] = [];
  const lines = text.split("\n").filter((l) => l.trim());
  const speakerRegex = /^(.+?):\s*(.+)$/;

  for (let i = 0; i < lines.length; i++) {
    const match = lines[i].match(speakerRegex);
    if (match) {
      const speakerLabel = match[1].trim();
      entries.push({
        id: `entry-${i}`,
        speakerLabel,
        displayName: resolveDisplayName(speakerLabel, mapping),
        text: match[2].trim(),
      });
    } else if (entries.length > 0) {
      entries[entries.length - 1].text += " " + lines[i].trim();
    }
  }
  return entries;
}

function formatResolvedText(entries: TranscriptEntryData[]): string {
  return entries
    .map((e) => (e.displayName ? `${e.displayName}: ${e.text}` : e.text))
    .join("\n\n");
}

function collectSpeakerNames(entries: TranscriptEntryData[]): string[] {
  const seen = new Set<string>();
  const names: string[] = [];
  for (const e of entries) {
    if (e.displayName && !seen.has(e.displayName)) {
      seen.add(e.displayName);
      names.push(e.displayName);
    }
  }
  return names;
}

/**
 * Single source of truth for turning a Recording into a transcript with
 * resolved speaker names. Pure — no React, no async, no I/O.
 */
export function resolveTranscript(
  recording: Pick<
    Recording,
    "transcript_json" | "diarized_text" | "transcript_text" | "speaker_mapping"
  > | null
  | undefined
): ResolvedTranscript {
  if (!recording) {
    return { entries: [], text: "", speakerNames: [], speakerMapping: null };
  }

  const speakerMapping = parseSpeakerMapping(recording.speaker_mapping);

  let entries = parseTranscriptJson(recording.transcript_json, speakerMapping);
  if (entries.length === 0 && recording.diarized_text) {
    entries = parseDiarizedText(recording.diarized_text, speakerMapping);
  }
  if (entries.length === 0 && recording.transcript_text) {
    entries = [
      {
        id: "entry-0",
        speakerLabel: "",
        displayName: "",
        text: recording.transcript_text,
      },
    ];
  }

  return {
    entries,
    text: formatResolvedText(entries),
    speakerNames: collectSpeakerNames(entries),
    speakerMapping,
  };
}

/**
 * Parse a minutes timestamp ("mm:ss" or "h:mm:ss", brackets optional) into
 * milliseconds. Returns null for anything else, including out-of-range
 * minute/second fields. Pure.
 */
export function parseTimestampMs(raw: string): number | null {
  const match = raw.trim().match(/^\[?(?:(\d+):)?(\d{1,3}):(\d{2})\]?$/);
  if (!match) return null;
  const h = match[1] != null ? parseInt(match[1], 10) : 0;
  const m = parseInt(match[2], 10);
  const s = parseInt(match[3], 10);
  if (s >= 60 || (match[1] != null && m >= 60)) return null;
  return (h * 3600 + m * 60 + s) * 1000;
}

/**
 * Id of the transcript entry containing `timeMs`: the last timed entry whose
 * start is <= timeMs (so a time in a gap maps to the preceding turn). A time
 * before the first entry maps to the first timed entry. Entries are assumed to
 * be in time order; untimed entries are ignored. Returns null if no entry has
 * a start time. Pure.
 */
export function findEntryIdAtTime(
  entries: Pick<TranscriptEntryData, "id" | "startTimeMs">[],
  timeMs: number
): string | null {
  let first: string | null = null;
  let match: string | null = null;
  for (const entry of entries) {
    if (entry.startTimeMs == null) continue;
    if (first === null) first = entry.id;
    if (entry.startTimeMs <= timeMs) match = entry.id;
    else break;
  }
  return match ?? first;
}
