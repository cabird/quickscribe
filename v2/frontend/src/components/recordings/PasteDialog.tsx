import { useCallback, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePasteTranscript } from "@/lib/queries";

interface PasteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PasteDialog({ open, onOpenChange }: PasteDialogProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [source, setSource] = useState("other");
  const [recordedAt, setRecordedAt] = useState("");

  const pasteMutation = usePasteTranscript();

  const reset = useCallback(() => {
    setTitle("");
    setContent("");
    setSource("other");
    setRecordedAt("");
  }, []);

  const handleClose = useCallback(() => {
    if (!pasteMutation.isPending) {
      reset();
      onOpenChange(false);
    }
  }, [pasteMutation.isPending, reset, onOpenChange]);

  const handleSubmit = useCallback(async () => {
    if (!content.trim()) return;

    try {
      await pasteMutation.mutateAsync({
        title: title.trim() || undefined,
        transcript_text: content.trim(),
        recorded_at: recordedAt || undefined,
      });
      reset();
      onOpenChange(false);
    } catch {
      // Error handled by mutation
    }
  }, [content, title, source, recordedAt, pasteMutation, reset, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Paste Transcript</DialogTitle>
          <DialogDescription>
            Paste a transcript from a meeting tool like Zoom or Teams.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="paste-title">Title</Label>
            <Input
              id="paste-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Meeting title"
              disabled={pasteMutation.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="paste-content">Transcript</Label>
            <Textarea
              id="paste-content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Paste your transcript here...&#10;&#10;Speaker Name: Hello, welcome to the meeting.&#10;Another Speaker: Thanks for having us."
              className="min-h-[200px] font-mono text-sm"
              disabled={pasteMutation.isPending}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Source</Label>
              <Select value={source} onValueChange={(v) => { if (v !== null) setSource(v); }} disabled={pasteMutation.isPending}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="zoom">Zoom</SelectItem>
                  <SelectItem value="teams">Teams</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="paste-date">Date (optional)</Label>
              <Input
                id="paste-date"
                type="datetime-local"
                value={recordedAt}
                onChange={(e) => setRecordedAt(e.target.value)}
                disabled={pasteMutation.isPending}
              />
            </div>
          </div>

          {pasteMutation.isError && (
            <p className="text-sm text-destructive">
              Failed to save transcript. Please try again.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={pasteMutation.isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!content.trim() || pasteMutation.isPending}
          >
            {pasteMutation.isPending ? "Saving..." : "Save Transcript"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
