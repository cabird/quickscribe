import type { SyncRunType } from "@/types/models";

/** Numeric run stats, parsed from the API's `stats_json` string. */
export type RunStats = Record<string, number>;

export function parseRunStats(statsJson: string | null | undefined): RunStats | null {
  if (!statsJson) return null;
  try {
    const parsed: unknown = JSON.parse(statsJson);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
    const stats: RunStats = {};
    for (const [key, value] of Object.entries(parsed)) {
      if (typeof value === "number") stats[key] = value;
    }
    return stats;
  } catch {
    return null;
  }
}

export interface StatPart {
  label: string;
  tone?: "muted" | "success" | "destructive";
}

/** One-line summary for a job card, by run type. */
export function summarizeRunStats(type: SyncRunType, stats: RunStats): StatPart[] {
  const parts: StatPart[] = [];
  const n = (key: string) => stats[key] ?? 0;

  if (type === "plaud_sync") {
    parts.push({ label: `${n("new_recordings")} submitted for transcription` });
    if (n("errors") > 0) parts.push({ label: `${n("errors")} errors`, tone: "destructive" });
  } else if (type === "transcription_poll") {
    // Older poll runs recorded only {completed, polled}; for those, failed
    // jobs and errors are folded into "still running" (rows age out in 30 days)
    const stillRunning =
      "still_running" in stats ? n("still_running") : Math.max(0, n("polled") - n("completed"));
    parts.push({ label: `${n("completed")} completed`, tone: n("completed") > 0 ? "success" : undefined });
    parts.push({ label: `${stillRunning} still running` });
    if (n("failed") > 0) parts.push({ label: `${n("failed")} failed`, tone: "destructive" });
    if (n("errors") > 0) parts.push({ label: `${n("errors")} errors`, tone: "destructive" });
  } else if (n("errors") > 0) {
    parts.push({ label: `${n("errors")} errors`, tone: "destructive" });
  }
  return parts;
}
