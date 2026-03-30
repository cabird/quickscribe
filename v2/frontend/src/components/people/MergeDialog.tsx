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
import { ArrowRight } from "lucide-react";
import { useMergeParticipants, useParticipants } from "@/lib/queries";
import type { Participant } from "@/types/models";

interface MergeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  primaryParticipant: Participant;
}

export function MergeDialog({ open, onOpenChange, primaryParticipant }: MergeDialogProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSecondary, setSelectedSecondary] = useState<Participant | null>(null);

  const { data: participantsData } = useParticipants();
  const participants = participantsData?.data ?? [];
  const mergeMutation = useMergeParticipants();

  const filteredParticipants = participants.filter((p: Participant) => {
    if (p.id === primaryParticipant.id) return false;
    if (!searchQuery) return false;
    const q = searchQuery.toLowerCase();
    return (
      p.display_name.toLowerCase().includes(q) ||
      p.first_name?.toLowerCase().includes(q) ||
      p.last_name?.toLowerCase().includes(q)
    );
  });

  const handleClose = useCallback(() => {
    if (!mergeMutation.isPending) {
      setSearchQuery("");
      setSelectedSecondary(null);
      onOpenChange(false);
    }
  }, [mergeMutation.isPending, onOpenChange]);

  const handleMerge = useCallback(async () => {
    if (!selectedSecondary) return;

    try {
      await mergeMutation.mutateAsync({
        targetId: primaryParticipant.id,
        sourceId: selectedSecondary.id,
      });
      handleClose();
    } catch {
      // Error handled by mutation
    }
  }, [selectedSecondary, primaryParticipant.id, mergeMutation, handleClose]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Merge Participants</DialogTitle>
          <DialogDescription>
            Merge another participant into {primaryParticipant.display_name}. The secondary
            participant will be removed and their data merged.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Search */}
          <div className="space-y-2">
            <Label>Search for participant to merge</Label>
            <Input
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setSelectedSecondary(null);
              }}
              placeholder="Type a name to search..."
              disabled={mergeMutation.isPending}
            />
          </div>

          {/* Search results */}
          {searchQuery && filteredParticipants.length > 0 && !selectedSecondary && (
            <div className="max-h-40 overflow-y-auto rounded-md border">
              {filteredParticipants.map((p) => (
                <button
                  key={p.id}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => setSelectedSecondary(p)}
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium">
                    {p.display_name.charAt(0).toUpperCase()}
                  </span>
                  <span>{p.display_name}</span>
                  {p.organization && (
                    <span className="text-xs text-muted-foreground">({p.organization})</span>
                  )}
                </button>
              ))}
            </div>
          )}

          {searchQuery && filteredParticipants.length === 0 && !selectedSecondary && (
            <p className="text-center text-sm text-muted-foreground">No matching participants</p>
          )}

          {/* Merge preview */}
          {selectedSecondary && (
            <div className="rounded-lg border bg-muted/30 p-4">
              <p className="mb-3 text-xs font-medium uppercase text-muted-foreground">
                Merge Preview
              </p>
              <div className="flex items-center justify-center gap-4">
                <div className="text-center">
                  <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 text-sm font-medium text-destructive">
                    {selectedSecondary.display_name.charAt(0).toUpperCase()}
                  </div>
                  <p className="mt-1 text-sm font-medium">{selectedSecondary.display_name}</p>
                  <p className="text-xs text-muted-foreground">will be removed</p>
                </div>

                <ArrowRight className="h-5 w-5 text-muted-foreground" />

                <div className="text-center">
                  <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary">
                    {primaryParticipant.display_name.charAt(0).toUpperCase()}
                  </div>
                  <p className="mt-1 text-sm font-medium">{primaryParticipant.display_name}</p>
                  <p className="text-xs text-muted-foreground">will be kept</p>
                </div>
              </div>

              <Button
                variant="ghost"
                size="sm"
                className="mt-2 w-full text-xs"
                onClick={() => setSelectedSecondary(null)}
              >
                Choose different participant
              </Button>
            </div>
          )}

          {mergeMutation.isError && (
            <p className="text-sm text-destructive">
              Merge failed. Please try again.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={mergeMutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleMerge}
            disabled={!selectedSecondary || mergeMutation.isPending}
          >
            {mergeMutation.isPending ? "Merging..." : "Confirm Merge"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
