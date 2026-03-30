import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { Minimize2, Send, Trash2, X } from "lucide-react";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useChatWithTranscript } from "@/lib/queries";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface ChatPanelProps {
  recordingId: string;
  isOpen: boolean;
  onClose: () => void;
  onHighlightEntry?: (entryId: string) => void;
}

const REF_REGEX = /\[\[ref_(\w+)\]\]/g;

function renderMessageContent(content: string, onHighlightEntry?: (entryId: string) => void): React.ReactNode {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let refCounter = 0;
  let match: RegExpExecArray | null;

  const regex = new RegExp(REF_REGEX.source, "g");
  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index));
    }
    refCounter++;
    const refId = match[1];
    parts.push(
      <button
        key={`ref-${refCounter}`}
        className="inline-flex items-center justify-center rounded bg-primary/10 px-1 text-xs font-medium text-primary hover:bg-primary/20"
        onClick={() => {
          onHighlightEntry?.(`entry-${refId}`);
        }}
        title="Click to scroll to referenced transcript section"
      >
        [{refCounter}]
      </button>
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex));
  }
  return parts.length > 0 ? parts : content;
}

export function ChatPanel({ recordingId, isOpen, onClose, onHighlightEntry }: ChatPanelProps) {
  const isMobile = useIsMobile();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const chatMutation = useChatWithTranscript();

  // Scroll to bottom on new messages
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || chatMutation.isPending) return;

    const userMessage: ChatMessage = { role: "user", content: text };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput("");

    try {
      const response = await chatMutation.mutateAsync({
        recording_id: recordingId,
        messages: newMessages,
      });
      setMessages([
        ...newMessages,
        { role: "assistant", content: response.message },
      ]);
    } catch {
      setMessages([
        ...newMessages,
        { role: "assistant", content: "Sorry, an error occurred. Please try again." },
      ]);
    }
  }, [input, messages, recordingId, chatMutation]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleClear = useCallback(() => {
    setMessages([]);
  }, []);

  const chatContent = (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Chat with Transcript</h3>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleClear} title="Clear conversation">
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
          {!isMobile && (
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose} title="Minimize">
              <Minimize2 className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose} title="Close">
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 px-4">
        <div ref={scrollRef} className="space-y-4 py-4">
          {messages.length === 0 && (
            <p className="text-center text-sm text-muted-foreground">
              Ask a question about this transcript
            </p>
          )}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                msg.role === "user"
                  ? "ml-auto bg-primary text-primary-foreground"
                  : "bg-muted"
              )}
            >
              <div className="whitespace-pre-wrap">
                {msg.role === "assistant"
                  ? renderMessageContent(msg.content, onHighlightEntry)
                  : msg.content}
              </div>
            </div>
          ))}
          {chatMutation.isPending && (
            <div className="max-w-[85%] rounded-lg bg-muted px-3 py-2 text-sm">
              <span className="inline-flex gap-1">
                <span className="animate-bounce">.</span>
                <span className="animate-bounce [animation-delay:0.1s]">.</span>
                <span className="animate-bounce [animation-delay:0.2s]">.</span>
              </span>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t p-3">
        <div className="flex gap-2">
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the transcript..."
            className="min-h-[40px] max-h-32 resize-none text-sm"
            rows={1}
          />
          <Button
            size="icon"
            className="h-10 w-10 shrink-0"
            onClick={handleSend}
            disabled={!input.trim() || chatMutation.isPending}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );

  // Mobile: full-screen sheet
  if (isMobile) {
    return (
      <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
        <SheetContent side="bottom" className="h-[90vh] p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Chat with Transcript</SheetTitle>
          </SheetHeader>
          {chatContent}
        </SheetContent>
      </Sheet>
    );
  }

  // Desktop: side panel
  if (!isOpen) return null;

  return (
    <div className="flex h-full w-[40%] min-w-[300px] max-w-[500px] shrink-0 flex-col border-l bg-background">
      {chatContent}
    </div>
  );
}
