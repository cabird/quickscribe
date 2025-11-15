/**
 * Generate a reference ID for a transcript entry
 * Format: ref_ + 2 letters + 2 numbers (e.g., ref_AB01, ref_CD23)
 */
export function generateRefId(index: number): string {
  const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const letterPairIndex = Math.floor(index / 100);
  const numberPart = String(index % 100).padStart(2, '0');

  const letter1 = letters[Math.floor(letterPairIndex / 26) % 26];
  const letter2 = letters[letterPairIndex % 26];

  return `ref_${letter1}${letter2}${numberPart}`;
}

/**
 * Extract reference IDs from a message
 * Returns array of ref IDs found in [[ref_XX##]] format
 */
export function extractRefs(message: string): string[] {
  const refPattern = /\[\[(ref_[A-Z]{2}\d{2})\]\]/g;
  const matches = [...message.matchAll(refPattern)];
  return matches.map(match => match[1]);
}

/**
 * Replace [[REF]] tags with clickable reference numbers
 * Returns object with display text and reference mapping
 */
export function formatMessageWithRefs(
  message: string,
  refMapping: Map<string, number>
): { displayText: string; references: Array<{ refId: string; displayNum: number; positions: number[] }> } {
  const refs: Array<{ refId: string; displayNum: number; positions: number[] }> = [];
  let displayNum = 1;
  const refToNum = new Map<string, number>();

  // First pass: assign display numbers to unique refs
  const extractedRefs = extractRefs(message);
  extractedRefs.forEach(refId => {
    if (!refToNum.has(refId) && refMapping.has(refId)) {
      refToNum.set(refId, displayNum);
      refs.push({ refId, displayNum, positions: [] });
      displayNum++;
    }
  });

  // Second pass: replace refs and track positions
  let displayText = message;
  const refPattern = /\[\[(ref_[A-Z]{2}\d{2})\]\]/g;

  displayText = displayText.replace(refPattern, (_match, refId) => {
    const num = refToNum.get(refId);
    if (num !== undefined) {
      return `[${num}]`;
    }
    // Invalid ref - strip it
    return '';
  });

  return { displayText, references: refs };
}
