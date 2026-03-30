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
import { useCreateParticipant } from "@/lib/queries";

interface AddParticipantDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddParticipantDialog({ open, onOpenChange }: AddParticipantDialogProps) {
  const [displayName, setDisplayName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [organization, setOrganization] = useState("");
  const [notes, setNotes] = useState("");
  const [aliases, setAliases] = useState("");

  const createMutation = useCreateParticipant();

  const reset = useCallback(() => {
    setDisplayName("");
    setFirstName("");
    setLastName("");
    setEmail("");
    setRole("");
    setOrganization("");
    setNotes("");
    setAliases("");
  }, []);

  const handleClose = useCallback(() => {
    if (!createMutation.isPending) {
      reset();
      onOpenChange(false);
    }
  }, [createMutation.isPending, reset, onOpenChange]);

  const handleSubmit = useCallback(async () => {
    if (!displayName.trim()) return;

    try {
      await createMutation.mutateAsync({
        display_name: displayName.trim(),
        first_name: firstName.trim() || undefined,
        last_name: lastName.trim() || undefined,
        email: email.trim() || undefined,
        role: role.trim() || undefined,
        organization: organization.trim() || undefined,
        notes: notes.trim() || undefined,
        aliases: aliases
          .split(",")
          .map((a) => a.trim())
          .filter(Boolean),
      });
      reset();
      onOpenChange(false);
    } catch {
      // Error handled by mutation
    }
  }, [
    displayName, firstName, lastName, email, role, organization, notes, aliases,
    createMutation, reset, onOpenChange,
  ]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Person</DialogTitle>
          <DialogDescription>
            Add a new participant to your contacts.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 max-h-[60vh] overflow-y-auto px-0.5">
          <div className="space-y-2">
            <Label htmlFor="add-display-name">Display Name *</Label>
            <Input
              id="add-display-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="How this person appears in transcripts"
              disabled={createMutation.isPending}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="add-first-name">First Name</Label>
              <Input
                id="add-first-name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                disabled={createMutation.isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-last-name">Last Name</Label>
              <Input
                id="add-last-name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                disabled={createMutation.isPending}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="add-email">Email</Label>
            <Input
              id="add-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={createMutation.isPending}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="add-role">Role</Label>
              <Input
                id="add-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="Job title"
                disabled={createMutation.isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-org">Organization</Label>
              <Input
                id="add-org"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                disabled={createMutation.isPending}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="add-aliases">Aliases</Label>
            <Input
              id="add-aliases"
              value={aliases}
              onChange={(e) => setAliases(e.target.value)}
              placeholder="Comma-separated alternative names"
              disabled={createMutation.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="add-notes">Notes</Label>
            <Textarea
              id="add-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="min-h-[60px]"
              disabled={createMutation.isPending}
            />
          </div>

          {createMutation.isError && (
            <p className="text-sm text-destructive">
              Failed to create participant. Please try again.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={createMutation.isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!displayName.trim() || createMutation.isPending}
          >
            {createMutation.isPending ? "Creating..." : "Add Person"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
