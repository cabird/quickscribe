import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { format } from "date-fns";
import { Loader2, Search, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { useKeywordSearch, useParticipants } from "@/lib/queries";
import type { Participant, SearchResult } from "@/types/models";
import { Highlighted } from "./Highlighted";

const DEBOUNCE_MS = 150;
const AI_SCOPE = 10; // top results handed to "Ask AI"
const MAX_SUGGESTIONS = 8;

// The @term being typed just before the caret, e.g. "…with @car|"
const AT_TOKEN_RE = /(^|\s)@([^\s"]*)$/;

/** Same rule as the backend: `term` prefix-matches a run of words in a name. */
function nameMatches(term: string, names: string[]): boolean {
  const want = term.toLowerCase().split(/\s+/).filter(Boolean);
  if (want.length === 0) return true;
  return names.some((name) => {
    const words = name.toLowerCase().split(/\s+/).filter(Boolean);
    for (let i = 0; i + want.length <= words.length; i++) {
      const w = words.slice(i, i + want.length);
      const head = want.slice(0, -1).every((t, k) => w[k] === t);
      if (head && w[want.length - 1].startsWith(want[want.length - 1])) return true;
    }
    return false;
  });
}

function participantNames(p: Participant): string[] {
  const first = p.first_name ?? "";
  const last = p.last_name ?? "";
  return [p.display_name, first, last, `${first} ${last}`, ...(p.aliases ?? [])].filter(
    (n) => n && n.trim(),
  );
}

/** The query minus search syntax, as a question for the AI. */
function toQuestion(q: string): string {
  return q
    .replace(/(^|\s)-("[^"]*"?|\S+)/g, " ") // exclusions
    .replace(/(^|\s)(@|person:)("[^"]*"?|\S*)/gi, " ") // people
    .replace(/\s+/g, " ")
    .trim();
}

interface FastSearchViewProps {
  onAskAi: (question: string, recordingIds: string[]) => void;
}

/**
 * Instant keyword search (no LLM). Syntax: all words required, "exact phrase",
 * -exclude, @person (anyone whose name starts with it spoke). Picking a person
 * from the @ menu pins exactly that person as a chip.
 */
export function FastSearchView({ onAskAi }: FastSearchViewProps) {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState(params.get("q") ?? "");
  const [pinned, setPinned] = useState<string[]>(
    (params.get("p") ?? "").split(",").filter(Boolean),
  );
  const [debounced, setDebounced] = useState(text);
  const inputRef = useRef<HTMLInputElement>(null);

  // @ autocomplete
  const [atTerm, setAtTerm] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);
  const { data: participantsData } = useParticipants();
  const participants = useMemo(() => participantsData?.data ?? [], [participantsData]);
  const byId = useMemo(() => new Map(participants.map((p) => [p.id, p])), [participants]);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(text), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [text]);

  // Keep the URL in sync so reload/back keeps the search
  useEffect(() => {
    const next: Record<string, string> = {};
    if (debounced) next.q = debounced;
    if (pinned.length) next.p = pinned.join(",");
    setParams(next, { replace: true });
  }, [debounced, pinned, setParams]);

  const hasQuery = debounced.trim() !== "" || pinned.length > 0;
  const { data, isFetching, isError, isPlaceholderData } = useKeywordSearch(
    { q: debounced, personIds: pinned },
    hasQuery,
  );
  const results: SearchResult[] = hasQuery ? (data?.data ?? []) : [];

  const suggestions = useMemo(() => {
    if (atTerm === null) return [];
    return participants
      .filter((p) => !pinned.includes(p.id) && nameMatches(atTerm, participantNames(p)))
      .slice(0, MAX_SUGGESTIONS);
  }, [atTerm, participants, pinned]);

  const updateAtTerm = (value: string, caret: number | null) => {
    const m = AT_TOKEN_RE.exec(value.slice(0, caret ?? value.length));
    setAtTerm(m ? m[2] : null);
    setActiveIdx(0);
  };

  const pick = (p: Participant) => {
    const input = inputRef.current;
    const caret = input?.selectionStart ?? text.length;
    const before = text.slice(0, caret).replace(AT_TOKEN_RE, "$1");
    const after = text.slice(caret);
    setText((before + after).replace(/\s{2,}/g, " "));
    setPinned((prev) => [...prev, p.id]);
    setAtTerm(null);
    requestAnimationFrame(() => input?.focus());
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing) return; // IME in progress
    if (suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) => (i + 1) % suggestions.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) => (i - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        pick(suggestions[activeIdx]);
        return;
      }
    }
    if (e.key === "Escape") {
      setAtTerm(null);
      return;
    }
    if (e.key === "Backspace" && text === "" && pinned.length > 0) {
      setPinned((prev) => prev.slice(0, -1));
    }
  };

  // From the live text (the debounced query can lag), and only once the
  // results match it, so Ask AI never uses the previous query's results
  const question = toQuestion(text);
  const resultsCurrent = text === debounced && !isFetching;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b p-4">
        <div className="mx-auto flex max-w-3xl gap-2">
          <div className="relative flex-1">
            <div
              className="flex min-h-10 flex-wrap items-center gap-1 rounded-md border border-input bg-background px-2 py-1 focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 ring-offset-background"
              onClick={() => inputRef.current?.focus()}
            >
              <Search className="mx-1 h-4 w-4 shrink-0 text-muted-foreground" />
              {pinned.map((id) => (
                <span
                  key={id}
                  className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
                >
                  @{byId.get(id)?.display_name ?? "…"}
                  <button
                    type="button"
                    aria-label="Remove person"
                    className="rounded-full hover:bg-primary/20"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPinned((prev) => prev.filter((x) => x !== id));
                    }}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
              <input
                ref={inputRef}
                value={text}
                aria-label="Search recordings"
                role="combobox"
                aria-expanded={suggestions.length > 0}
                aria-controls="person-suggestions"
                aria-activedescendant={
                  suggestions.length > 0 ? `person-suggestion-${suggestions[activeIdx]?.id}` : undefined
                }
                onChange={(e) => {
                  setText(e.target.value);
                  updateAtTerm(e.target.value, e.target.selectionStart);
                }}
                onKeyDown={onKeyDown}
                onSelect={(e) =>
                  updateAtTerm(e.currentTarget.value, e.currentTarget.selectionStart)
                }
                onBlur={() => setTimeout(() => setAtTerm(null), 150)}
                placeholder={pinned.length ? "" : 'Search… words, "exact phrase", -exclude, @person'}
                className="min-w-[8rem] flex-1 bg-transparent py-1 text-sm outline-none placeholder:text-muted-foreground"
                autoFocus
                spellCheck={false}
              />
              {isFetching && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />}
            </div>

            {suggestions.length > 0 && (
              <div
                id="person-suggestions"
                role="listbox"
                className="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-md border bg-popover shadow-md"
              >
                {suggestions.map((p, i) => (
                  <button
                    key={p.id}
                    id={`person-suggestion-${p.id}`}
                    role="option"
                    aria-selected={i === activeIdx}
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault(); // keep focus in the input
                      pick(p);
                    }}
                    className={cn(
                      "flex w-full items-baseline gap-2 px-3 py-1.5 text-left text-sm",
                      i === activeIdx ? "bg-accent" : "hover:bg-accent/60",
                    )}
                  >
                    <span className="font-medium">{p.display_name}</span>
                    {(p.first_name || p.last_name) && (
                      <span className="text-xs text-muted-foreground">
                        {[p.first_name, p.last_name].filter(Boolean).join(" ")}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          <Button
            variant="outline"
            onClick={() => onAskAi(question, results.slice(0, AI_SCOPE).map((r) => r.id))}
            disabled={question.length < 3 || (hasQuery && !resultsCurrent)}
            title={
              results.length
                ? `Ask AI, answering from the top ${Math.min(results.length, AI_SCOPE)} results`
                : "Ask AI across the whole library (slow)"
            }
          >
            <Sparkles className="h-4 w-4" />
            <span className="ml-1.5">Ask AI</span>
          </Button>
        </div>

        {/* Status line: result count, and what each @term matched */}
        {hasQuery && data && (
          <div
            className={cn(
              "mx-auto mt-2 flex max-w-3xl flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground",
              isPlaceholderData && "opacity-50",
            )}
          >
            <span>
              {data.total} result{data.total === 1 ? "" : "s"} · {data.took_ms} ms
            </span>
            {data.people.map((p) =>
              p.names.length ? (
                <span key={p.term}>
                  @{p.term} → {p.names.slice(0, 5).join(", ")}
                  {p.names.length > 5 ? ` +${p.names.length - 5}` : ""}
                </span>
              ) : (
                <span key={p.term} className="text-amber-600 dark:text-amber-400">
                  No one matches @{p.term}
                </span>
              ),
            )}
          </div>
        )}
      </div>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-3xl space-y-2 p-4">
          {!hasQuery && <SearchHelp />}

          {hasQuery && isError && (
            <Card className="border-destructive p-4 text-sm text-destructive">Search failed.</Card>
          )}

          {hasQuery && data && results.length === 0 && !isFetching && (
            <p className="py-12 text-center text-sm text-muted-foreground">
              No recordings contain all of those terms.
            </p>
          )}

          {results.map((r) => (
            <ResultCard key={r.id} result={r} onOpen={() => navigate(`/recordings/${r.id}`)} />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

function ResultCard({ result, onOpen }: { result: SearchResult; onOpen: () => void }) {
  const date = result.recorded_at ?? result.created_at;
  return (
    <Card
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      className="cursor-pointer px-4 py-3 transition-colors hover:bg-accent/50"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm font-semibold leading-snug">
          {result.title_highlight ? (
            <Highlighted text={result.title_highlight} />
          ) : (
            result.title || result.original_filename
          )}
        </h3>
        {date && (
          <span className="shrink-0 text-xs text-muted-foreground">
            {format(new Date(date), "MMM d, yyyy")}
          </span>
        )}
      </div>
      {result.speaker_names && result.speaker_names.length > 0 && (
        <p className="mt-0.5 text-xs text-muted-foreground">
          {result.speaker_names.join(", ")}
        </p>
      )}
      {result.snippets.map((s, i) => (
        <p key={i} className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
          <Highlighted text={s} />
        </p>
      ))}
    </Card>
  );
}

function SearchHelp() {
  const rows: [string, string][] = [
    ["dryden patent", "recordings containing both words (any form: patent, patents…)"],
    ['"claim construction"', "the exact phrase"],
    ["dryden -billing", "exclude recordings that mention billing"],
    ["@car", "Carmen, Carmichael, Fred Carson… spoke in it (pick from the list to pin one person)"],
    ["@carmen @tom interview", "both spoke, and interview was mentioned"],
  ];
  return (
    <div className="mx-auto max-w-xl py-10">
      <h2 className="text-center text-lg font-medium">Search your recordings</h2>
      <p className="mt-1 text-center text-sm text-muted-foreground">
        Titles, summaries, meeting notes, speakers and full transcripts. Every term must match.
      </p>
      <dl className="mt-6 space-y-2 text-sm">
        {rows.map(([q, what]) => (
          <div key={q} className="flex gap-3">
            <dt className="w-48 shrink-0 font-mono text-xs leading-5">{q}</dt>
            <dd className="text-muted-foreground">{what}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Use <span className="font-medium">Ask AI</span> for a written answer drawn from the top results.
      </p>
    </div>
  );
}
