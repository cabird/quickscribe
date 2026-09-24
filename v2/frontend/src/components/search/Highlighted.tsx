import { Fragment } from "react";

// Must match search_service.HL_START / HL_END on the backend
const HL_START = "\u0002";
const HL_END = "\u0003";

/** Render search text with its matched terms wrapped in <mark>. */
export function Highlighted({ text }: { text: string }) {
  const parts: { text: string; hit: boolean }[] = [];
  for (const chunk of text.split(HL_START)) {
    const end = chunk.indexOf(HL_END);
    if (end === -1) {
      parts.push({ text: chunk, hit: false });
    } else {
      parts.push({ text: chunk.slice(0, end), hit: true });
      parts.push({ text: chunk.slice(end + 1), hit: false });
    }
  }
  return (
    <>
      {parts.map((p, i) =>
        p.hit ? (
          <mark
            key={i}
            className="rounded-sm bg-amber-200/70 px-0.5 text-foreground dark:bg-amber-500/30"
          >
            {p.text}
          </mark>
        ) : (
          <Fragment key={i}>{p.text}</Fragment>
        ),
      )}
    </>
  );
}
