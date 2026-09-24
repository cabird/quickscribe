import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { AskAiView } from "@/components/search/AskAiView";
import { FastSearchView } from "@/components/search/FastSearchView";

/**
 * Search page: instant keyword search by default, with "Ask AI" (LLM answers)
 * as an opt-in fallback. ?mode=ai selects the AI view.
 */
export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const mode = params.get("mode") === "ai" ? "ai" : "search";
  // Recordings handed over by "Ask AI" on the keyword results
  const [scope, setScope] = useState<{ ids: string[]; autoStart: boolean } | null>(null);

  const switchTo = (next: "search" | "ai") => {
    if (next === mode) return;
    setScope(null);
    const keep: Record<string, string> = {};
    for (const k of ["q", "p"]) {
      const v = params.get(k);
      if (v) keep[k] = v;
    }
    setParams(next === "ai" ? { ...keep, mode: "ai" } : keep);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex justify-center border-b px-4 pt-3">
        <div className="inline-flex gap-1" role="tablist">
          <ModeTab active={mode === "search"} onClick={() => switchTo("search")}>
            <Search className="h-3.5 w-3.5" /> Search
          </ModeTab>
          <ModeTab active={mode === "ai"} onClick={() => switchTo("ai")}>
            <Sparkles className="h-3.5 w-3.5" /> Ask AI
          </ModeTab>
        </div>
      </div>
      <div className="min-h-0 flex-1">
        {mode === "ai" ? (
          <AskAiView
            key={scope ? `${scope.ids.join(",")}|${scope.autoStart}` : "library"}
            scopeIds={scope?.ids.length ? scope.ids : undefined}
            autoStart={scope?.autoStart}
            onClearScope={() => setScope({ ids: [], autoStart: true })}
          />
        ) : (
          <FastSearchView
            onAskAi={(question, ids) => {
              setScope({ ids, autoStart: true });
              const p = params.get("p");
              setParams({ q: question, mode: "ai", ...(p ? { p } : {}) });
            }}
          />
        )}
      </div>
    </div>
  );
}

function ModeTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 pb-2 text-sm transition-colors",
        active
          ? "border-primary font-medium text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}
