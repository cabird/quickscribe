import { useCallback, useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { Plus } from "lucide-react";
import type { Participant } from "@/types/models";

interface SpeakerDropdownProps {
  participants: Participant[];
  currentName: string;
  onSelect: (participant: Participant) => void;
  onCreateNew: (name: string) => void;
  onClose: () => void;
  className?: string;
}

export function SpeakerDropdown({
  participants,
  currentName,
  onSelect,
  onCreateNew,
  onClose,
  className,
}: SpeakerDropdownProps) {
  const [query, setQuery] = useState("");
  const [highlightIndex, setHighlightIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const closingRef = useRef(false);

  const filtered = participants.filter((p) => {
    if (!query) return true;
    const q = query.toLowerCase();
    return (
      p.display_name.toLowerCase().includes(q) ||
      p.first_name?.toLowerCase().includes(q) ||
      p.last_name?.toLowerCase().includes(q) ||
      (Array.isArray(p.aliases) && p.aliases.some((a: string) => a.toLowerCase().includes(q))) ||
      p.email?.toLowerCase().includes(q)
    );
  });

  const showCreateOption =
    query.trim().length > 0 &&
    !filtered.some((p) => p.display_name.toLowerCase() === query.trim().toLowerCase());

  const totalItems = filtered.length + (showCreateOption ? 1 : 0);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    setHighlightIndex(0);
  }, [query]);

  // Close on click outside — delay slightly so button onMouseDown fires first
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (closingRef.current) return;
      if (listRef.current && !listRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    // Small delay so the opening click doesn't immediately close
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handler);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handler);
    };
  }, [onClose]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setHighlightIndex((i) => Math.min(i + 1, totalItems - 1));
          break;
        case "ArrowUp":
          e.preventDefault();
          setHighlightIndex((i) => Math.max(i - 1, 0));
          break;
        case "Enter":
        case "Tab":
          e.preventDefault();
          if (highlightIndex < filtered.length) {
            onSelect(filtered[highlightIndex]);
          } else if (showCreateOption) {
            onCreateNew(query.trim());
          }
          break;
        case "Escape":
          e.preventDefault();
          onClose();
          break;
      }
    },
    [highlightIndex, filtered, showCreateOption, query, onSelect, onCreateNew, onClose, totalItems]
  );

  // Use onMouseDown to fire before the document handler closes us
  const handleSelectClick = useCallback(
    (p: Participant) => {
      closingRef.current = true;
      onSelect(p);
    },
    [onSelect]
  );

  const handleCreateClick = useCallback(() => {
    closingRef.current = true;
    onCreateNew(query.trim());
  }, [onCreateNew, query]);

  return (
    <div
      ref={listRef}
      className={cn(
        "absolute z-50 w-64 rounded-md border bg-popover shadow-lg",
        className
      )}
      onKeyDown={handleKeyDown}
    >
      <div className="p-2">
        <Input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Rename "${currentName}"...`}
          className="h-8 text-sm"
        />
      </div>

      <div className="max-h-48 overflow-y-auto px-1 pb-1">
        {filtered.map((p, i) => (
          <button
            key={p.id}
            className={cn(
              "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm",
              i === highlightIndex ? "bg-accent text-accent-foreground" : "hover:bg-accent/50"
            )}
            onMouseEnter={() => setHighlightIndex(i)}
            onMouseDown={(e) => {
              e.preventDefault(); // Prevent focus loss
              handleSelectClick(p);
            }}
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium">
              {p.display_name.charAt(0).toUpperCase()}
            </span>
            <div className="min-w-0">
              <p className="truncate font-medium">{p.display_name}</p>
              {p.organization && (
                <p className="truncate text-xs text-muted-foreground">{p.organization}</p>
              )}
            </div>
          </button>
        ))}

        {showCreateOption && (
          <button
            className={cn(
              "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm",
              highlightIndex === filtered.length
                ? "bg-accent text-accent-foreground"
                : "hover:bg-accent/50"
            )}
            onMouseEnter={() => setHighlightIndex(filtered.length)}
            onMouseDown={(e) => {
              e.preventDefault(); // Prevent focus loss
              handleCreateClick();
            }}
          >
            <Plus className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span>
              Add &quot;{query.trim()}&quot;
            </span>
          </button>
        )}

        {filtered.length === 0 && !showCreateOption && (
          <p className="px-2 py-3 text-center text-xs text-muted-foreground">No participants found</p>
        )}
      </div>
    </div>
  );
}
