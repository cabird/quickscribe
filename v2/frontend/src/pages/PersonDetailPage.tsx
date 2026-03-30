import { useCallback, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { format, formatDistanceToNow } from "date-fns";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  ArrowLeft,
  GitMerge,
  Pencil,
  Save,
  Trash2,
  X,
} from "lucide-react";
import { MergeDialog } from "@/components/people/MergeDialog";
import { useIsMobile } from "@/hooks/useIsMobile";
import {
  useParticipant,
  useUpdateParticipant,
  useDeleteParticipant,
} from "@/lib/queries";
import type {
  UpdateParticipantRequest,
} from "@/types/models";

export default function PersonDetailPage() {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();

  const [isEditing, setIsEditing] = useState(false);
  const [showMerge, setShowMerge] = useState(false);
  const [editForm, setEditForm] = useState<UpdateParticipantRequest>({});

  const { data: participant, isLoading } = useParticipant(id!);

  const updateMutation = useUpdateParticipant();
  const deleteMutation = useDeleteParticipant();

  const startEditing = useCallback(() => {
    if (!participant) return;
    setEditForm({
      display_name: participant.display_name,
      first_name: participant.first_name ?? undefined,
      last_name: participant.last_name ?? undefined,
      email: participant.email ?? undefined,
      role: participant.role ?? undefined,
      organization: participant.organization ?? undefined,
      relationship: participant.relationship ?? undefined,
      notes: participant.notes ?? undefined,
      aliases: participant.aliases ?? [],
      is_user: participant.is_user,
    });
    setIsEditing(true);
  }, [participant]);

  const handleSave = useCallback(async () => {
    if (!id) return;
    await updateMutation.mutateAsync({ id, body: editForm });
    setIsEditing(false);
  }, [id, editForm, updateMutation]);

  const handleDelete = useCallback(async () => {
    if (!id) return;
    await deleteMutation.mutateAsync(id);
    navigate("/people");
  }, [id, deleteMutation, navigate]);

  const handleBack = useCallback(() => {
    navigate("/people");
  }, [navigate]);

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!participant) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Person not found
      </div>
    );
  }

  const initials = getInitials(participant.display_name);

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-2xl space-y-6 p-4 md:p-6">
        {/* Header */}
        <div className="flex items-start gap-4">
          {isMobile && (
            <Button
              variant="ghost"
              size="icon"
              className="mt-1 h-8 w-8 shrink-0"
              onClick={handleBack}
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
          )}

          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xl font-semibold text-primary">
            {initials}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold">
                {participant.display_name}
              </h1>
              {participant.is_user && (
                <Badge variant="secondary">Me</Badge>
              )}
            </div>
            {(participant.first_name || participant.last_name) && (
              <p className="text-sm text-muted-foreground">
                {[participant.first_name, participant.last_name]
                  .filter(Boolean)
                  .join(" ")}
              </p>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex shrink-0 items-center gap-1">
            {isEditing ? (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setIsEditing(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
                <Button
                  size="icon"
                  className="h-8 w-8"
                  onClick={handleSave}
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-4 w-4" />
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => setShowMerge(true)}
                  title="Merge"
                >
                  <GitMerge className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={startEditing}
                  title="Edit"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-destructive hover:bg-accent hover:text-destructive"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>
                        Delete {participant.display_name}?
                      </AlertDialogTitle>
                      <AlertDialogDescription>
                        This will remove this participant and clear their
                        speaker assignments in recordings.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleDelete}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </>
            )}
          </div>
        </div>

        <Separator />

        {/* Info grid */}
        {isEditing ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Display Name</Label>
                <Input
                  value={editForm.display_name ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, display_name: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={editForm.email ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, email: e.target.value })
                  }
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>First Name</Label>
                <Input
                  value={editForm.first_name ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, first_name: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Last Name</Label>
                <Input
                  value={editForm.last_name ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, last_name: e.target.value })
                  }
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Role</Label>
                <Input
                  value={editForm.role ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, role: e.target.value })
                  }
                  placeholder="Job title"
                />
              </div>
              <div className="space-y-2">
                <Label>Organization</Label>
                <Input
                  value={editForm.organization ?? ""}
                  onChange={(e) =>
                    setEditForm({ ...editForm, organization: e.target.value })
                  }
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Relationship</Label>
              <Input
                value={editForm.relationship ?? ""}
                onChange={(e) =>
                  setEditForm({ ...editForm, relationship: e.target.value })
                }
                placeholder="Colleague, Client, etc."
              />
            </div>
            <div className="space-y-2">
              <Label>Aliases (comma-separated)</Label>
              <Input
                value={editForm.aliases?.join(", ") ?? ""}
                onChange={(e) =>
                  setEditForm({
                    ...editForm,
                    aliases: e.target.value
                      .split(",")
                      .map((a) => a.trim())
                      .filter(Boolean),
                  })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Notes</Label>
              <Textarea
                value={editForm.notes ?? ""}
                onChange={(e) =>
                  setEditForm({ ...editForm, notes: e.target.value })
                }
                className="min-h-[80px]"
              />
            </div>
            <div className="flex items-center gap-3">
              <Switch
                checked={editForm.is_user ?? false}
                onCheckedChange={(checked) =>
                  setEditForm({ ...editForm, is_user: !!checked })
                }
              />
              <Label>This is me</Label>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
              <InfoRow label="Email" value={participant.email} />
              <InfoRow label="Role" value={participant.role} />
              <InfoRow label="Organization" value={participant.organization} />
              <InfoRow
                label="Relationship"
                value={participant.relationship}
              />
              <InfoRow
                label="First Seen"
                value={
                  participant.first_seen
                    ? format(new Date(participant.first_seen), "PP")
                    : null
                }
              />
              <InfoRow
                label="Last Seen"
                value={
                  participant.last_seen
                    ? format(new Date(participant.last_seen), "PP")
                    : null
                }
              />
            </div>

            {/* Aliases */}
            {Array.isArray(participant.aliases) && participant.aliases.length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">
                  Aliases
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {(Array.isArray(participant.aliases) ? participant.aliases : []).map((alias: string, i: number) => (
                    <Badge key={i} variant="secondary">
                      {alias}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Notes */}
            {participant.notes && (
              <div>
                <h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">
                  Notes
                </h3>
                <div className="whitespace-pre-wrap rounded-md border bg-muted/30 p-3 text-sm">
                  {participant.notes}
                </div>
              </div>
            )}
          </div>
        )}

        <Separator />

        {/* Recent recordings */}
        <div>
          <h3 className="mb-3 text-xs font-medium uppercase text-muted-foreground">
            Recent Recordings
          </h3>
          {participant.recent_recordings &&
          participant.recent_recordings.length > 0 ? (
            <div className="space-y-2">
              {participant.recent_recordings.slice(0, 5).map((rec) => (
                <Card
                  key={rec.id}
                  className="cursor-pointer px-3 py-2 transition-colors hover:bg-accent/50"
                  onClick={() => navigate(`/recordings/${rec.id}`)}
                >
                  <p className="text-sm font-medium">
                    {rec.title || rec.original_filename}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {rec.recorded_at
                      ? formatDistanceToNow(new Date(rec.recorded_at), {
                          addSuffix: true,
                        })
                      : format(new Date(rec.created_at), "PP")}
                  </p>
                </Card>
              ))}
              {participant.recent_recordings.length > 5 && (
                <p className="text-center text-xs text-muted-foreground">
                  +{participant.recent_recordings.length - 5} more recordings
                </p>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No recordings found
            </p>
          )}
        </div>
      </div>

      {/* Merge dialog */}
      {showMerge && (
        <MergeDialog
          open={showMerge}
          onOpenChange={setShowMerge}
          primaryParticipant={participant}
        />
      )}
    </ScrollArea>
  );
}

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div>
      <span className="text-muted-foreground">{label}</span>
      <p className="font-medium">{value || "-"}</p>
    </div>
  );
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}
